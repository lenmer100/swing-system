"""Point-in-time input assembly from data already on disk (SEC EDGAR via fund_pit, prices, DGS10, Yahoo consensus)."""
from __future__ import annotations
import json, functools
from pathlib import Path
import numpy as np, pandas as pd
from . import assumptions as A
from .liquidity import liquidity_asof
from .capital import monthly_returns, regression_beta, blume

DS = Path(__import__("os").environ.get("MARKET_STORE", "data_store") + "")
DEMO = Path("./data")


@functools.lru_cache(None)
def dgs10():
    d = pd.read_csv(DS / "bt/dgs10.csv", parse_dates=["observation_date"], na_values=".")
    return d.dropna().set_index("observation_date")["DGS10"] / 100


def risk_free(asof):
    s = dgs10()
    return float(s[s.index <= pd.Timestamp(asof)].iloc[-1])


@functools.lru_cache(None)
def fund(t):
    p = DS / f"bt/fund_pit/{t}.parquet"
    if not p.exists():
        return _with_supp(t, None)
    f = pd.read_parquet(p).sort_values("avail_date").reset_index(drop=True)
    f = f[f.revenue_ttm.notna()]
    return _with_supp(t, f)


SUPP = Path(__file__).parent / "cache" / "fund_supp"


def _with_supp(t, f):
    """Fallback to demo-local companyfacts build (valuation/edgar_supp.py) when the scanner's fund_pit has no usable
    revenue+operating income TTM, or its latest usable row is >200 days older than the supplement's."""
    sp = SUPP / f"{t}.parquet"
    if not sp.exists():
        return f
    s = pd.read_parquet(sp).sort_values("avail_date").reset_index(drop=True)
    ok = f[f.operating_income_ttm.notna()] if f is not None and "operating_income_ttm" in f else None
    if ok is None or not len(ok) or ok.avail_date.max() < s.avail_date.max() - pd.Timedelta(days=200) or pd.isna(f.iloc[-1].get("operating_income_ttm")) \
            or all(pd.isna(f.iloc[-1].get(k)) for k in ("shares_best", "shares_dil", "shares_outstanding")):
        return s
    return f


@functools.lru_cache(None)
def raw(t):
    p = DS / f"fundamentals/{t}.parquet"
    return pd.read_parquet(p) if p.exists() else None


@functools.lru_cache(None)
def prices(t):
    p = DS / f"bt/prices/{t}.parquet"
    return pd.read_parquet(p) if p.exists() else None


@functools.lru_cache(None)
def mret(t):
    px = prices(t)
    return None if px is None else monthly_returns(px)


@functools.lru_cache(None)
def type_map():
    p = pd.read_parquet(DS / "derived/v34_panel.parquet", columns=["ticker", "date", "typ"])
    return p.sort_values("date").groupby("ticker").typ.last().to_dict()


def fund_asof(t, asof, lag_rows=0):
    f = fund(t)
    if f is None:
        return None
    f = f[f.avail_date <= pd.Timestamp(asof)]
    if len(f) <= lag_rows:
        return None
    return f.iloc[-1 - lag_rows]


def invested_capital(r, ticker=None):
    """Operating invested capital = equity + debt - (cash + short-term investments, EDGAR PIT if cached)."""
    v = lambda k: r[k] if k in r.index and pd.notna(r[k]) else None
    eq = v("equity")
    if eq is None:
        return None
    d, c = v("total_debt") or 0, v("cash") or 0
    if ticker is not None:
        liq = liquidity_asof(ticker, r["avail_date"])
        if liq is not None:
            c = max(c, liq)
    return eq + d - c


def operating_ic(t, avail):
    """v5.1 (GE): operating-side invested capital = PP&E + intangibles + goodwill + receivables + inventory - payables
    (point-in-time XBRL). Used only when the financing side (equity + debt - cash) is <= 0, e.g. after large buybacks
    with cash/securities held for legacy liabilities. None if PP&E is not reported."""
    from . import concepts as C
    from .goodwill import goodwill_asof
    ppe = C.instant(t, "ppe_net", avail)
    if ppe is None:
        ppe = C.instant(t, "ppe_alt", avail)
    if ppe is None:   # gross - accumulated depreciation (filers that tag only these, e.g. GE)
        gr, ad = C.instant(t, "ppe_gross", avail), C.instant(t, "ppe_accdep", avail)
        ppe = gr - ad if gr is not None and ad is not None and gr > ad else None
    if ppe is None:
        return None
    gw = goodwill_asof(t, avail) or 0.0
    parts = [ppe, C.instant(t, "intangibles", avail) or 0.0, gw, C.instant(t, "receivables", avail) or 0.0,
             C.instant(t, "inventory", avail) or 0.0, -(C.instant(t, "payables", avail) or 0.0)]
    v = float(sum(parts))
    return v if v > 0 else None


def firm_stats(t, asof, price=None):
    """Firm-level fundamentals at `asof` (only filings available by then)."""
    f = fund(t)
    if f is None:
        return None
    f = f[f.avail_date <= pd.Timestamp(asof)]
    if len(f) < 1:           # v4.2: short history (IPO/new registrant) is valued and flagged, not dropped
        return None
    r = f.iloc[-1]
    g = lambda k: r.get(k) if k in r.index and pd.notna(r.get(k)) else None
    rev, ebit = g('revenue_ttm'), g('operating_income_ttm')
    if not rev or rev <= 0 or ebit is None:
        return None
    hist = f.tail(12)
    m_hist = (hist.get('operating_income_ttm', pd.Series(dtype=float)) / hist.revenue_ttm).dropna()
    ic = invested_capital(r, t)
    ic3 = invested_capital(f.iloc[-13], t) if len(f) >= 13 else None
    ic_basis = "Finanzierungsseite (Eigenkapital + Schulden − Liquidität)"
    if ic is None or ic <= 0:   # v5.1 (GE): financing side <= 0 -> operating side, same rule for the 3y-ago point
        op = operating_ic(t, r["avail_date"])
        if op is not None:
            ic, ic_basis = op, "operative Seite (Sachanlagen + Immaterielle + Goodwill + Working Capital), Finanzierungsseite ≤ 0"
            if len(f) >= 13 and (ic3 is None or ic3 <= 0):
                ic3 = operating_ic(t, f.iloc[-13]["avail_date"])
    rev3 = f.iloc[-13].revenue_ttm if len(f) >= 13 else None
    s2c = None
    if ic and ic3 and rev3 and ic - ic3 > 0 and rev - rev3 > 0:
        s2c = (rev - rev3) / (ic - ic3)
    # through-the-cycle: median of rolling 3y sales-to-capital over up to 10y of history
    win = []
    for j in range(max(12, len(f) - 40), len(f)):
        a, b = f.iloc[j], f.iloc[j - 12]
        i1, i0 = invested_capital(a, t), invested_capital(b, t)
        if i1 and i0 and i1 - i0 > 0 and a.revenue_ttm - b.revenue_ttm > 0:
            win.append((a.revenue_ttm - b.revenue_ttm) / (i1 - i0))
    s2c_cycle = float(np.median(win)) if len(win) >= 4 else None
    shares = g('shares_best') or g('shares_dil') or g('shares_outstanding')
    out = dict(data_source=str(r.get('source')), currency_reported=r.get('currency_reported') if 'currency_reported' in r.index and isinstance(r.get('currency_reported'), str) else 'USD', only_annual=bool(r.get('only_annual')) if 'only_annual' in r.index and pd.notna(r.get('only_annual')) else False,
               supp_note=r.get('supp_note') if 'supp_note' in r.index else None, ticker=t, filing_avail=str(pd.Timestamp(r.avail_date).date()), last_quarter_end=str(pd.Timestamp(r.last_quarter_end).date()),
               revenue_ttm=float(rev), ebit_ttm=float(ebit), margin_ttm=float(ebit / rev),
               margin_3y_median=float(m_hist.median()), margin_3y_max=float(m_hist.max()),
               revenue_ttm_3y_ago=None if rev3 is None else float(rev3),
               rev_cagr_3y=None if not rev3 or rev3 <= 0 else float((rev / rev3) ** (1 / 3) - 1),
               net_income_ttm=None if g('net_income_ttm') is None else float(g('net_income_ttm')),
               sbc_ttm=None if g('sbc_ttm') is None else float(g('sbc_ttm')),
               equity=None if g('equity') is None else float(g('equity')),
               total_debt=float(g('total_debt') or 0),
               cash=float(max(g('cash') or 0, liquidity_asof(t, r["avail_date"]) or 0)),
               cash_source="EDGAR Cash+kurzfr. Wertpapiere" if liquidity_asof(t, r["avail_date"]) else "EDGAR Cash (ohne Wertpapiere)",
               invested_capital=None if ic is None else float(ic), invested_capital_basis=ic_basis, invested_capital_3y_ago=None if ic3 is None else float(ic3),
               sales_to_capital_raw=s2c, sales_to_capital_cycle=s2c_cycle, s2c_windows=len(win), history_rows=int(len(f)), short_history=bool(len(f) < 4), shares_diluted=float(shares) if shares and pd.notna(shares) else None)
    return out


def tax_and_interest(t, asof, years=3):
    d = raw(t)
    if d is None:
        return None, None
    d = d[(d.fp == "FY") & (d.form.str.startswith("10-K") | d.form.str.startswith("20-F")) & (d.filed <= pd.Timestamp(asof))]
    d = d[(d.end - d.start).dt.days > 330]
    piv = d.sort_values("filed").drop_duplicates(["key", "end"], keep="last").pivot_table(index="end", columns="key", values="val", aggfunc="last")
    eff = None
    if {"income_tax", "pretax_income"} <= set(piv.columns):
        x = piv[["income_tax", "pretax_income"]].dropna().tail(years)
        if len(x) and x.pretax_income.sum() > 0:
            eff = float(x.income_tax.sum() / x.pretax_income.sum())
    intr = None
    if "interest_expense" in piv.columns:
        s = piv.interest_expense.dropna()
        if len(s):
            intr = float(abs(s.iloc[-1]))
    return eff, intr


def fy_end_month(t):
    d = raw(t)
    if d is None:
        return 12, None
    x = d[(d.key == "revenue") & (d.fp == "FY")]
    x = x[(x.end - x.start).dt.days > 330]
    if not len(x):
        return 12, None
    last = x.end.max()
    return int(last.month), last


def last_close(t, asof):
    px = prices(t)
    if px is None:
        return None
    px = px[px.date <= pd.Timestamp(asof)]
    return None if not len(px) else float(px.close.iloc[-1])


def own_beta(t, asof):
    s, m = mret(t), mret("SPY")
    if s is None:
        return None, 0
    b, n = regression_beta(s, m, asof)
    return blume(b), n


def pe_history(t, asof, price_now, years=5):
    """Trailing GAAP PE history (month-end price / TTM diluted EPS from EDGAR filings as available)."""
    f, px = fund(t), prices(t)
    if f is None or px is None:
        return None
    a = pd.Timestamp(asof)
    f = f[(f.avail_date <= a)].copy()
    if "net_income_ttm" not in f or "shares_best" not in f:
        return None
    # prices are split-adjusted; scale as-reported share counts by splits after each filing
    sp = px[(px.splits.fillna(0) > 0)][["date", "splits"]] if "splits" in px else px.iloc[:0]
    fac = f.avail_date.map(lambda d: float(np.prod(sp[sp.date > d].splits)) if len(sp) else 1.0)
    f["eps"] = f.net_income_ttm / (f.shares_best * fac)
    p = px[(px.date <= a) & (px.date > a - pd.DateOffset(years=years))].set_index("date").close.resample("ME").last().dropna()
    L = p.rename("px").reset_index(); L["date"] = L.date.astype("datetime64[ns]")
    R = f[["avail_date", "eps"]].rename(columns={"avail_date": "date"}); R["date"] = R.date.astype("datetime64[ns]")
    e = pd.merge_asof(L, R.sort_values("date"), on="date")
    e = e[e.eps > 0]
    if len(e) < 12:
        return None
    pe = e.px / e.eps
    cur_eps = f.eps.iloc[-1]
    cur = price_now / cur_eps if cur_eps > 0 else None
    med = float(pe.median())
    return dict(months=int(len(pe)), median=med, p25=float(pe.quantile(.25)), p75=float(pe.quantile(.75)),
                current_trailing=cur, current_vs_median=None if cur is None else cur / med - 1,
                percentile=None if cur is None else float((pe < cur).mean()), gaap_eps_ttm=float(cur_eps))


def sector_stats(asof, typ_filter=None):
    """Bottom-up sector medians across the full pool at `asof`: op margin, sales-to-capital, beta, trailing PE."""
    tm = type_map()
    rows = []
    for t, typ in tm.items():
        if typ_filter and typ not in typ_filter:
            continue
        fs = firm_stats(t, asof)
        if not fs:
            continue
        b, n = own_beta(t, asof)
        pr = last_close(t, asof)
        pe = None
        if pr and fs["net_income_ttm"] and fs["shares_diluted"] and fs["net_income_ttm"] > 0:
            pe = pr / (fs["net_income_ttm"] / fs["shares_diluted"])
        rows.append(dict(ticker=t, typ=typ, margin=fs["margin_ttm"], s2c=fs["sales_to_capital_cycle"] or fs["sales_to_capital_raw"], beta=b, pe=pe))
    df = pd.DataFrame(rows)
    out = {}
    for typ, g in df.groupby("typ"):
        s2c = g.s2c.dropna().clip(*A.S2C_BOUNDS)
        pe = g.pe.dropna()
        pe = pe[(pe > 0) & (pe < 200)]
        out[typ] = dict(n=int(len(g)), margin_median=float(g.margin.median()),
                        s2c_median=float(s2c.median()) if len(s2c) else None,
                        beta_median=float(g.beta.dropna().median()) if g.beta.notna().any() else None,
                        pe_median=float(pe.median()) if len(pe) else None, pe_n=int(len(pe)),
                        tickers=sorted(g.ticker)[:60])
    return out
