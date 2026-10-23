"""Stop-Evidenz Schritt 1: historische Swing-Setups mit unveränderter Live-Logik (swing_levels._analyse), PIT-Universum, monatlich."""
import sys, numpy as np, pandas as pd, pickle
from pathlib import Path
from multiprocessing import Pool
sys.path.insert(0, __import__("os").environ.get("APP_ROOT", "."))
import swing_levels as SL
DS = Path(__import__("os").environ.get("MARKET_STORE", "data_store") + ""); SEAL = pd.Timestamp("2022-12-31"); H = 126; FILLWIN = 21
OUT = Path("./studies/stop_setups_t2.pkl")
_cur = {}
SL.prices = lambda sym: _cur["px"]  # live code reads prices(sym); we feed the cut-off frame
an = SL._analyse.__wrapped__

def load(t):
    for d in ("prices", "prices_hist"):
        p = DS / d / f"{t}.parquet"
        if p.exists():
            x = pd.read_parquet(p); x["date"] = pd.to_datetime(x["date"]); return x[x.date <= SEAL].sort_values("date").reset_index(drop=True)
    return None

SPY = load("SPY").set_index("date").close.pct_change()

def work(args):
    t, ivs = args
    px = load(t)
    if px is None or len(px) < 300: return []
    px = px[(px.close > 0)].reset_index(drop=True)
    r = px.set_index("date").close.pct_change()
    sma200 = px.close.rolling(200).mean(); sma50 = px.close.rolling(50).mean()
    me = px.groupby(px.date.dt.to_period("M")).tail(1).index
    out = []
    for i in me:
        d = px.date[i]
        if i < 252 or d.year < 2016 or d.year > 2021 or i + FILLWIN + 5 >= len(px): continue
        if not any(s <= d <= e for s, e in ivs): continue
        _cur["px"] = px.iloc[:i + 1].copy()
        try: a = an(t, str(d))
        except Exception: continue
        p = a["plan"]
        if not p: continue
        e, A = p["entry"], a["atr"]
        # Fill: inside -> close d; sonst Limit Oberkante, gültig 21 Tage
        if p["inside"]: f = i
        else:
            f = next((j for j in range(i + 1, min(i + 1 + FILLWIN, len(px))) if px.low[j] <= e), None)
            if f is None: continue
            e = min(e, px.open[f])
        fw = px.iloc[f + 1 if p["inside"] else f: f + 1 + H] if not p["inside"] else px.iloc[f + 1:f + 1 + H]
        if len(fw) < 21: continue
        z = p["zone"]; zl = min(z["lo"], z["low"])
        lower = [s["lo"] for s in a["sup"] if s["hi"] < z["lo"]]
        rr = r.loc[:d].tail(252); sp = SPY.reindex(rr.index)
        beta = float(rr.cov(sp) / sp.var()) if sp.notna().sum() > 200 else np.nan
        s2 = sma200[i]; s2p = sma200[i - 21]
        out.append(dict(ticker=t, date=d, entry=e, atr=A, atr_pct=A / a["price"], price=a["price"], zl=zl, stop0=p["stop"], ko0=p["ko"], t1=p["t1"], t2=p["t2"] if p["t2"] else np.nan,
                        t1src=p["t1src"], src=p["src"], touches=z["touches"], score=z.get("score", 1), lower_lo=lower[0] if lower else np.nan,
                        beta=beta, d200=a["price"] / s2 - 1, sma200_up=bool(s2 > s2p), above50=bool(a["price"] > sma50[i]), sma50_gt200=bool(sma50[i] > s2),
                        fill_lag=f - i, lo=fw.low.values.astype("f4"), hi=fw.high.values.astype("f4"), op=fw.open.values.astype("f4"), cl=fw.close.values.astype("f4")))
    return out

if __name__ == "__main__":
    iv = pd.read_parquet(DS / "universe/intervals.parquet")
    jobs = [(t, list(zip(g.start, g.end))) for t, g in iv.groupby("ticker")]
    print(len(jobs), "Ticker", flush=True)
    res = []
    with Pool(8) as P:
        for k, o in enumerate(P.imap_unordered(work, jobs, chunksize=4)):
            res += o
            if k % 100 == 0: print(k, len(res), flush=True)
    pickle.dump(res, open(OUT, "wb")); print("fertig", len(res))
