"""v5 Investment plan (LM 22.10.): tranches, add-on levels, stop and ordered stress scenarios, derived from the valuation
and long-term supports. Only for display_mode == 'value' (belastbar, range within the method bounds).
Rules (fixed a priori):
- supports: 40-week and 200-week average of weekly closes, monthly pivot lows of the last 6 years (below price).
- T1 (40 %): price if price <= fair value, else the fair value (no buying above fair value).
- T2 (30 %): buy zone = fair value x (1 - margin of safety); snapped to a long-term support within +-5 % if one exists.
- T3 (30 %): pessimistic value; snapped to a support within +-5 %. Levels must be >= 5 % apart, else dropped (weights renormalised).
- stop (thesis break, v5.2): base = min(pessimistic value, lowest tranche); stop = base x (1 - max(8 %, p80 one-year drawdown of the
  volatility group, test period 2016-19)): ruhig 32 %, mittel 34 %, volatil 37 %. Group = 14-day mean (high - low) / price, cut-offs 1.533 % / 2.044 %.
- stress scenarios, ascending, only values below today's price and > 0: pessimistic value, largest historical drawdown
  from today's price, stop level; main stress value = pessimistic value."""
import pandas as pd
from pathlib import Path
PX = Path(__import__("os").environ.get("MARKET_STORE", "data_store") + "/prices")
MON = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
SNAP = 0.05; GAP = 0.05; STOP = 0.08; VCUT = (0.01533, 0.02044); DD80 = {"ruhig": 0.32, "mittel": 0.34, "volatil": 0.37}; W = (0.4, 0.3, 0.3)


def supports(t, asof, price):
    p = PX / f"{t}.parquet"
    if not p.exists():
        return [], None, None
    px = pd.read_parquet(p); px = px[px.date <= pd.Timestamp(asof)]
    if len(px) < 60:
        return [], None, None
    w = px.set_index("date").close.resample("W-FRI").last()
    m = px.set_index("date").resample("ME").agg({"low": "min"})
    out = []
    if len(w) >= 40 and w.rolling(40).mean().iloc[-1] < price:
        out.append(dict(name="40-Wochen-Linie", v=float(w.rolling(40).mean().iloc[-1])))
    if len(w) >= 200 and w.rolling(200).mean().iloc[-1] < price:
        out.append(dict(name="200-Wochen-Linie", v=float(w.rolling(200).mean().iloc[-1])))
    lows = m.low.tail(72).values; mi = m.tail(72).index
    for i in range(2, len(lows) - 2):
        if lows[i] == min(lows[i - 2:i + 3]) and lows[i] < price:
            out.append(dict(name=f"Monatstief {MON[mi[i].month - 1]} {mi[i].year}", v=float(lows[i])))
    run = px.close.cummax(); dd = float((px.close / run - 1).min())
    vol = float(((px.high - px.low).tail(14).mean()) / px.close.iloc[-1])
    return sorted(out, key=lambda x: -x["v"]), dd, vol


def plan(r, asof):
    if r.get("status") != "ok":
        return None
    if r.get("display_mode") != "value":
        return dict(available=False, reason="Bewertung nicht belastbar oder Kapazitätsaufbau (nur implizierte Rendite): kein Tranchenplan, keine Kaufniveaus, kein Stresswert aus der Bewertung")
    price = r["price"]; rg = r["range"]; fv = rg["base"]; pess = rg["pessimistic"]; bz = r.get("buy_zone_below")
    sup, mdd, vol = supports(r["ticker"], asof, price)
    def snap(v, why):
        s = min(sup, key=lambda x: abs(x["v"] / v - 1)) if sup else None
        return (s["v"], f"{why}, an langfristiger Unterstützung ({s['name']})") if s and abs(s["v"] / v - 1) <= SNAP else (v, why)
    lv = [(min(price, fv), "aktueller Kurs (unter fairem Wert)" if price <= fv else "fairer Wert (Kurs darüber: kein Kauf darüber)")]
    if bz:
        lv.append(snap(bz, f"Kaufzone: fairer Wert − {1 - bz / fv:.0%} Sicherheitsmarge"))
    lv.append(snap(pess, "pessimistisches Szenario der Bewertung"))
    tr = []
    for v, why in lv:
        if v > 0 and (not tr or v <= tr[-1]["v"] * (1 - GAP)):
            tr.append(dict(v=v, why=why))
    ws = W[:len(tr)]; s_ = sum(ws)
    for i, (t, w) in enumerate(zip(tr, ws), 1):
        t.update(n=i, w=w / s_)
    grp = None if vol is None else "ruhig" if vol <= VCUT[0] else "mittel" if vol <= VCUT[1] else "volatil"
    sd = max(STOP, DD80[grp]) if grp else STOP; base = min(pess, tr[-1]["v"])
    stop = (1 - sd) * base
    stop_why = (f"{sd:.0%} unter min(pessimistischer Wert, letzte Tranche) = {base:,.2f}. Abstand = 80-%-Quantil des größten Ein-Jahres-Rückgangs nach Kauf in der Volatilitätsgruppe "
                f"„{grp}“ (Tagesspanne {vol:.2%} vom Kurs), gemessen 2016–2019; mindestens 8 %. Der alte Abstand von 8 % wurde in 40–58 % der Fälle ausgelöst, dieser in der Validierung 2020–2021 in rund 6 % (1 Jahr)."
                ).replace(",", "X").replace(".", ",").replace("X", ".") if grp else f"{STOP:.0%} unter min(pessimistischer Wert, letzte Tranche)"

    stress = [dict(name="Pessimistisches Szenario", v=pess, why="fairer Wert im pessimistischen Szenario der Bewertung")]
    if mdd is not None:
        stress.append(dict(name="Größter historischer Rückgang", v=price * (1 + mdd), why=f"heutiger Kurs mit dem größten Rückgang der Kurshistorie ({mdd:.0%})"))
    stress.append(dict(name="Stopp (These gebrochen)", v=stop, why=stop_why))
    stress = sorted([s for s in stress if 0 < s["v"] < price], key=lambda x: -x["v"])
    return dict(available=True, tranches=tr, stop=stop, stop_pct=sd, stop_group=grp, stop_why=stop_why, supports=sup[:6], stress=stress, stress_main=pess if pess < price else (stress[0]["v"] if stress else None),
                rules=__doc__.split("Rules (fixed a priori):")[1].strip())
