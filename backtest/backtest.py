"""Point-in-time ranking/accuracy backtest of the v2 FCFF DCF (no consensus history on disk ->
revenue growth yrs 1-2 = trailing 3y CAGR clipped; same fixed assumptions otherwise).
Train = signal dates 2012-2019, Val = 2020-2021. Any row whose return window ends after
2022-12-31 is dropped; 2023+ (sealed) is never read."""
from __future__ import annotations
import json, math, sys
from pathlib import Path
from multiprocessing import Pool
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from valuation import assumptions as A, inputs as I
from valuation.dcf import DCFInputs, run_dcf
from valuation.capital import wacc as wacc_fn, combine_beta

SEAL = pd.Timestamp("2022-12-31")
OUT = Path(__file__).resolve().parents[1] / "data" / "valuation_v2_backtest.json"


def _pass1(args):
    t, dates = args
    res = []
    for d in dates:
        fs = I.firm_stats(t, d)
        if not fs or not fs["shares_diluted"]:
            continue
        b, n = I.own_beta(t, d)
        eff, intr = I.tax_and_interest(t, d)
        res.append(dict(ticker=t, date=d, fs=fs, beta_own=b, tax_eff=eff, interest=intr))
    return res


def load_panel():
    p = pd.read_parquet(I.DS / "derived/v34_panel.parquet")
    p = p[(p.date <= pd.Timestamp("2021-12-31")) & ~p.typ.isin(A.FINANCIAL_TYPES) & (p.price > 0)]
    return p


def run(procs=8):
    p = load_panel()
    jobs = [(t, list(g.date)) for t, g in p.groupby("ticker")]
    with Pool(procs) as pool:
        r1 = [x for chunk in pool.map(_pass1, jobs, chunksize=4) for x in chunk]
    f = pd.DataFrame([dict(ticker=x["ticker"], date=x["date"], margin=x["fs"]["margin_ttm"],
                           s2c=x["fs"]["sales_to_capital_cycle"] or x["fs"]["sales_to_capital_raw"], beta=x["beta_own"]) for x in r1])
    f = f.merge(p[["ticker", "date", "typ"]], on=["ticker", "date"])
    sec = f.groupby(["date", "typ"]).agg(margin_median=("margin", "median"), beta_median=("beta", "median"),
                                          s2c_median=("s2c", lambda s: s.dropna().clip(*A.S2C_BOUNDS).median())).reset_index()
    sec = {(r.date, r.typ): r._asdict() for r in sec.itertuples()}
    pm = p.set_index(["ticker", "date"])
    rows = []
    for x in r1:
        key = (x["ticker"], x["date"])
        if key not in pm.index:
            continue
        pr = pm.loc[key]
        fs, s = x["fs"], sec.get((x["date"], pr.typ), {})
        if fs["revenue_ttm"] <= 0 or fs["ebit_ttm"] is None:
            continue
        rf = I.risk_free(x["date"]); gT = min(rf, A.TERMINAL_G_CAP)
        tax_m = A.marginal_tax(A.COUNTRY.get(x["ticker"], "US"), x["date"].year)
        tax_eff = min(max(x["tax_eff"] if x["tax_eff"] is not None else tax_m, 0.05), tax_m)
        beta = combine_beta(x["beta_own"], s.get("beta_median"))
        shares = pr.shares if pr.shares and pr.shares > 0 else fs["shares_diluted"]
        mcap = pr.price * shares
        cap = wacc_fn(rf, beta, mcap, fs["total_debt"], fs["ebit_ttm"], x["interest"], tax_m)
        g = fs["rev_cagr_3y"] if fs["rev_cagr_3y"] is not None else 0.03
        g = min(max(g, A.BACKTEST_G_CLIP[0]), A.BACKTEST_G_CLIP[1])
        own = fs["margin_3y_median"]; sm = s.get("margin_median", own)
        sm = own if sm is None or not math.isfinite(sm) else sm
        s2c = fs["sales_to_capital_cycle"] or fs["sales_to_capital_raw"] or s.get("s2c_median") or A.S2C_FALLBACK
        s2c = min(max(s2c, A.S2C_BOUNDS[0]), A.S2C_BOUNDS[1])
        ic = fs["invested_capital"] or 0
        roic = fs["ebit_ttm"] * (1 - tax_eff) / ic if ic > 0 else cap["wacc"]
        di = DCFInputs(fs["revenue_ttm"], fs["margin_ttm"], own + A.MARGIN_REVERSION * (sm - own), g, g, gT,
                       tax_eff, tax_m, s2c, roic, cap["wacc"], cap["wacc_mature"], fs["total_debt"] - fs["cash"],
                       fs["shares_diluted"])
        # per-share value scaled to panel share basis (split consistency): equity / panel shares
        d = run_dcf(di, detail=False)
        v = d["equity"] / shares
        rows.append(dict(ticker=x["ticker"], date=x["date"], typ=pr.typ, price=pr.price, fv=v, wacc=cap["wacc"],
                         ret_1y=pr.ret_1y - pr.spy_1y if pd.notna(pr.ret_1y) else np.nan,
                         ret_2y=pr.ret_2y - pr.spy_2y if pd.notna(pr.ret_2y) else np.nan,
                         ey=(1 / pr.pe) if pr.pe and pr.pe > 0 else np.nan,
                         fcfy=(1 / pr.pfcf) if pr.pfcf and pr.pfcf > 0 else np.nan))
    df = pd.DataFrame(rows)
    df["sig"] = np.log(df.fv.clip(lower=df.price * 0.01) / df.price)
    df.loc[df.fv <= 0, "sig"] = np.log(0.01)
    return df


def ic_stats(df, sig, ret):
    ics = []
    for d, g in df.dropna(subset=[sig, ret]).groupby("date"):
        if len(g) >= 30:
            ics.append(g[sig].rank().corr(g[ret].rank()))
    ics = np.array(ics)
    if not len(ics):
        return None
    t = ics.mean() / (ics.std(ddof=1) / math.sqrt(len(ics))) if len(ics) > 1 else None
    return dict(ic_mean=float(ics.mean()), t=float(t) if t else None, n_dates=int(len(ics)))


def quint(df, sig, ret):
    out = []
    for d, g in df.dropna(subset=[sig, ret]).groupby("date"):
        if len(g) >= 30:
            q = pd.qcut(g[sig].rank(method="first"), 5, labels=False)
            out.append((g[ret][q == 4].mean() - g[ret][q == 0].mean(), g[ret][q == 4].median() - g[ret][q == 0].median()))
    return dict(mean=float(np.mean([a for a, b in out])), median=float(np.mean([b for a, b in out]))) if out else None


def evaluate(df):
    res = {}
    for name, lo, hi, rets in (("train", "2012-01-01", "2019-12-31", ("ret_1y", "ret_2y")),
                               ("val", "2020-01-01", "2021-12-31", ("ret_1y",))):
        s = df[(df.date >= lo) & (df.date <= hi)].copy()
        r = dict(n=int(len(s)), median_fv_to_price=float((s.fv / s.price).median()),
                 share_fv_above_price=float((s.fv > s.price).mean()))
        for ret in rets:
            h = 1 if ret == "ret_1y" else 2
            ok = s[s.date + pd.DateOffset(years=h) <= SEAL]
            r[ret] = dict(v2_dcf=ic_stats(ok, "sig", ret), q5_minus_q1=quint(ok, "sig", ret),
                          baseline_earnings_yield=ic_stats(ok, "ey", ret), baseline_fcf_yield=ic_stats(ok, "fcfy", ret),
                          hit_rate_direction=float(((ok.sig > 0) == (ok[ret] > 0)).mean()),
                          v2_dcf_positive_fv_only=ic_stats(ok[ok.fv > 0], "sig", ret),
                          share_negative_fv=float((ok.fv <= 0).mean()))
            # accuracy: does the price gap close? share of rows where |log(FV/P)| shrinks after h years
        res[name] = r
    return res


if __name__ == "__main__":
    df = run()
    df.to_parquet(OUT.with_suffix(".parquet"))
    res = evaluate(df)
    OUT.write_text(json.dumps(dict(note=__doc__, results=res), indent=1, default=float))
    print(json.dumps(res, indent=1, default=float))
