"""Stop-Evidenz Teil 3 (v5.2): Ausstiege × Stopps, Regeln vorab fest. Setups wie stop_eval (Live-Logik, PIT), Horizont 126 Handelstage (6 Monate).
Ausstiege: T1 (live), T2 (zweiter Widerstand; ohne T2: Zeitende), TRP (nach Ziel 1 Stopp auf Einstieg, dann unter letztes höheres 2/2-Pivot-Tief),
TRA (nach Ziel 1 Stopp auf Einstieg, dann höchstes Hoch − 2 ATR), H21/H63/H126 (Mindesthaltedauer: nur Stopp oder Schluss am Tag 21/63/126).
Stopps: R0 live, K2 (Zone − 2 ATR), Q80 (Testquantil je Zelle). Stopp intraday (Tief), Kurslücke zum Eröffnungskurs. Turbo: KO = Anfangsstopp − 1 ATR, 5 % p. a. auf (L − 1).
Test 2016–2019, Validierung 2020–2021, ab 2023 versiegelt (Setups enden 2022-12-31 inkl. Pfad)."""
import pickle, numpy as np, pandas as pd, json
S = pickle.load(open("./studies/stop_setups_t2.pkl", "rb")); P = json.load(open("./studies/stop_params.json"))
q = P["atr_terciles"]; QT = P["QT"]["80"]; FIN = 0.05
def run(s, stop, mode, H=None):
    lo, hi, op, cl, e, A, t1, t2 = s["lo"], s["hi"], s["op"], s["cl"], s["entry"], s["atr"], s["t1"], s["t2"]
    n = len(lo) if H is None else min(H, len(lo)); st = stop; armed = False; piv = []; mh = -1
    for k in range(n):
        if op[k] <= st: return op[k] / e - 1, k + 1, "stop" if not armed else "trail"
        if lo[k] <= st: return st / e - 1, k + 1, "stop" if not armed else "trail"
        if mode == "T1" and hi[k] >= t1: return max(op[k], t1) / e - 1, k + 1, "ziel"
        if mode == "T2" and t2 == t2 and hi[k] >= t2: return max(op[k], t2) / e - 1, k + 1, "ziel"
        if mode in ("TRP", "TRA"):
            if not armed and hi[k] >= t1: armed = True; st = max(st, e)
            mh = max(mh, hi[k])
            if armed:   # Nachziehen erst mit Wissen bis Tagesende k, gilt ab k+1
                if mode == "TRA": st = max(st, mh - 2 * A)
                elif k >= 4:
                    j = k - 2
                    if lo[j] == lo[j - 2:j + 3].min():
                        if not piv or lo[j] > piv[-1]: st = max(st, lo[j])
                        piv.append(lo[j])
    return cl[n - 1] / e - 1, n, "zeit"
rows = []
import sys as _s
for i, s in enumerate([] if '--agg' in _s.argv else S):
    e, A = s["entry"], s["atr"]
    if not (s["stop0"] < e < s["t1"]) or s["date"].year < 2016 or s["date"] > pd.Timestamp("2022-12-31"): continue
    per = "test" if s["date"].year <= 2019 else "val" if s["date"].year <= 2021 else None
    if per is None: continue
    cell = ("ruhig" if s["atr_pct"] <= q[0] else "mittel" if s["atr_pct"] <= q[1] else "volatil") + " / " + ("über SMA200" if s["d200"] > 0 else "unter SMA200")
    stops = {"R0": s["stop0"], "K2": s["zl"] - 2 * A, "Q80": min(e - QT[cell] * A, s["zl"]) if cell in QT else s["zl"] - 2 * A}
    for sn, st in stops.items():
        if not st < e: continue
        ko = st - A; L = e / (e - ko); rp = 1 - st / e
        for mode, H in (("T1", None), ("T2", None), ("TRP", None), ("TRA", None), ("H21", 21), ("H63", 63), ("H126", 126)):
            ret, d, how = run(s, st, mode[:1] if mode.startswith("H") else mode, H)
            gko = e * (1 + ret) <= ko
            tr = max(-1.0, -1.0 if gko else L * ret - FIN * (L - 1) * d / 365)
            rows.append(dict(i=i, per=per, cell=cell, stop=sn, exit=mode, ret=ret, R=ret / rp, days=d, how=how, L=L, turbo=tr, has_t2=s["t2"] == s["t2"]))
import sys
if "--agg" in sys.argv: R = pd.read_parquet("./studies/exit_results.parquet")
else: R = pd.DataFrame(rows); R.to_parquet("./studies/exit_results.parquet")
def agg(g): return pd.Series(dict(n=len(g), win=(g.ret > 0).mean(), ER=g.R.clip(-3, 5).mean(), ER_raw=g.R.mean(), stop_rate=(g.how == "stop").mean(), days_med=g.days.median(),
                                  days_mean=g.days.mean(), turbo=g.turbo.mean(), turbo_21d=(g.turbo / g.days).mean() * 21, ret=g.ret.mean()))
T = R.groupby(["per", "stop", "exit"]).apply(agg).reset_index(); T.to_csv("./studies/exit_table.csv", index=False)
C = R.groupby(["per", "cell", "stop", "exit"]).apply(agg).reset_index(); C.to_csv("./studies/exit_table_cells.csv", index=False)
pd.set_option("display.width", 250); print(T.round(3).to_string())
