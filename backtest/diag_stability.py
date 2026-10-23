"""Archetype stability 2012-19 (train only): quarterly chain per ticker, yearly flip rate (last class per year)."""
import sys, warnings
from pathlib import Path
from multiprocessing import Pool
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1])); warnings.filterwarnings("ignore")
from valuation import backtest_v4 as B, inputs as I

def _p(args):
    t, rows = args; out = []; st = (None, None)
    for d, typ, price, shares in sorted(rows, key=lambda r: r[0]):
        try:
            fs = I.firm_stats(t, d)
            if not fs or not fs.get("shares_diluted"): continue
            px = price * shares / fs["shares_diluted"] if shares and shares > 0 else price
            a, why, x = B.E.arch_of(t, d, px, typ, None, growth=B._g(fs), chain=st)
            st = (a, x.get("raw_class")); out.append(dict(ticker=t, date=d, arch=a, raw=x.get("raw_class")))
        except Exception:
            continue
    return out

def flips(df, col):
    y = df.assign(yr=df.date.dt.year).sort_values("date").groupby(["ticker", "yr"])[col].last().reset_index()
    y["prev"] = y.groupby("ticker")[col].shift(); y = y.dropna(subset=["prev"])
    return round(float((y[col] != y.prev).mean()), 3), {a: round(float((g[col] != g.prev).mean()), 3) for a, g in y.groupby("prev") if len(g) >= 30}

if __name__ == "__main__":
    step = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    p = pd.read_parquet(I.DS / "derived/v34_panel.parquet"); p = p[(p.date <= "2019-12-31") & (p.price > 0)]
    tk = sorted(p.ticker.unique())[::step]; p = p[p.ticker.isin(tk)]
    J = [(t, list(zip(g.date, g.typ, g.price, g.shares))) for t, g in p.groupby("ticker")]
    with Pool(8) as pool:
        df = pd.DataFrame([x for ch in pool.map(_p, J, chunksize=2) for x in ch])
    df.to_parquet("/tmp/stab.parquet")
    print("final", flips(df, "arch")); print("raw  ", flips(df, "raw")); print(df.arch.value_counts().to_dict())
