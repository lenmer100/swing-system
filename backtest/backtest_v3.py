"""Point-in-time backtest of v3 (same panel/dates as v2; financials+REITs now included because v3 has
models for them). No PIT consensus on disk -> growth yrs1-2 = trailing 3y CAGR (v2 clip), PE weight 0
(reinvester/no-consensus rule). ERP+rf = Damodaran month of the signal date. Train 2012-19, val 2020-21;
rows whose horizon ends after 2022-12-31 dropped; 2023+ never read."""
from __future__ import annotations
import json, math, sys, warnings
from pathlib import Path
from multiprocessing import Pool
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")
from valuation import assumptions as A, inputs as I
from valuation.engine_v3 import value_v3
from valuation.backtest import ic_stats, quint, SEAL, _pass1

OUT = Path(__file__).resolve().parents[1] / "data" / "valuation_v3_backtest.json"
SEC = {}


def _init(sec):
    global SEC; SEC = sec


def _val(args):
    t, rows = args
    out = []
    for d, typ, price, shares in rows:
        try:
            fs = I.firm_stats(t, d)
            if not fs or not fs.get("shares_diluted"):
                continue
            g = fs["rev_cagr_3y"] if fs["rev_cagr_3y"] is not None else 0.03
            g = min(max(g, A.BACKTEST_G_CLIP[0]), A.BACKTEST_G_CLIP[1])
            px_fs = price * shares / fs["shares_diluted"] if shares and shares > 0 else price  # split-consistent
            r = value_v3(t, d, px_fs, SEC.get(d, {}), typ=typ, cons=None, growth=g, detail=False)
            if r.get("status") != "ok":
                continue
            c = r["classification"]
            out.append(dict(ticker=t, date=d, typ=typ, fv_ratio=r["range"]["base"] / px_fs,
                            model=c.get("model"), moat=c.get("moat"), stage=c.get("stage")))
        except Exception:
            continue
    return out


def run(procs=8):
    p = pd.read_parquet(I.DS / "derived/v34_panel.parquet")
    p = p[(p.date <= pd.Timestamp("2021-12-31")) & (p.price > 0)]
    nf = p[~p.typ.isin(A.FINANCIAL_TYPES)]
    jobs = [(t, list(g.date)) for t, g in p.groupby("ticker")]
    with Pool(procs) as pool:
        r1 = [x for ch in pool.map(_pass1, jobs, chunksize=4) for x in ch]
    f = pd.DataFrame([dict(ticker=x["ticker"], date=x["date"], margin=x["fs"]["margin_ttm"],
                           s2c=x["fs"]["sales_to_capital_cycle"] or x["fs"]["sales_to_capital_raw"], beta=x["beta_own"]) for x in r1])
    f = f.merge(p[["ticker", "date", "typ"]], on=["ticker", "date"])
    sec = {}
    for (d, typ), g in f.groupby(["date", "typ"]):
        sec.setdefault(d, {})[typ] = dict(margin_median=g.margin.median(), beta_median=g.beta.median(),
                                          s2c_median=g.s2c.dropna().clip(*A.S2C_BOUNDS).median())
    jobs = [(t, list(zip(g.date, g.typ, g.price, g.shares))) for t, g in p.groupby("ticker")]
    with Pool(procs, initializer=_init, initargs=(sec,)) as pool:
        rows = [x for ch in pool.map(_val, jobs, chunksize=4) for x in ch]
    df = pd.DataFrame(rows).merge(p, on=["ticker", "date", "typ"])
    df["sig"] = np.log(df.fv_ratio.clip(lower=0.01))
    for h in (1, 2, 3):
        df[f"ret_{h}y_x"] = df[f"ret_{h}y"] - df[f"spy_{h}y"]
    df["ey"] = np.where(df.pe > 0, 1 / df.pe, np.nan); df["fcfy"] = np.where(df.pfcf > 0, 1 / df.pfcf, np.nan)
    v2 = pd.read_parquet(OUT.parent / "valuation_v2_backtest.parquet")[["ticker", "date", "sig", "fv", "price"]]
    v2 = v2.rename(columns={"sig": "sig_v2", "fv": "fv_v2", "price": "price_v2"})
    return df.merge(v2, on=["ticker", "date"], how="left")


def calib(s, col, h):
    """price convergence: gap now |log FV/P_t| vs gap later |log FV/P_t+h| (FV held fixed, raw returns)."""
    ok = s[(s.date + pd.DateOffset(years=h) <= SEAL) & s[f"ret_{h}y"].notna() & s[col].notna()]
    ok = ok[ok[col] > 0]
    g0 = np.log(ok[col]); g1 = g0 - np.log1p(ok[f"ret_{h}y"])
    slope = float(np.polyfit(g0, np.log1p(ok[f"ret_{h}y"]), 1)[0]) if len(ok) > 10 else None
    return dict(n=int(len(ok)), median_abs_gap_now=float(g0.abs().median()), median_abs_gap_after=float(g1.abs().median()),
                share_gap_shrinks=float((g1.abs() < g0.abs()).mean()), slope_logret_on_gap=slope,
                median_abs_err_pct=float((np.exp(g1.abs()) - 1).median()))


def evaluate(df):
    df = df.copy(); df["ratio_v2"] = df.fv_v2 / df.price_v2
    res = {}
    for name, lo, hi in (("train", "2012-01-01", "2019-12-31"), ("val", "2020-01-01", "2021-12-31")):
        s = df[(df.date >= lo) & (df.date <= hi)]
        both = s.dropna(subset=["sig_v2"])
        r = dict(n=int(len(s)), n_with_v2=int(len(both)), median_fv_to_price=float(s.fv_ratio.median()),
                 models=s.model.value_counts().to_dict())
        for h in (1, 2, 3):
            ret = f"ret_{h}y_x"; ok = s[s.date + pd.DateOffset(years=h) <= SEAL]; okb = both[both.date + pd.DateOffset(years=h) <= SEAL]
            if ok[ret].notna().sum() < 100:
                continue
            r[ret] = dict(v3_all=ic_stats(ok, "sig", ret), v3_same_universe_as_v2=ic_stats(okb, "sig", ret),
                          v2=ic_stats(okb, "sig_v2", ret), earnings_yield=ic_stats(ok, "ey", ret),
                          fcf_yield=ic_stats(ok, "fcfy", ret), v3_q5_minus_q1=quint(ok, "sig", ret))
            r[f"calibration_{h}y"] = dict(v3=calib(s, "fv_ratio", h), v2=calib(both, "ratio_v2", h))
        res[name] = r
    return res


if __name__ == "__main__":
    df = run(); df.to_parquet(OUT.with_suffix(".parquet"))
    res = evaluate(df)
    OUT.write_text(json.dumps(dict(note=__doc__, results=res), indent=1, default=str))
    print(json.dumps(res, indent=1, default=str))
