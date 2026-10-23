"""Swing-Tool: Rechenkern (Board-Zeilen, Ziele, Listen, Hebel-/Kostenmodell). Nur vorhandene Snapshot-Daten."""
import json
import pandas as pd
from lib import D, load_v3, prices, plain
from common import CASES

SW = json.loads((D / "swing.json").read_text())
SETUP_DE = {"Basis-Retest": "Rücktest Ausbruch", "Support-Zone (v3)": "Unterstützungszone", "Trend-Pullback SMA100": "Rücksetzer 100-Tage-Linie",
            "Trend-Pullback SMA50": "Rücksetzer 50-Tage-Linie", "Trend-Pullback SMA200": "Rücksetzer 200-Tage-Linie"}

def tdays(asof, d):
    if not d: return None
    return len(pd.bdate_range(pd.Timestamp(asof) + pd.Timedelta(days=1), pd.Timestamp(d)))

def setup_of(c):
    m = c["plan"].get("method") or ""
    for k, v in SETUP_DE.items():
        if m.startswith(k): return v
    return plain(m).split(" (")[0] if m else "k. A."

_PC = None
def plan_of(sym):
    """Swing-Plan (eine Einstiegszone, Stopp, Ziele) nach swing_levels; Pool-weit aus data/swing_plans.json (Abendlauf), sonst live gerechnet."""
    global _PC
    if _PC is None:
        f = D / "swing_plans.json"; _PC = json.loads(f.read_text()) if f.exists() else {}
    if sym in _PC and _PC[sym].get("asof") == str(prices(sym).date.iloc[-1].date()): return _PC[sym]
    from swing_levels import analyse
    p = analyse(sym)["plan"]
    return None if p is None else {k: v for k, v in p.items() if k != "zone"} | {"touches": p["zone"]["touches"], "conf": p["zone"]["conf"], "asof": analyse(sym)["asof"]}

def levels(c):
    """Kompatibel zur alten Signatur: ([Einstieg], Unterkante, Oberkante, Einstieg)."""
    p = plan_of(c["symbol"])
    if p is None: raise KeyError("kein Swing-Plan")
    return [p["entry"]], p["lo"], p["hi"], p["entry"]

def cons_target(sym):
    return (load_v3()[1][sym].get("targets") or {}).get("median")

def targets(sym):
    """Ziel 1 = Unterkante des nächsten Widerstands (swing_levels), Ziel 2 = Widerstand danach, sonst Kursziel-Median der Analysten."""
    p = plan_of(sym); px = prices(sym); hi52 = float(px.tail(252).high.max())
    if p: return dict(t1=p["t1"], t1_src=p["t1src"], t2=p["t2"] or cons_target(sym), t2_src="nächster Widerstand" if p["t2"] else "Analysten-Median", hi52=hi52)
    return dict(t1=None, t1_src=None, t2=cons_target(sym), t2_src="Analysten-Median", hi52=hi52)

def _targets_old(sym):
    """Ziel 1 = nächster Widerstand (Pivot-Hoch über Kurs, sonst 52-Wochen-Hoch); Ziel 2 = Kursziel-Median der Analysten."""
    c = CASES[sym]; px = prices(sym); price = c["price"]
    # v4: nächster Widerstand über dem Ø Einstieg inkl. gleitender Durchschnitte (50/100/200 Tage, 30 Wochen), Swing-Hochs, 52-Wochen-Hoch
    try:
        _, _, _, ref = levels(c)
    except Exception:
        ref = price
    ref = max(ref, price)
    s_ = SW["stocks"].get(sym, {})
    cands = [(v, "nächstes Swing-Hoch") for v in c["structure"]["pivot_highs"]]
    cands += [(c.get("sma50"), "50-Tage-Linie"), (s_.get("sma100"), "100-Tage-Linie"), (c.get("sma200"), "200-Tage-Linie"), (c.get("sma30w"), "30-Wochen-Linie")]
    hi52 = float(px.tail(252).high.max()); cands.append((hi52, "52-Wochen-Hoch"))
    cands = sorted((v, n) for v, n in cands if v and v > ref * 1.005)
    t1, src = cands[0] if cands else (None, None)
    t2 = cons_target(sym)
    return dict(t1=t1, t1_src=src, t2=t2, hi52=hi52)

def plan_target(sym):
    """Ein Ziel für alle Chance/Risiko-Angaben: Ziel 1 (nächster Widerstand), sonst Ziel 2 (Analysten-Median)."""
    tg = targets(sym); return tg["t1"] or tg["t2"]

def crv(entry, stop, target):
    """Eine Formel überall (vor Kosten): (Ziel − Einstieg) ÷ (Einstieg − Stopp)."""
    return (target - entry) / (entry - stop) if target and entry > stop else None

def regime():
    """Marktlage in IBD-Art (eigene Näherung): Index über/unter 50-Tage-Linie + Verteilungstage der letzten 25 Sitzungen."""
    q = SW["idx"][1]; s = SW["idx"][0]; dd = max(q["dist_days"], s["dist_days"])
    if q["last"] < q["sma200"] or s["last"] < s["sma200"]: lab, tone = "Korrektur", "neg"
    elif q["last"] < q["sma50"] or dd >= 6: lab, tone = "Aufwärtstrend unter Druck", "warn"
    else: lab, tone = "Bestätigter Aufwärtstrend", "pos"
    return lab, tone, dd

def row(sym):
    c = CASES[sym]; s = SW["stocks"][sym]; lv, lo, hi, avg = levels(c); stop = plan_of(sym)["stop"]; _px = prices(sym); price = float(_px.close.iloc[-1])
    tgt = plan_target(sym); n = tdays(c["asof"], c["next_earnings"])
    prev = float(_px.close.iloc[-2])
    dist, dist_prev = price / hi - 1, prev / hi - 1
    # dist > 0: Kurs über der Zone
    near = lo <= price <= hi or 0 < dist <= 0.03
    lines = {"50-Tage-Linie": c["sma50"], "100-Tage-Linie": s["sma100"], "200-Tage-Linie": c["sma200"]}
    at_line = next((k for k, v in lines.items() if 0 <= price / v - 1 <= 0.02), None)
    pl = plan_of(sym)
    return dict(sym=sym, c=c, s=s, setup="Unterstützungszone" if pl["src"] == "Unterstützungszone" else "Rücksetzer 50-Tage-Linie", plan=pl, cat=c["category"], verdict=c["category"].split(":")[0].split(" (")[0].strip(),
                lv=lv, lo=lo, hi=hi, avg=avg, stop=stop, price=price, inzone=lo <= price <= hi, dist=dist, dist_prev=dist_prev,
                risk=(avg - stop) / avg, crv=crv(avg, stop, tgt), tgt=tgt, n=n,
                rank=s["rank"], rank_prev=s["rank_prev"], chg=price / prev - 1,
                near=near, breakout=price > s["hi20_prev"] >= prev, at_line=at_line, failed=price < stop,
                changed=abs(s["rank"] - s["rank_prev"]) >= 5 or (lo <= prev <= hi) != (lo <= price <= hi) or ((prev < stop) != (price < stop)))

PRESETS = [("alle", "Alle", lambda r: True), ("nahe", "Nahe Einstiegszone", lambda r: r["near"]), ("ausbruch", "Ausbruch heute", lambda r: r["breakout"]),
           ("linie", "Rücksetzer an Linie", lambda r: r["at_line"] is not None), ("gescheitert", "Gescheitert", lambda r: r["failed"]),
           ("geaendert", "Geändert seit Vortag", lambda r: r["changed"]), ("zahlen", "Zahlen in 7 Tagen", lambda r: r["n"] is not None and r["n"] <= 7)]

def board_rows():
    """Board-Zeilen für den ganzen Pool (einmal je Prozess gerechnet); Titel ohne Swing-Daten oder Plan fallen weg."""
    if not hasattr(board_rows, "_c"):
        out = []
        for s_ in CASES:
            try:
                r = row(s_); r["status"] = swing_status(r); out.append(r)
            except Exception:
                pass
        board_rows._c = out
    return board_rows._c

def turbo_model(entry, stop, target, ko, ratio, fin_pa, spread, days, fee, risk_amt, product):
    """Illustratives Modell. Turbo-Long: Preis ≈ (Basis − KO) × Bezugsverhältnis; Finanzierung ≈ KO × Satz × Tage/365 × BV.
    Rückgabe: Stückzahl, Kosten, G/V-Szenarien, CRV vor/nach Kosten."""
    if product == "Aktie":
        per_loss = entry - stop
        if per_loss <= 0: return None
        n = int(risk_amt / per_loss) if per_loss > 0 else 0
        cost = n * entry * spread + 2 * fee
        pnl = lambda S: n * (S - entry)
        price0 = entry; lev = 1.0; ko_dist = None; fin = 0.0
    else:
        if ko >= stop or ko >= entry: return dict(err="Die Knock-out-Schwelle muss unter dem Stopp liegen, sonst wird der Turbo vor dem Stopp ausgeknockt.")
        price0 = (entry - ko) * ratio; lev = entry / (entry - ko); ko_dist = ko / entry - 1
        fin_per = ko * fin_pa * days / 365 * ratio
        per_loss = (entry - stop) * ratio
        n = int(risk_amt / per_loss) if per_loss > 0 else 0
        fin = n * fin_per
        cost = n * price0 * spread + 2 * fee + fin
        pnl = lambda S: n * (max(S - ko, 0) * ratio - price0)
    g, l = pnl(target), -pnl(stop)
    sc = [("Ziel", target), ("Einstieg (unverändert)", entry), ("Stopp", stop)] + ([("Knock-out", ko)] if product != "Aktie" else [])
    return dict(n=n, price0=price0, lev=lev, ko_dist=ko_dist, invest=n * price0, cost=cost, fin=fin, gain=g, loss=l,
                rr_gross=g / l if l > 0 else None, rr_net=(g - cost) / (l + cost) if l + cost > 0 else None,
                scen=[(k, S, pnl(S) - cost) for k, S in sc], pnl=pnl)

# ---------------------------------------------------------------- v4.2: Swing-Status nur aus Swing-Kriterien
def trend_ok(c): return c.get("stage") == 2 and not c.get("stage_block") and "kein Stage 2" not in (c.get("stage_text") or "")
STATUS_ORDER = ["In Einstiegszone", "Nahe Einstiegszone", "Warten auf Rücksetzer", "Zahlen abwarten", "Trend nicht bestätigt", "Stopp unterschritten"]
STATUS_TONE = {"In Einstiegszone": "pos", "Nahe Einstiegszone": "pos", "Warten auf Rücksetzer": "neu", "Zahlen abwarten": "warn", "Trend nicht bestätigt": "warn", "Stopp unterschritten": "neg"}
def swing_status(r):
    if r["failed"]: return "Stopp unterschritten"
    if r["n"] is not None and r["n"] < 5: return "Zahlen abwarten"
    if not trend_ok(r["c"]): return "Trend nicht bestätigt"
    if r["inzone"]: return "In Einstiegszone"
    if 0 < r["dist"] <= 0.03: return "Nahe Einstiegszone"
    return "Warten auf Rücksetzer"
