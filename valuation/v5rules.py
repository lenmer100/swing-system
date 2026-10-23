"""v5 building blocks (merged rule set of the three V5 method audits, design_ref/V5_METHOD_AUDIT_*.md).
All thresholds fixed a priori with the economic reason next to them; nothing fitted to a price or target level."""
from __future__ import annotations
import math
import numpy as np
import pandas as pd
from . import inputs as I, concepts as C
from .goodwill import goodwill_asof

ACQ_GW_SHARE = 0.25      # dGoodwill > 25 % of dIC over 3y: growth was bought -> charge acquisitions (s2c incl. goodwill)
ROIC_CONSIST = 0.5       # implied incremental ROIC m(1-t)S2C must lie within +-50 % of the measured ROIC (mega audit 1)
STABLE_P10 = 0.7         # proven long-run margin: p10 >= 0.7 x median over >= 20 quarters (mega audit 3)
INFLATION = 0.025        # REIT organic rent growth up to inflation needs no retention (CYC R2); long-run US CPI target 2 % + 0.5 pp
CAPTIVE_PB = 1.0         # finance-arm equity at book (P/B 1 = ROE ~ CoE; CYC C5)
# Damodaran cumulative 10-year default rates by synthetic rating (order = assumptions.RATING_SPREADS)
DEFAULT_10Y = [0.0007, 0.0051, 0.0060, 0.0066, 0.0250, 0.0754, 0.1663, 0.2500, 0.3680, 0.4500, 0.5901, 0.7000, 0.8500, 0.8500, 1.0]
DISTRESS_IC = 0.5        # distress value = 50 % of book invested capital (fire-sale recovery, mega audit 6)


def _f(x):
    try:
        x = float(x); return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def capital_ex_goodwill(t, asof, fs):
    """IC ex goodwill (and ex acquired intangibles where tagged) now and 3y ago; organic and total S2C; ROIC ex GW (TTM).
    Rule (merged GROWTH Q1/MEGA check 1/CYC X5): organic growth needs organic capital -> S2C from dIC ex goodwill;
    if dGoodwill > 25 % of dIC the growth was bought -> acquisitions are charged at their purchase price (S2C incl. GW)."""
    f = I.fund(t)
    f = f[f.avail_date <= pd.Timestamp(asof)] if f is not None else None
    out = dict(gw=None, ic_ex=None, s2c_organic=None, s2c_total=fs.get("sales_to_capital_raw"), acquisitive=False, roic_ex_ttm=None)
    if f is None or not len(f) or fs.get("invested_capital") is None:
        return out
    gw = goodwill_asof(t, f.avail_date.iloc[-1], f.last_quarter_end.iloc[-1])
    if gw is None:
        return out
    ia = C.instant(t, "intangibles", asof) or 0.0
    ic_ex = fs["invested_capital"] - gw - ia
    out.update(gw=gw, intangibles=ia, ic_ex=ic_ex)
    nopat = fs["ebit_ttm"] * 0.75
    if ic_ex > 0.05 * fs["revenue_ttm"]:
        out["roic_ex_ttm"] = nopat / ic_ex
    if len(f) >= 13 and fs.get("invested_capital_3y_ago") is not None:
        r3 = f.iloc[-13]
        gw3 = goodwill_asof(t, r3.avail_date, r3.last_quarter_end) or 0.0
        d_ic = fs["invested_capital"] - fs["invested_capital_3y_ago"]
        d_gw = gw - gw3
        d_rev = fs["revenue_ttm"] - float(r3.revenue_ttm)
        d_ic_ex = d_ic - d_gw
        out.update(d_ic=d_ic, d_gw=d_gw)
        if d_rev > 0 and d_ic_ex > 0:
            out["s2c_organic"] = d_rev / d_ic_ex
        out["acquisitive"] = bool(d_ic > 0 and d_gw > ACQ_GW_SHARE * d_ic)
        # goodwill jump in the last 4 quarters (deal closed) -> consensus growth contains the deal, its price is on the balance sheet
        if len(f) >= 5:
            r1 = f.iloc[-5]
            gw1 = goodwill_asof(t, r1.avail_date, r1.last_quarter_end) or 0.0
            out["deal_closed_1y"] = bool(gw - gw1 > 0.10 * max(fs["invested_capital"], 1.0))
    return out


def ppe_roic(t, asof, fs):
    """ROIC when IC <= 0 or tiny (buy-backs, cash tag errors): NOPAT / net PP&E (operating assets), mega audit 10/GROWTH 5."""
    p = C.instant(t, "ppe_net", asof)
    if p and p > 0.05 * fs["revenue_ttm"]:
        return fs["ebit_ttm"] * 0.75 / p
    return None


def stable_margin(x):
    """Own long-run median margin if proven stable (>= 20 quarters, p10 >= 0.7 x median > 0), else None."""
    ml, p10, n = x.get("margin_long"), x.get("margin_p10"), x.get("margin_quarters") or 0
    if ml is not None and p10 is not None and n >= 20 and ml > 0 and p10 >= STABLE_P10 * ml:
        return ml
    return None


def revenue_trend(t, asof):
    """Cycle-normalised revenue (CYC C2): log-linear trend of TTM revenue over up to 10y (>= 20 quarters), evaluated at
    the last quarter; slope = trend growth p.a. -> (trend revenue, slope) or (None, None)."""
    f = I.fund(t)
    if f is None:
        return None, None
    f = f[f.avail_date <= pd.Timestamp(asof)].tail(40)
    r = pd.to_numeric(f.revenue_ttm, errors="coerce")
    ok = r > 0
    if ok.sum() < 20:
        return None, None
    y = np.log(r[ok].values); x = (pd.to_datetime(f.last_quarter_end[ok]) - pd.to_datetime(f.last_quarter_end.iloc[-1])).dt.days.values / 365.25
    b, a = np.polyfit(x, y, 1)
    return float(math.exp(a)), float(math.exp(b) - 1)


def default_probability(ebit_norm, interest, debt):
    """Damodaran synthetic rating from interest coverage on normalised EBIT -> cumulative 10y default rate."""
    from .assumptions import RATING_SPREADS
    if not debt or debt <= 0 or not interest or interest <= 0:
        return 0.0, None
    cov = (ebit_norm or 0) / interest
    for k, (lo, _) in enumerate(RATING_SPREADS):
        if cov >= lo:
            return DEFAULT_10Y[k], cov
    return DEFAULT_10Y[-1], cov


def persistence_share(pers, cap=0.75):
    """Continuous excess-return share from persistence (CYC B4): 0 at <= 20 % of years above ke, cap at >= 80 %."""
    if pers is None:
        return 0.0
    return cap * max(0.0, min(1.0, (pers - 0.2) / 0.6))


def payout_ratio(t, asof, ni_or_affo):
    d = C.annual(t, "dividends", asof, n=1)
    if not d or not ni_or_affo or ni_or_affo <= 0:
        return None
    return max(0.0, min(1.0, abs(d[0]) / ni_or_affo))


def tangible_roe_series(t, asof, n=24, ex_aoci=False):
    """ROTCE (bank) or ROE ex AOCI (insurer) per TTM row over the last n quarters (PIT goodwill per row; intangibles and
    preferred at the latest value, preferred dividends netted where tagged). -> (series, latest denominator)."""
    f = I.fund(t)
    if f is None or "equity" not in f:
        return None, None
    f = f[f.avail_date <= pd.Timestamp(asof)].tail(n)
    if not len(f):
        return None, None
    pref = C.instant(t, "preferred", asof) or 0.0
    pdv = (C.annual(t, "pref_div", asof) or [0.0])[0] or 0.0
    ia = C.instant(t, "intangibles", asof) or 0.0
    aoci = (C.instant(t, "aoci", asof) or 0.0) if ex_aoci else 0.0
    vals, den = [], None
    for _, r in f.iterrows():
        gw = 0.0 if ex_aoci else (goodwill_asof(t, r.avail_date, r.last_quarter_end) or 0.0)
        d_ = (r.equity or 0) - pref - gw - (0 if ex_aoci else ia) - aoci
        if d_ and d_ > 0 and pd.notna(r.net_income_ttm):
            vals.append((r.net_income_ttm - pdv) / d_)
        den = d_
    s = pd.Series(vals, dtype=float)
    s = s[(s > -0.5) & (s < 0.8)]
    return s, den


def insurer_normalised(t, asof, tax):
    """Normalised insurer earnings (CYC I1): net margin on earned premiums, median over up to 10 fiscal years (spans
    catastrophe and reserve cycles; it is 1 - combined ratio + float yield after tax), x current premiums.
    Tagging of losses/LAE/underwriting expense is too patchy for a direct combined ratio."""
    pr = C.d_annual(t, "premiums", asof, n=10)
    if len(pr) < 3:
        return None
    f = I.fund(t)
    f = f[f.avail_date <= pd.Timestamp(asof)] if f is not None else None
    if f is None or not len(f):
        return None
    m = []
    for end, p in pr:
        r = f[pd.to_datetime(f.last_quarter_end) == end]
        if len(r) and pd.notna(r.net_income_ttm.iloc[-1]) and p > 0:
            m.append(float(r.net_income_ttm.iloc[-1]) / p)
    if len(m) < 3:
        return None
    nm = float(np.median(m))
    return dict(net_margin_premiums=nm, premiums=pr[0][1], ni_norm=nm * pr[0][1], years=len(m), combined_ratio=None)


def ebita_cycle(t, asof):
    """CYC C3: cycle centre on EBITA (operating income + amortisation of acquired intangibles, which is non-cash and
    does not recur for organic growth) over up to 10y; -> dict(median, p25, p75, amort_share) or None."""
    f = I.fund(t)
    if f is None or "amortization_ttm" not in f:
        return None
    f = f[f.avail_date <= pd.Timestamp(asof)].tail(40)
    am = pd.to_numeric(f.amortization_ttm, errors="coerce")
    if am.notna().sum() < 4 or pd.isna(am.iloc[-1]):     # missing early rows = no acquisition amortisation yet (0)
        return None
    m = ((pd.to_numeric(f.operating_income_ttm, errors="coerce") + am.fillna(0)) / f.revenue_ttm).replace([np.inf, -np.inf], np.nan).dropna()
    if len(m) < 20:
        return None
    last = float(am.fillna(0).iloc[-1]) / float(f.revenue_ttm.iloc[-1])
    return dict(median=float(m.median()), p25=float(m.quantile(.25)), p75=float(m.quantile(.75)), amort_now=last)
