"""Point-in-time backtest of v4 on the v3 panel/dates. No PIT consensus on disk -> growth yrs 1-2 = trailing 3y CAGR
(clip as v3), archetype from PIT numbers with trailing growth. Peers (archetype, archetype x sector, profitable by
sector) per signal date from the same pass. Train 2012-19, val 2020-21; horizon must end <= 2022-12-31; 2023+ never read."""
from __future__ import annotations
import json, sys, warnings
from pathlib import Path
from multiprocessing import Pool
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")
from valuation import assumptions as A, inputs as I, engine_v4 as E
from valuation.backtest import ic_stats, quint, SEAL

OUT = Path(__file__).resolve().parents[1] / "data" / "valuation_v4_backtest.json"
G = {}


def _init(g):
    G.update(g)


def _g(fs):
    g = fs["rev_cagr_3y"] if fs["rev_cagr_3y"] is not None else 0.03
    return min(max(g, A.BACKTEST_G_CLIP[0]), A.BACKTEST_G_CLIP[1])


def _p1(args):
    t, rows = args; out = []; st = (None, None)
    for d, typ, price, shares in sorted(rows, key=lambda r: r[0]):
        try:
            fs = I.firm_stats(t, d)
            if not fs or not fs.get("shares_diluted"):
                continue
            px = price * shares / fs["shares_diluted"] if shares and shares > 0 else price
            a, why, x = E.arch_of(t, d, px, typ, None, growth=_g(fs), chain=st)
            st = (a, x.get("raw_class"))
            b, _ = I.own_beta(t, d)
            out.append(dict(ticker=t, date=d, typ=typ, arch=a, margin=fs["margin_ttm"],
                            s2c=fs["sales_to_capital_cycle"] or fs["sales_to_capital_raw"], beta=b, capex_rev=x["capex_rev"], growth=x["growth"]))
        except Exception:
            continue
    return out


def _val(args):
    t, rows = args; out = []; st = (None, None)
    for d, typ, price, shares in sorted(rows, key=lambda r: r[0]):
        try:
            fs = I.firm_stats(t, d)
            if not fs or not fs.get("shares_diluted"):
                continue
            px = price * shares / fs["shares_diluted"] if shares and shares > 0 else price
            r = E.value_v4(t, d, px, G["peers"].get(d, {}), G["secs"].get(d, {}), typ=typ, cons=None, growth=_g(fs), detail=False, chain=st)
            if r.get("status") != "ok":
                continue
            st = (r["archetype"]["key"], r["archetype"].get("raw"))
            out.append(dict(ticker=t, date=d, typ=typ, fv4=r["range"]["base"] / px, arch=r["archetype"]["key"], reliable=r["reliable"]))
        except Exception:
            continue
    return out


def run(procs=8):
    p = pd.read_parquet(I.DS / "derived/v34_panel.parquet")
    p = p[(p.date <= pd.Timestamp("2021-12-31")) & (p.price > 0)]
    jobs = [(t, list(zip(g.date, g.typ, g.price, g.shares))) for t, g in p.groupby("ticker")]
    with Pool(procs) as pool:
        r1 = pd.DataFrame([x for ch in pool.map(_p1, jobs, chunksize=4) for x in ch])
    peers, secs = {}, {}
    for d, g in r1.groupby("date"):
        peers[d] = E.peer_stats(g.to_dict("records"))
        secs[d] = {ty: dict(margin_median=h.margin.median(), beta_median=h.beta.median(), s2c_median=h.s2c.dropna().clip(*A.S2C_BOUNDS).median())
                   for ty, h in g.groupby("typ")}
    with Pool(procs, initializer=_init, initargs=(dict(peers=peers, secs=secs),)) as pool:
        rows = [x for ch in pool.map(_val, jobs, chunksize=4) for x in ch]
    df = pd.DataFrame(rows).merge(p, on=["ticker", "date", "typ"])
    df["sig4"] = np.log(df.fv4.clip(lower=0.01))
    for h in (1, 2, 3):
        df[f"ret_{h}y_x"] = df[f"ret_{h}y"] - df[f"spy_{h}y"]
    df["fcfy"] = np.where(df.pfcf > 0, 1 / df.pfcf, np.nan)
    v3 = pd.read_parquet(OUT.parent / "valuation_v3_backtest.parquet")[["ticker", "date", "sig"]].rename(columns={"sig": "sig3"})
    return df.merge(v3, on=["ticker", "date"], how="left")


def evaluate(df):
    res = {}
    for name, lo, hi in (("train", "2012-01-01", "2019-12-31"), ("val", "2020-01-01", "2021-12-31")):
        s = df[(df.date >= lo) & (df.date <= hi)]
        r = dict(n=int(len(s)), archetypes=s.arch.value_counts().to_dict(), share_reliable=float(s.reliable.mean()))
        # mega audit 1: market-consistency acceptance test (NOT a tuning target): pool median FV/price in 0.85-1.15
        mm = s.groupby("date").fv4.median()
        r["median_fv_px"] = dict(pool=float(s.fv4.median()), monthly_median_of_medians=float(mm.median()),
                                 monthly_min=float(mm.min()), monthly_max=float(mm.max()),
                                 by_archetype={a: float(g.fv4.median()) for a, g in s.groupby("arch")},
                                 test="PASS" if 0.85 <= float(mm.median()) <= 1.15 else "FAIL")
        # stability (archetype audit F10): yearly class per ticker (last signal date per year), flips / ticker-years
        y = s.assign(yr=s.date.dt.year).sort_values("date").groupby(["ticker", "yr"]).arch.last().reset_index()
        y["prev"] = y.groupby("ticker").arch.shift()
        y = y.dropna(subset=["prev"])
        r["stability"] = dict(flip_rate_total=float((y.arch != y.prev).mean()),
                              by_archetype={a: float((g.arch != g.prev).mean()) for a, g in y.groupby("prev") if len(g) >= 30})
        for h in (1, 3):
            ret = f"ret_{h}y_x"; ok = s[s.date + pd.DateOffset(years=h) <= SEAL]
            both = ok.dropna(subset=["sig3"])
            if ok[ret].notna().sum() < 100:
                continue
            r[ret] = dict(v4=ic_stats(both, "sig4", ret), v3=ic_stats(both, "sig3", ret), fcf_yield=ic_stats(both, "fcfy", ret),
                          v4_reliable_only=ic_stats(both[both.reliable], "sig4", ret), v4_q5_minus_q1=quint(both, "sig4", ret),
                          by_archetype={a: dict(n=int(len(g)), v4=ic_stats(g, "sig4", ret), v3=ic_stats(g, "sig3", ret), fcf_yield=ic_stats(g, "fcfy", ret))
                                        for a, g in both.groupby("arch") if len(g) >= 150})
        res[name] = r
    return res


if __name__ == "__main__":
    df = run(); df.to_parquet(OUT.with_suffix(".parquet"))
    res = evaluate(df)
    OUT.write_text(json.dumps(dict(note=__doc__, results=res), indent=1, default=str))
    print(json.dumps(res, indent=1, default=str)[:6000])
