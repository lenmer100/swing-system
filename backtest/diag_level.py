"""Level decomposition 2012-19 (diagnosis, no tuning): Dec signal dates, every 3rd ticker.
Run per switch set via env V4_DIAG; peers from one baseline pass (cached)."""
import json, os, pickle, sys, warnings
from pathlib import Path
from multiprocessing import Pool
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1])); warnings.filterwarnings("ignore")
from valuation import backtest_v4 as B, engine_v4 as E, inputs as I, assumptions as A
PK = Path("/tmp/diag_peers.pkl")

def jobs():
    p = pd.read_parquet(I.DS / "derived/v34_panel.parquet")
    p = p[(p.date <= "2019-12-31") & (p.date.dt.month == 12) & (p.price > 0)]
    tk = sorted(p.ticker.unique())[::3]; p = p[p.ticker.isin(tk)]
    return p, [(t, list(zip(g.date, g.typ, g.price, g.shares))) for t, g in p.groupby("ticker")]

def _v(args):
    t, rows = args; out = []
    for d, typ, price, shares in rows:
        try:
            fs = I.firm_stats(t, d)
            if not fs or not fs.get("shares_diluted"): continue
            px = price * shares / fs["shares_diluted"] if shares and shares > 0 else price
            r = E.value_v4(t, d, px, B.G["peers"].get(d, {}), B.G["secs"].get(d, {}), typ=typ, cons=None, growth=B._g(fs), detail=False)
            if r.get("status") != "ok": continue
            out.append(dict(ticker=t, date=d, arch=r["archetype"]["key"], fv=r["range"]["base"] / px,
                            zero=r["range"]["base"] <= 0, wacc=r["cost_of_capital"]["wacc"], beta=r["cost_of_capital"]["beta"],
                            ke=r["cost_of_capital"]["cost_of_equity"], m_start=r["margin"]["start"], m_t=r["margin"]["targets"]["base"] if r.get("margin") else None))
        except Exception:
            continue
    return out

if __name__ == "__main__":
    p, J = jobs()
    if not PK.exists():
        with Pool(8) as pool:
            r1 = pd.DataFrame([x for ch in pool.map(B._p1, J, chunksize=2) for x in ch])
        peers = {d: E.peer_stats(g.to_dict("records")) for d, g in r1.groupby("date")}
        secs = {d: {ty: dict(margin_median=h.margin.median(), beta_median=h.beta.median(), s2c_median=h.s2c.dropna().clip(*A.S2C_BOUNDS).median())
                    for ty, h in g.groupby("typ")} for d, g in r1.groupby("date")}
        PK.write_bytes(pickle.dumps((peers, secs)))
    peers, secs = pickle.loads(PK.read_bytes())
    with Pool(8, initializer=B._init, initargs=(dict(peers=peers, secs=secs),)) as pool:
        df = pd.DataFrame([x for ch in pool.map(_v, J, chunksize=2) for x in ch])
    tag = os.environ.get("V4_DIAG", "") or "baseline"
    df.to_parquet(f"/tmp/diag_{tag.replace(',', '+')}.parquet")
    mm = df.groupby("date").fv.median()
    print(tag, len(df), "pool", round(df.fv.median(), 3), "monthly", round(mm.median(), 3), "zero%", round(df.zero.mean(), 3),
          {a: round(g.fv.median(), 2) for a, g in df.groupby("arch")}, "wacc", round(df.wacc.median(), 4), "beta", round(df.beta.median(), 2), flush=True)
