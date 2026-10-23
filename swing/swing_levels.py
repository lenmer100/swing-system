"""Swing-Tool: Unterstützungen/Widerstände, EINE Einstiegszone, Stopp, Ziele. Nur aus den Tageskursen bis zum letzten Schlusskurs gerechnet,
gleiche Regeln für jede Aktie (keine Ticker-Anpassung).

Methode
1. Volatilität: ATR 14 (Wilder). Alle Breiten und Abstände werden in ATR gemessen, damit ruhige und wilde Aktien gleich behandelt werden.
2. Wendepunkte: bestätigte Swing-Hochs/-Tiefs (Fraktal, 5 Handelstage links und rechts) der letzten 2 Jahre.
3. Zonen: Wendepunkte (Hochs UND Tiefe, Rollentausch) werden nach Preis sortiert und zusammengelegt, solange der Abstand zum
   Zonenmittel <= 0,6 ATR ist. Zonenbreite = Spanne der Wendepunkte, mindestens 0,5 ATR, höchstens 1,5 ATR.
4. Stärke: je Wendepunkt Gewicht = Aktualität (Halbwertszeit 6 Monate) × Volumen (relatives Volumen am Wendetag, 0,5–2).
   Dazu +1 je gleitendem Durchschnitt (20/50/100/200 Tage), der in der Zone liegt (Konfluenz). Zone gilt ab 2 Berührungen.
5. Einstiegszone: die nächste Unterstützung unter dem Kurs (oder die Zone, in der der Kurs steht) mit mindestens 2 Berührungen
   oder Konfluenz mit einer steigenden 50/100/200-Tage-Linie, höchstens 4 ATR bzw. 15 % entfernt. Sonst: steigende 50-Tage-Linie ±0,25 ATR.
6. Einstieg = Oberkante der Zone (Limit). Zweite Tranche optional erst 5 % tiefer, nur wenn sie mindestens 0,5 ATR über dem Stopp liegt.
7. Stopp = tiefster Punkt der Zone bzw. ihres tiefsten Wendetiefs minus 1 ATR (unter dem Swing-Tief, außerhalb des normalen Rauschens).
   Fällt der Stopp in eine tiefere Unterstützung, wandert er unter deren Unterkante (−0,5 ATR), damit er nicht dort liegt, wo Käufer erwartet werden.
8. Ziel 1 = Unterkante des nächsten Widerstands mindestens 1 ATR über dem Einstieg; Ziel 2 = der Widerstand danach.
   Ohne Widerstand (Allzeithoch-Nähe): Ziel = Einstieg + 2 × Risiko, als solches gekennzeichnet.
9. Knock-out-Vorschlag = Stopp − 1 ATR (Puffer für Kurslücken über den Stopp)."""
import numpy as np
import pandas as pd
from functools import lru_cache
from lib import prices

W, LOOKBACK, MERGE, WMIN, WMAX, HALF = 5, 504, 0.6, 0.5, 1.5, 126

def atr(px, n=14):
    h, l, c = px.high, px.low, px.close
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()

def pivots(px, w=W):
    hi, lo, n = px.high.values, px.low.values, len(px); out = []
    for i in range(w, n - w):
        if hi[i] == hi[i - w:i + w + 1].max(): out.append((i, float(hi[i]), "H"))
        if lo[i] == lo[i - w:i + w + 1].min(): out.append((i, float(lo[i]), "T"))
    return out

def _mas(px):
    c = px.close; out = {}
    for n in (20, 50, 100, 200):
        if len(c) >= n + 20:
            s = c.rolling(n).mean(); out[n] = dict(v=float(s.iloc[-1]), rising=bool(s.iloc[-1] > s.iloc[-21]))
    return out

def analyse(sym):
    return _analyse(sym, str(prices(sym).date.iloc[-1]))

@lru_cache(maxsize=4096)
def _analyse(sym, _last):
    px = prices(sym).reset_index(drop=True)
    px = px[px.close > 0].reset_index(drop=True)
    a = float(atr(px).iloc[-1]); price = float(px.close.iloc[-1]); n = len(px)
    seg = px.tail(LOOKBACK).reset_index(drop=True); off = n - len(seg)
    vol = seg.volume.astype(float); rv = (vol / vol.rolling(50, min_periods=10).mean()).fillna(1).clip(.5, 2).values
    pv = sorted(pivots(seg), key=lambda x: x[1])
    cl = []
    for i, p, k in pv:
        if cl and abs(p - np.mean([x[1] for x in cl[-1]])) <= MERGE * a: cl[-1].append((i, p, k))
        else: cl.append([(i, p, k)])
    mas = _mas(px); zones = []
    for g in cl:
        ps = [x[1] for x in g]; lo, hi = min(ps), max(ps); mid = (lo + hi) / 2
        if hi - lo < WMIN * a: lo, hi = mid - WMIN * a / 2, mid + WMIN * a / 2
        if hi - lo > WMAX * a: lo, hi = mid - WMAX * a / 2, mid + WMAX * a / 2
        age = [len(seg) - 1 - x[0] for x in g]
        score = sum(0.5 ** (ag / HALF) * rv[x[0]] for ag, x in zip(age, g))
        conf = [m for m, d in mas.items() if lo - .25 * a <= d["v"] <= hi + .25 * a]
        zones.append(dict(lo=lo, hi=hi, mid=mid, touches=len(g), score=score + len(conf), conf=conf, last=str(seg.date.iloc[len(seg) - 1 - min(age)].date()),
                          first=str(seg.date.iloc[len(seg) - 1 - max(age)].date()), age=min(age), low=min(ps), high=max(ps),
                          kinds="".join(sorted({x[2] for x in g}))))
    allz = list(zones)
    # nur belastbare Zonen: >= 2 Berührungen, oder 1 Berührung jünger als 3 Monate mit Konfluenz
    zones = [z for z in zones if z["touches"] >= 2 or (z["age"] <= 63 and z["conf"])]
    for z in zones: z["role"] = "S" if z["hi"] < price else "R" if z["lo"] > price else "K"
    sup = sorted([z for z in zones if z["role"] in ("S", "K")], key=lambda z: -z["hi"])
    res = sorted([z for z in zones if z["role"] in ("R", "K")], key=lambda z: z["lo"])
    # --- Einstiegszone
    entry_z, src = None, None
    for z in sup:
        if price - z["hi"] > min(4 * a, .15 * price): break
        if z["mid"] > price: continue
        if z["touches"] >= 2 or any(mas[m]["rising"] for m in z["conf"] if m >= 50):
            entry_z, src = z, "Unterstützungszone"; break
    if entry_z is None and 50 in mas and mas[50]["v"] < price and mas[50]["rising"] and price - mas[50]["v"] <= min(4 * a, .15 * price):
        v = mas[50]["v"]; lows = [z for z in sup if z["hi"] < v]
        entry_z = dict(lo=v - .25 * a, hi=v + .25 * a, mid=v, touches=0, conf=[50], low=v - .25 * a, score=1, role="S", last=None, first=None, kinds="")
        src = "50-Tage-Linie"
    plan = None
    if entry_z:
        inside = entry_z["lo"] <= price <= entry_z["hi"]
        entry = price if inside else entry_z["hi"]
        stop = min(entry_z["lo"], entry_z["low"]) - a
        # Stopp nicht in eine tiefere Unterstützung legen: dann unter deren Unterkante (−0,5 ATR)
        for z in sup:
            if z is not entry_z and z["hi"] < entry_z["lo"] and z["lo"] - .25 * a < stop <= z["hi"] + .25 * a: stop = z["lo"] - .5 * a; break
        risk = entry - stop
        t2nd = entry * .95; second = t2nd if t2nd - stop >= .5 * a else None
        hi52 = float(px.high.tail(252).max())
        ups = sorted([(z["lo"], f"Widerstand, {z['touches']}× berührt" if z["touches"] > 1 else f"Swing-Hoch {pd.Timestamp(z['last']).strftime('%m.%Y')}") for z in allz if z["lo"] >= entry + a]
                     + ([(hi52, "52-Wochen-Hoch")] if hi52 >= entry + a else []))
        ups = [u for i, u in enumerate(ups) if i == 0 or u[0] > ups[i - 1][0] + .5 * a]
        if ups: t1, t1src = ups[0]
        else: t1, t1src = entry + 2 * risk, "kein Widerstand darüber: 2 × Risiko"
        t2 = ups[1][0] if len(ups) > 1 else None
        plan = dict(src=src, zone=entry_z, lo=entry_z["lo"], hi=entry_z["hi"], inside=inside, entry=entry, stop=stop, risk=risk, risk_pct=risk / entry,
                    stop_atr=(entry_z["lo"] - stop) / a, stop_moved=stop < min(entry_z["lo"], entry_z["low"]) - a - 1e-9, second=second, t1=t1, t1src=t1src, t2=t2, crv=(t1 - entry) / risk if risk > 0 else None,
                    ko=stop - a, dist=price / entry - 1)
    return dict(sym=sym, price=price, atr=a, atr_pct=a / price, zones=zones, sup=sup, res=res, mas=mas, plan=plan, asof=str(px.date.iloc[-1].date()),
                pivots=[(str(seg.date.iloc[i].date()), p, k) for i, p, k in pivots(seg)][-40:])
