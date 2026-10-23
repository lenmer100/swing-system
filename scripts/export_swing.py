"""Swing-Zusatzdaten aus dem market data store-Kursbestand (nur Kurse/Volumen, keine Fremdinhalte): Pool-Rang (SCTR-Art), Marktbreite,
Verteilungstage, RS-Linie. Stichtag = Demo-Stand (meta.json asof)."""
import json, glob, os
import numpy as np, pandas as pd
ROOT = __import__("os").environ.get("APP_ROOT", "."); PX = __import__("os").environ.get("MARKET_STORE", "data_store") + "/prices"
asof = pd.Timestamp(json.load(open(f"{ROOT}/data/meta.json"))["asof"])
pool = set(pd.read_csv(__import__("os").environ.get("UNIVERSE_CSV", "universe.csv")).symbol)
SY = ["META", "MELI", "GOOGL", "AMZN", "NVDA"]
def load(s):
    d = pd.read_parquet(f"{PX}/{s}.parquet"); d["date"] = pd.to_datetime(d["date"]); return d[d.date <= asof].reset_index(drop=True)
def rsi(c, n=14):
    d = c.diff(); u = d.clip(lower=0).ewm(alpha=1 / n).mean(); v = (-d.clip(upper=0)).ewm(alpha=1 / n).mean(); return 100 - 100 / (1 + u / v)
def sctr_raw(c):
    if len(c) < 260: return None
    e200, e50 = c.ewm(span=200).mean(), c.ewm(span=50).mean()
    ppo = (c.ewm(span=12).mean() - c.ewm(span=26).mean()) / c.ewm(span=26).mean() * 100
    hist = ppo - ppo.ewm(span=9).mean()
    return (.3 * (c / e200 - 1) * 100 + .3 * (c / c.shift(125) - 1) * 100 + .15 * (c / e50 - 1) * 100 + .15 * (c / c.shift(20) - 1) * 100
            + .05 * np.clip((hist - hist.shift(3)) * 50 + 50, 0, 100) / 100 * 10 + .05 * rsi(c) / 10)
raw = {}; ab50 = ab200 = n = 0
for f in glob.glob(f"{PX}/*.parquet"):
    s = os.path.basename(f)[:-8]
    if s not in pool: continue
    d = load(s)
    if len(d) < 260 or d.date.iloc[-1] < asof - pd.Timedelta(days=4): continue
    c = d.close; r = sctr_raw(c); raw[s] = (r.iloc[-1], r.iloc[-2])
    n += 1; ab50 += c.iloc[-1] > c.rolling(50).mean().iloc[-1]; ab200 += c.iloc[-1] > c.rolling(200).mean().iloc[-1]
t0 = pd.Series({k: v[0] for k, v in raw.items()}).rank(pct=True); t1 = pd.Series({k: v[1] for k, v in raw.items()}).rank(pct=True)
spy = load("SPY"); qqq = load("QQQ")
def dist_days(d):
    x = d.tail(26).reset_index(drop=True); return int(sum((x.close[i] / x.close[i - 1] - 1 <= -0.002) and x.volume[i] > x.volume[i - 1] for i in range(1, len(x))))
def idx(d, name):
    c = d.close; return dict(name=name, last=float(c.iloc[-1]), sma50=float(c.rolling(50).mean().iloc[-1]), sma200=float(c.rolling(200).mean().iloc[-1]),
                             dist_days=dist_days(d), chg5=float(c.iloc[-1] / c.iloc[-6] - 1))
out = dict(asof=str(asof.date()), pool_n=n, breadth50=ab50 / n, breadth200=ab200 / n, idx=[idx(spy, "S&P 500 (SPY)"), idx(qqq, "Nasdaq 100 (QQQ)")], stocks={})
sp = spy.set_index("date").close
for s in SY:
    d = load(s); c = d.set_index("date").close; rs = (c / sp.reindex(c.index).ffill()).dropna()
    rsw = rs.resample("W-FRI").last().tail(104)
    v = d.tail(50); up = v[v.close.diff() > 0].volume.sum(); dn = v[v.close.diff() < 0].volume.sum()
    out["stocks"][s] = dict(rank=int(min(99, t0[s] * 100)), rank_prev=int(min(99, t1[s] * 100)),
                            rs_w=[[str(k.date()), float(x)] for k, x in rsw.items()], rs_high52=bool(rs.iloc[-1] >= rs.tail(252).max() * 0.995),
                            rs_chg3m=float(rs.iloc[-1] / rs.iloc[-64] - 1), updown_vol=float(up / dn) if dn else None,
                            vol_rel=float(d.volume.iloc[-1] / d.volume.tail(51).head(50).mean()), close_prev=float(d.close.iloc[-2]),
                            hi20_prev=float(d.high.iloc[-21:-1].max()), sma100=float(d.close.rolling(100).mean().iloc[-1]))
rk = pd.read_csv(__import__("os").environ.get("UNIVERSE_CSV", "universe.csv")).set_index("symbol")
for s_ in SY:
    r = rk.loc[s_]; out["stocks"][s_]["turbo"] = dict(ko=float(r.turbo_ko), lev=float(r.turbo_lev), rr_net=float(r.turbo_rr), ok=bool(r.turbo_ok == True), why=str(r.turbo_why))
tb = pd.read_csv(__import__("os").environ.get("MARKET_STORE", "data_store") + "/bt/dtb3.csv"); out["tbill3m"] = float(pd.to_numeric(tb.iloc[:, 1], errors="coerce").dropna().iloc[-1]) / 100
json.dump(out, open(f"{ROOT}/data/swing.json", "w"), indent=1)
print(n, out["breadth50"], out["breadth200"], {s: (v["rank"], v["rank_prev"], v["rs_high52"]) for s, v in out["stocks"].items()}, out["idx"])

# ---------------------------------------------------------------- Phase 2: Zusatzdaten
out = json.load(open(f"{ROOT}/data/swing.json"))
SEAL = pd.Timestamp("2022-12-31")      # Statistiken nur bis 2022; 2023+ bleibt versiegelt
# Breite-Verlauf (60 Sitzungen)
cl = {}
for s in pool:
    f = f"{PX}/{s}.parquet"
    if os.path.exists(f):
        d = load(s)
        if len(d) >= 260 and d.date.iloc[-1] >= asof - pd.Timedelta(days=4): cl[s] = d.set_index("date").close
C = pd.DataFrame(cl).loc[:asof].tail(320)
a50 = (C > C.rolling(50).mean()).sum(1) / C.notna().sum(1); a200 = (C > C.rolling(200).mean()).sum(1) / C.notna().sum(1)
out["breadth_hist"] = [[str(k.date()), float(a50[k]), float(a200[k])] for k in C.index[-60:]]
# Sektor-Rotation (RRG-Näherung, wöchentlich gegen SPY)
SEC = {"XLK": "Technologie", "XLC": "Kommunikation", "XLY": "Zyklischer Konsum", "XLP": "Basiskonsum", "XLV": "Gesundheit", "XLF": "Finanzen",
       "XLI": "Industrie", "XLE": "Energie", "XLB": "Grundstoffe", "XLU": "Versorger", "XLRE": "Immobilien"}
spw = load("SPY").set_index("date").close.resample("W-FRI").last()
rrg = {}
for e, nm in SEC.items():
    w = load(e).set_index("date").close.resample("W-FRI").last(); rs = (w / spw).dropna()
    ratio = 100 + (rs / rs.rolling(10).mean() - 1) * 100 * 10 / 10
    ratio = 100 * rs / rs.rolling(10).mean(); mom = 100 * ratio / ratio.shift(4)
    rrg[e] = dict(name=nm, trail=[[str(k.date()), float(ratio[k]), float(mom[k])] for k in ratio.index[-12:]],
                  perf1m=float(w.iloc[-1] / w.iloc[-5] - 1), perf3m=float(w.iloc[-1] / w.iloc[-14] - 1))
out["rrg"] = rrg
# Pool-Perzentile Q/B/M (X8) und Pool-Listen (W17)
rk = pd.read_csv(__import__("os").environ.get("UNIVERSE_CSV", "universe.csv"))
rk["val_pct"] = rk.base_cagr.rank(pct=True) * 100; rk["q_pct"] = rk.v3_q_pct
mom = pd.Series({k: v for k, v in t0.items()}) * 100
earn7 = rk[(rk.days_to_earn >= 0) & (rk.days_to_earn <= 7)].sort_values("days_to_earn")
out["earn7"] = [dict(sym=r.symbol, name=r["name"], n=int(r.days_to_earn), cat=r.category) for _, r in earn7.iterrows()]
for s_ in SY:
    r = rk[rk.symbol == s_].iloc[0]
    cs_ = json.load(open(f"{ROOT}/data/cases.json"))[s_]   # Q und B aus demselben Fall wie alle anderen Anzeigen
    out["stocks"][s_]["pct"] = dict(q=float(cs_["q_pct"]), v=float((rk.base_cagr.dropna() < cs_["scenarios"]["basis"]["cagr"]).mean() * 100), m=float(mom.get(s_, float("nan"))))
    # Zahlen-Reaktion (X2): Folgetag-Reaktion (Schluss Vortag -> Schluss nach Bericht), nur bis 2022
    e = pd.read_parquet(f__import__("os").environ.get("MARKET_STORE", "data_store") + "/derived/yf_earnings/{s_}.parquet"); e["date"] = pd.to_datetime(e.date)
    px = pd.read_parquet(f"{ROOT}/data/pxl_{s_}.parquet"); px["date"] = pd.to_datetime(px.date); px = px.set_index("date").close
    reac = []
    for _, x in e.sort_values("date").iterrows():
        d0 = x.date.normalize()
        if d0 > pd.Timestamp("2026-07-29") or d0 < pd.Timestamp("2020-07-01"): continue   # alle berichteten Quartale bis zum letzten Termin vor dem Datenstand
        aft = d0 + pd.Timedelta(days=1) if x.date.hour >= 16 else d0
        pre = px[:aft - pd.Timedelta(days=1)]; post = px[aft:]
        if len(pre) and len(post): reac.append([str(d0.date()), float(post.iloc[0] / pre.iloc[-1] - 1), None if pd.isna(x["Surprise(%)"]) else float(x["Surprise(%)"]),
            None if pd.isna(x.get("EPS Estimate")) else float(x["EPS Estimate"]), None if pd.isna(x.get("Reported EPS")) else float(x["Reported EPS"])])
    out["stocks"][s_]["reactions"] = reac
    # Saisonalität (X9): Monatsrenditen bis 2022
    m = px[:SEAL].resample("ME").last().pct_change().dropna()
    out["stocks"][s_]["season"] = [[int(mm), float(g.mean()), float((g > 0).mean()), int(len(g))] for mm, g in m.groupby(m.index.month)]
    out["stocks"][s_]["season_years"] = [int(m.index.year.min()), int(m.index.year.max())]
# Korrelation (X17), 1 Jahr Tagesrenditen bis Stichtag
R = pd.DataFrame({s_: load(s_).set_index("date").close for s_ in SY}).tail(253).pct_change().dropna()
out["corr"] = R.corr().round(3).values.tolist()
# Erwartete Bewegung (X1) aus Optionskette, Abruf heute (nicht point-in-time)
try:
    import yfinance as yf
    cases = json.load(open(f"{ROOT}/data/cases.json"))
    out["implied"] = {}
    for s_ in SY:
        t = yf.Ticker(s_); ed = cases[s_]["next_earnings"]; exp = next((x for x in t.options if x > ed), None)
        if not exp: continue
        ch = t.option_chain(exp); spot = float(t.history(period="1d").Close.iloc[-1])
        k = min(ch.calls.strike, key=lambda z: abs(z - spot))
        def mid(df):
            r = df[df.strike == k].iloc[0]; m = (r.bid + r.ask) / 2
            return float(m if r.bid > 0 and r.ask > 0 else r.lastPrice)
        out["implied"][s_] = dict(move=(mid(ch.calls) + mid(ch.puts)) / spot, expiry=exp, strike=float(k), spot=spot, fetched=str(pd.Timestamp.now().date()), basis="Geld/Brief-Mitte" if float(ch.calls[ch.calls.strike == k].bid.iloc[0]) > 0 else "letzter Handelspreis")
except Exception as ex:
    print("implied move skipped:", ex)
json.dump(out, open(f"{ROOT}/data/swing.json", "w"), indent=1)
print("phase2", len(out["earn7"]), out.get("implied"), {s: len(v["reactions"]) for s, v in out["stocks"].items()})
