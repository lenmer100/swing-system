"""Stop-Evidenz Schritt 2+3: MAE, Trefferquoten, Expectancy je Gruppe; Regelfamilien a priori, Quantile nur aus Test, Prüfung auf Validierung."""
import pickle, numpy as np, pandas as pd, json
from pathlib import Path
S = pickle.load(open("./studies/stop_setups.pkl", "rb"))
FIN = 0.05
def sim(s, stop, tgt):
    lo, hi, op, cl, e = s["lo"], s["hi"], s["op"], s["cl"], s["entry"]
    for k in range(len(lo)):
        if op[k] <= stop: return op[k] / e - 1, k + 1, "stop"
        if lo[k] <= stop: return stop / e - 1, k + 1, "stop"
        if hi[k] >= tgt: return max(op[k], tgt) / e - 1, k + 1, "t1"
    return cl[-1] / e - 1, len(lo), "zeit"
def turbo(s, stop, ko, ret, days, how):
    e = s["entry"]; L = e / (e - ko)
    gap_ko = how == "stop" and e * (1 + ret) <= ko
    r = -1.0 if gap_ko else L * ret - FIN * (L - 1) * days / 365
    return max(r, -1.0), L
rows = []
for s in S:
    e, A = s["entry"], s["atr"]
    if not (s["stop0"] < e < s["t1"]): continue
    hit = np.where(s["hi"] >= s["t1"])[0]; kt = hit[0] if len(hit) else None
    lo_pre = s["lo"][:kt + 1] if kt is not None else s["lo"]
    d = dict(ticker=s["ticker"], date=s["date"], atr_pct=s["atr_pct"], beta=s["beta"], d200=s["d200"], up200=s["sma200_up"], s50=s["sma50_gt200"],
             src=s["src"], touches=s["touches"], e=e, A=A, success=kt is not None, t1_days=(kt + 1) if kt is not None else np.nan,
             mae_pre_atr=(e - lo_pre.min()) / A, mae_pre_pct=1 - lo_pre.min() / e, zl=s["zl"], lower=s["lower_lo"], stop0=s["stop0"], ko0=s["ko0"], t1=s["t1"])
    for m, n in ((1, 21), (3, 63), (6, 126)): d[f"mae{m}m_atr"] = (e - s["lo"][:n].min()) / A; d[f"mae{m}m_pct"] = 1 - s["lo"][:n].min() / e
    d["_s"] = s; rows.append(d)
df = pd.DataFrame(rows); df["per"] = np.where(df.date.dt.year <= 2019, "test", "val")
te = df.per == "test"
q = df.loc[te, "atr_pct"].quantile([1/3, 2/3]).values; df["vol"] = pd.cut(df.atr_pct, [-1, q[0], q[1], 9], labels=["ruhig", "mittel", "volatil"])
qb = df.loc[te, "beta"].quantile([1/3, 2/3]).values; df["beta_t"] = pd.cut(df.beta, [-9, qb[0], qb[1], 99], labels=["Beta niedrig", "Beta mittel", "Beta hoch"])
df["sma200"] = np.where(df.d200 > 0, "über SMA200", "unter SMA200")
df["d200_b"] = pd.cut(df.d200, [-9, 0, .1, .25, 99], labels=["<0 %", "0–10 %", "10–25 %", ">25 %"])
df["trend"] = np.where(df.s50 & df.up200, "Aufwärts", np.where(~df.s50 & ~df.up200, "Abwärts", "Übergang"))
df["zone"] = np.where(df.src != "Unterstützungszone", "50-Tage-Linie", np.where(df.touches >= 3, "Zone 3+ Berührungen", "Zone 2 Berührungen"))
df["cell"] = df.vol.astype(str) + " / " + df.sma200
# Q-Regeln: Quantile der MAE (vor Ziel 1, in ATR ab Einstieg) der erfolgreichen Test-Setups je Zelle
succ = df[te & df.success]
QT = {p: succ.groupby("cell").mae_pre_atr.quantile(p / 100).to_dict() for p in (80, 90)}
def stops(r):
    e, A, zl = r.e, r.A, r.zl
    o = {"R0 live": r.stop0}
    for k in (1, 1.5, 2, 3): o[f"K{k}"] = zl - k * A
    for p in (80, 90): o[f"Q{p}"] = min(e - QT[p][r.cell] * A - 0.0, zl - 0.0 * A) if r.cell in QT[p] else zl - 2 * A
    o["S struktur"] = (r.lower - .5 * A) if np.isfinite(r.lower) and r.lower < zl else zl - 2 * A
    return o
res = []
for r in df.itertuples():
    for name, st in stops(r).items():
        if not st < r.e: continue
        ko = st - r.A
        ret, days, how = sim(r._s if False else df.at[r.Index, "_s"], st, r.t1)
        ko_hit = (r._asdict() and None)
        s = df.at[r.Index, "_s"]; hit = np.where(s["hi"] >= r.t1)[0]; kt = hit[0] if len(hit) else len(s["lo"]) - 1
        ko_hit = bool((s["lo"][:kt + 1] <= ko).any() and (np.where(s["lo"] <= ko)[0][0] <= kt))
        stop_hit_any = bool((s["lo"] <= st).any())
        tr, L = turbo(s, st, ko, ret, days, how)
        res.append(dict(i=r.Index, rule=name, stop_atr=(r.e - st) / r.A, risk_pct=1 - st / r.e, ret=ret, R=ret / (1 - st / r.e), days=days, how=how,
                        ko_hit=ko_hit, stop_hit=how == "stop", L=L, turbo=tr))
R = pd.DataFrame(res).join(df.drop(columns="_s"), on="i")
R.to_parquet("./studies/stop_results.parquet"); df.drop(columns="_s").to_parquet("./studies/stop_setups_flat.parquet")
json.dump({"atr_terciles": list(q), "beta_terciles": list(qb), "QT": {k: {c: float(v) for c, v in d.items()} for k, d in QT.items()}}, open("./studies/stop_params.json", "w"), indent=1)
print(len(df), len(R))
