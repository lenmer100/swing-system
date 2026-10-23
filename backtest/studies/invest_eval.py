"""Stop-Evidenz Schritt 4: Investment-Tranchen/Stop (invest_plan-Regeln) PIT auf dem v4-Backtest-Panel (nur reliable).
Pessimistisch/Kaufzone fehlen im Panel -> archetypische Median-Verhältnisse pess/base und buy_zone/base aus dem v5.1-Export (Strukturannahme, kein Kursbezug)."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0, __import__("os").environ.get("APP_ROOT", "."))
from valuation import invest_plan as IP
DS = __import__("os").environ.get("MARKET_STORE", "data_store") + ""; SEAL = pd.Timestamp("2022-12-31")
X = json.load(open("./data/valuation_v4.json"))["stocks"]
rat = {}
for s in X.values():
    if s.get("status") != "ok" or s.get("display_mode") != "value": continue
    b = s["range"]["base"]; k = s["archetype"]["key"]
    rat.setdefault(k, []).append((s["range"]["pessimistic"] / b, (s.get("buy_zone_below") or np.nan) / b))
RAT = {k: (np.nanmedian([a for a, _ in v]), np.nanmedian([c for _, c in v])) for k, v in rat.items()}
P = pd.read_parquet("./data/valuation_v4_backtest.parquet")
P = P[(P.reliable == True) & (P.date >= "2016-01-01") & (P.fv4 > 0)]
cache = {}
def px(t):
    if t not in cache:
        try: d = pd.read_parquet(f"{DS}/prices/{t}.parquet"); d["date"] = pd.to_datetime(d.date); cache[t] = d[d.date <= SEAL]
        except Exception: cache[t] = None
    return cache[t]
out = []
for r in P.itertuples():
    d = px(r.ticker)
    if d is None or r.arch not in RAT: continue
    past = d[d.date <= r.date]
    if len(past) < 250: continue
    price = float(past.close.iloc[-1]); fv = r.fv4 * price; pr, br = RAT[r.arch]
    rec = dict(status="ok", display_mode="value", price=price, range=dict(base=fv, pessimistic=fv * pr), buy_zone_below=fv * br if np.isfinite(br) else None, ticker=r.ticker)
    IP.PX = __import__("pathlib").Path(f"{DS}/prices")
    pl = IP.plan(rec, r.date)
    if not pl or not pl["available"]: continue
    tr = [t["v"] for t in pl["tranches"]]
    fut = d[d.date > r.date]
    for H, n in (("1J", 252), ("2J", 504)):
        f = fut.head(n)
        if len(f) < n * .9: continue
        # Einstieg T1 erst, wenn Kurs T1 erreicht (T1 = min(Kurs, FV))
        hitT1 = f.index[f.low <= tr[0]]
        if price > tr[0] and not len(hitT1): out.append(dict(t=r.ticker, date=r.date, H=H, arch=r.arch, filled=False)); continue
        g = f if price <= tr[0] else f.loc[hitT1[0]:]
        mn = g.low.min()
        out.append(dict(t=r.ticker, date=r.date, H=H, arch=r.arch, filled=True, n_tr=len(tr), T2=len(tr) > 1 and mn <= tr[1], T3=len(tr) > 2 and mn <= tr[2],
                        stop=mn <= pl["stop"], mdd=1 - mn / tr[0], stop_dist=1 - pl["stop"] / tr[0], atr_pct=float(((past.high - past.low).tail(14).mean()) / price),
                        end_ret=float(f.close.iloc[-1]) / tr[0] - 1))
O = pd.DataFrame(out); O.to_parquet("./studies/invest_results.parquet"); print(len(O), O.filled.mean(), json.dumps({k: [round(a, 3), round(b, 3)] for k, (a, b) in RAT.items()}))
