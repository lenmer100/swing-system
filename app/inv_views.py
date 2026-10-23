"""Investment-Reiter Tranchenplan, Stressszenario, Unterstützungen.
Nur Werte aus investment.calc (Bewertung, Kursdaten); nichts erfunden."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import fairvalue
from lib import pchart, ii, prices_long, fnum, fprice, fpct, fdate, table, FONT
from swing import pstrip, sgn
import lib as _lib
def _m(f):
    """Negative Werte mit echtem Minuszeichen (−) statt Bindestrich."""
    def g(*a, **k):
        r = f(*a, **k); return "−" + r[1:] if isinstance(r, str) and r.startswith("-") else r
    return g
fnum, fprice, fpct = _m(_lib.fnum), _m(_lib.fprice), _m(_lib.fpct)

TCOL = {1: "#1e7b45", 2: "#2d8fa5", 3: "#6a5acd"}
INK, GREY, RED, BLUE, GREEN = "#1d2939", "#667085", "#c0322b", "#337ab7", "#1e7b45"

def h2(t, info=None): st.markdown(f'<div class="h2" style="margin-top:6px">{t}{" " + ii(info) if info else ""}</div>', unsafe_allow_html=True)

def _rgba(h, a): h = h.lstrip("#"); return f"rgba({int(h[:2], 16)},{int(h[2:4], 16)},{int(h[4:], 16)},{a})"

def _ticks(x0, x1, years):
    f = "YS" if years > 3 else "QS"
    tv = pd.date_range(x0, x1 if years <= 3 else x1 - (x1 - x0) * 0, freq=f)
    MON = ["Jan", "Apr", "Juli", "Okt"]
    return list(tv), [str(d.year) if f == "YS" or d.month == 1 else MON[(d.month - 1) // 3] for d in tv]

def _layout(fig, height, x0, xr, yl, yh, years, x1=None):
    tv, tt = _ticks(x0, x1 or xr, years)
    fig.update_layout(height=height, separators=",.", margin=dict(l=8, r=8, t=8, b=8), showlegend=False, plot_bgcolor="#fff", paper_bgcolor="#fff",
                      hovermode="x unified", font=dict(family=FONT, color=GREY, size=12),
                      hoverlabel=dict(bgcolor="#fff", bordercolor="#d0d7e2", font=dict(family=FONT, size=13, color=INK)),
                      yaxis=dict(gridcolor="#f2f4f7", side="right", tickformat=",.0f", range=[yl, yh], zeroline=False),
                      xaxis=dict(showgrid=False, range=[x0, xr], tickvals=tv, ticktext=tt, hoverformat="%d.%m.%Y", showspikes=True, spikecolor="#d0d7e2", spikethickness=1))

def _labels(fig, items, x, yl, yh):
    """Beschriftungen rechts neben dem Kursverlauf, ohne Überlappung."""
    lab = sorted(items, key=lambda l: l["y"]); gap = (yh - yl) * .055
    for i, l in enumerate(lab): l["ly"] = l["y"] if i == 0 else max(l["y"], lab[i - 1]["ly"] + gap)
    for l in lab:
        fig.add_annotation(x=x, y=l["ly"], text=l["t"], showarrow=False, xanchor="left", yanchor="middle", font=dict(size=12, color=l["col"]),
                           bgcolor="rgba(255,255,255,.92)", borderpad=2)

CSS = """<style>
.ivwrap{overflow-x:auto;-webkit-overflow-scrolling:touch} .ivwrap .ivt{min-width:640px}
@media (max-width:640px){.pstrip{grid-template-columns:1fr !important} [class*="st-key-scard"] button{min-height:92px} [class*="st-key-scard"] button p strong{font-size:21px}}
.ivt{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums}
.ivt th{font-size:12px;font-weight:600;color:var(--muted);text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)} .ivt th.r,.ivt td.r{text-align:right}
.ivt td{padding:11px 10px;border-bottom:1px solid #f2f4f7;color:#1d2939;vertical-align:middle} .ivt tr.sum td{border-top:1px solid var(--line);border-bottom:none;font-weight:700;background:#fafbfd}
.ivt .dot{display:inline-flex;width:24px;height:24px;border-radius:50%;color:#fff;font-size:12px;font-weight:700;align-items:center;justify-content:center;margin-right:8px}
.ivt .bar{display:inline-block;height:8px;border-radius:4px;background:var(--c);vertical-align:middle;margin-right:8px}
.ivt .sub{color:var(--muted);font-size:12.5px}
.ivempty{border:1px solid var(--line);border-radius:12px;padding:28px 28px;background:#fafbfd;display:flex;flex-direction:column;gap:6px;margin-top:8px}
.ivempty .t{font-size:18px;font-weight:700;color:#1d2939} .ivempty .s{font-size:14px;color:#475467}
.ivstat{display:inline-block;border-radius:999px;padding:3px 12px;font-size:12.5px;font-weight:600;background:var(--b);color:var(--c);margin:2px 0 8px}
[class*="st-key-scard_"] button,[class*="st-key-scardsel_"] button{display:block;width:100%;min-height:118px;text-align:left;border:1px solid #d0d7e2;border-radius:10px;background:#fff;padding:14px 18px;transition:border-color .15s,box-shadow .15s}
[class*="st-key-scard_"] button:hover,[class*="st-key-scardsel_"] button:hover{border-color:#98a2b3;box-shadow:0 1px 4px rgba(16,24,40,.08)}
[class*="st-key-scard_"] button p,[class*="st-key-scardsel_"] button p{margin:0;font-size:13px;line-height:1.5;color:#667085;text-align:left;white-space:normal}
[class*="st-key-scard_"] button p strong,[class*="st-key-scardsel_"] button p strong{display:block;font-size:26px;line-height:1.25;color:#1d2939;font-weight:700;margin:2px 0}
[class*="st-key-scard_"] button p em,[class*="st-key-scardsel_"] button p em{font-style:normal;font-weight:600;color:#c0322b}
[class*="st-key-scard_"] button div,[class*="st-key-scardsel_"] button div{width:100%;justify-content:flex-start}
[class*="st-key-scardsel_"]{border-radius:10px;box-shadow:0 0 0 2px #c0322b,0 0 0 5px rgba(192,50,43,.10)}
[class*="st-key-scardsel_"] button,[class*="st-key-scardsel_"] button:hover,[class*="st-key-scardsel_"] button:focus,[class*="st-key-scardsel_"] button:active,[class*="st-key-scardsel_"] button:focus-visible{border-color:transparent !important;background:#fffafa !important;box-shadow:none !important;outline:none !important}
[class*="st-key-scardsel_"] button p strong{color:#c0322b}
</style>"""

def empty(title, sub, reasons=None):
    st.markdown(f'<div class="ivempty"><span class="t">{title}</span><span class="s">{sub}</span></div>', unsafe_allow_html=True)
    if reasons:
        with st.expander("mehr"):
            st.markdown("".join(f'<div class="muted" style="padding:3px 0">{r}</div>' for r in reasons), unsafe_allow_html=True)

def implied_txt(sym):
    """Kapazitätsaufbau (v5 display_mode implied_return): statt eines Punktwerts die vom Kurs implizierte Rendite auf neue Kapazität."""
    ir = fairvalue.implied(sym) or {}; w = ir.get("wacc"); v = ir.get("value")
    if v is None:
        return (f"Der Wert hängt fast nur an der künftigen Rendite der neuen Kapazität. Selbst mit über 80 % Rendite auf neues Kapital lässt sich der heutige Kurs "
                f"nicht erklären (Kapitalkosten {fpct(w, 1)}). Das System setzt deshalb keinen fairen Wert und keine Kaufniveaus.")
    return (f"Der Kurs preist eine Rendite von {fpct(v, 1)} auf das neu investierte Kapital ein (Kapitalkosten {fpct(w, 1)}). "
            + ("Das liegt über den Kapitalkosten: Der Markt setzt auf profitable Kapazität." if v > w else "Das liegt unter den Kapitalkosten: Der Kurs verlangt wenig.")
            + " Kein Punktwert, deshalb keine Kaufniveaus.")

# ---------------------------------------------------------------- Tranchenplan
def tranches(c, sym, R):
    st.markdown(CSS, unsafe_allow_html=True)
    price = c["price"]; tr = R["tr"]; fv = R["fv"]; cur = c["currency"]
    if not tr or not fv:
        bad = fairvalue.unreliable(sym)
        if fairvalue.mode(sym) == "implied_return":
            empty("Kein Tranchenplan: Kapazitätsaufbau", implied_txt(sym), bad); return
        empty("Kein Tranchenplan", "Die Bewertung ist nicht belastbar. Ohne belastbaren fairen Wert setzt das System keine Kaufniveaus.", bad); return
    avg = sum(t["w"] for t in tr) / sum(t["w"] / t["v"] for t in tr)   # Ø Einstand bei gleichen Beträgen je Gewicht (Stückzahl-gewichtet)
    cum, inv, sh = [], 0.0, 0.0
    for t in tr: inv += t["w"]; sh += t["w"] / t["v"]; cum.append((inv, inv / sh))
    over = price > fv["med"]
    st.markdown(f'<span class="ivstat" style="--c:{"#b54708" if over else GREEN};--b:{"#fef0c7" if over else "#e3f4ea"}">'
                f'{"Kurs über dem fairen Wert: Plan startet erst ab " + fnum(tr[0]["v"]) if over else "Tranche 1 zum aktuellen Kurs möglich"}</span>', unsafe_allow_html=True)
    stop = R.get("stop")
    h2("Kaufniveaus im Kursverlauf", "Tranche 1 zum Kurs, höchstens zum fairen Wert (Basisszenario). Tranche 2 in der Kaufzone (fairer Wert minus Sicherheitsmarge), "
       "an eine langfristige Unterstützung bis ±5 % angelehnt. Tranche 3 am pessimistischen Wert. Stufen mindestens 5 % auseinander. "
       "Stopp (These gebrochen) 8 % unter dem tieferen Wert aus pessimistischem Wert und letzter Tranche. Nur bei belastbarer Bewertung.")
    years = 3; d = _close_tail(sym, years)
    x0, x1 = d.index.min(), d.index.max(); span = x1 - x0; xl = x1 + span * .015; xr = x1 + span * .24
    ys = [t["v"] for t in tr] + [fv["med"], avg] + ([stop] if stop else []) + list(d.values); yl, yh = min(ys) * .9, max(ys) * 1.05
    fig = go.Figure()
    for t in tr:
        b = t["v"] * .015
        fig.add_shape(type="rect", x0=x0, x1=xl, y0=t["v"] - b, y1=t["v"] + b, fillcolor=_rgba(TCOL[t["n"]], .13), line_width=0, layer="below")
        fig.add_shape(type="line", x0=x0, x1=xl, y0=t["v"], y1=t["v"], line=dict(color=TCOL[t["n"]], width=1.6))
    fig.add_shape(type="line", x0=x0, x1=xl, y0=fv["med"], y1=fv["med"], line=dict(color=GREEN, width=1.2, dash="dash"))
    fig.add_shape(type="line", x0=x0, x1=xl, y0=avg, y1=avg, line=dict(color=INK, width=1.2, dash="dot"))
    if stop: fig.add_shape(type="line", x0=x0, x1=xl, y0=stop, y1=stop, line=dict(color=RED, width=1.4, dash="dash"))
    fig.add_scatter(x=d.index, y=d.values, mode="lines", line=dict(color=INK, width=1.6), name="Schluss", hovertemplate="%{y:,.2f} " + cur + "<extra></extra>")
    fig.add_scatter(x=[x1], y=[price], mode="markers", marker=dict(color=INK, size=8), hoverinfo="skip")
    items = [dict(y=t["v"], t=f"<b>T{t['n']}</b>  {fnum(t['v'])} · {fpct(t['w'], 0)}", col=TCOL[t["n"]]) for t in tr]
    if abs(tr[0]["v"] / fv["med"] - 1) < .002: items[0]["t"] = f"<b>T1 = Fairer Wert</b>  {fnum(tr[0]['v'])} · {fpct(tr[0]['w'], 0)}"
    else: items.append(dict(y=fv["med"], t=f"<b>Fairer Wert</b>  {fnum(fv['med'])}", col=GREEN))
    items += [dict(y=avg, t=f"<b>Ø Einstand</b>  {fnum(avg)}", col=INK)]
    if stop: items.append(dict(y=stop, t=f"<b>Stopp</b>  {fnum(stop)} · {fpct(stop / price - 1, 0)}", col=RED))
    if all(abs(price / i["y"] - 1) > .03 for i in items): items.append(dict(y=price, t=f"<b>Kurs</b>  {fnum(price)}", col=GREY))
    _labels(fig, items, xl, yl, yh); _layout(fig, 420, x0, xr, yl, yh, years, x1)
    pchart(fig, use_container_width=True, key=f"trc_{sym}")
    # Tabelle: Gewichtung, Abstand, Ø Einstand kumuliert
    mx = max(t["w"] for t in tr)
    body = "".join(f'<tr><td><span class="dot" style="background:{TCOL[t["n"]]}">{t["n"]}</span><b>Tranche {t["n"]}</b></td>'
                   f'<td class="r"><b>{fnum(t["v"])}</b></td><td class="r {"tone-neg" if t["v"] < price * .999 else ""}">{sgn(t["v"] / price - 1) if abs(t["v"] / price - 1) > .001 else "zum Kurs"}</td>'
                   f'<td><span class="bar" style="--c:{TCOL[t["n"]]};width:{60 * t["w"] / mx:.0f}px"></span>{fpct(t["w"], 0)}</td>'
                   f'<td class="r">{fpct(cu[0], 0)}</td><td class="r">{fnum(cu[1])}</td><td class="sub">{t["why"]}</td></tr>' for t, cu in zip(tr, cum))
    body += (f'<tr class="sum"><td>Gesamt</td><td class="r">Ø {fnum(avg)}</td><td class="r">{sgn(avg / price - 1)}</td><td>100 %</td><td></td>'
             f'<td class="r">{fnum(avg)}</td><td class="sub" style="font-weight:400">{sgn(fv["med"] / avg - 1)} bis zum fairen Wert</td></tr>')
    st.markdown(f'<div class="ivwrap"><table class="ivt"><thead><tr><th>Tranche</th><th class="r">Kurs ({cur})</th><th class="r">Zum Kurs</th><th>Gewicht</th><th class="r">Investiert</th>'
                f'<th class="r">Ø Einstand {ii("Durchschnittlicher Kaufkurs nach dieser Tranche bei gleichem Betrag je Gewichtsanteil.")}</th><th>Herleitung</th></tr></thead><tbody>{body}</tbody></table></div>', unsafe_allow_html=True)
    st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
    pstrip([("Ø Einstand", fnum(avg), f"{sgn(avg / price - 1)} zum Kurs", None), ("Fairer Wert", fnum(fv["med"]), f"{sgn(fv['med'] / avg - 1)} zum Ø Einstand", "pos"),
            ("Stressszenario", fnum(R["worst"]), f"{sgn(R['worst'] / avg - 1)} zum Ø Einstand", "neg")]
           + ([("Stopp (These gebrochen)" + (" " + ii(R["stop_why"]) if R.get("stop_why") else ""), fnum(stop), f"{sgn(stop / avg - 1)} zum Ø Einstand", "neg")] if stop else []))

# ---------------------------------------------------------------- Stressszenario
SNAME = {"Stopp (These gebrochen)": "Stopp (These gebrochen)", "Pessimistisches Szenario": "Pessimistisches Szenario", "Heutiger Gewinn × reifes KGV": "Gewinn × reifes KGV", "Größter historischer Rückgang": "Historischer Extremfall"}
SORD = ["Pessimistisches Szenario", "Heutiger Gewinn × reifes KGV", "Größter historischer Rückgang", "Stopp (These gebrochen)"]

def _set(k, i): st.session_state[k] = i

def stress_chart(sym, cur, price, v, name, col, key):
    px = prices_long(sym).set_index("date"); years = 3; d = px.close[px.index >= px.index.max() - pd.Timedelta(days=365 * years)]
    x0, x1 = d.index.min(), d.index.max(); span = x1 - x0; xl = x1 + span * .015; xr = x1 + span * .24
    yl, yh = min(list(d.values) + [v]) * .85, max(list(d.values) + [price]) * 1.05
    fig = go.Figure()
    fig.add_shape(type="rect", x0=x1, x1=xl, y0=v, y1=price, fillcolor=_rgba(RED, .10), line_width=0, layer="below")
    fig.add_shape(type="line", x0=x0, x1=xl, y0=v, y1=v, line=dict(color=RED, width=1.8))
    fig.add_shape(type="line", x0=x0, x1=xl, y0=price, y1=price, line=dict(color=GREY, width=1, dash="dot"))
    fig.add_scatter(x=d.index, y=d.values, mode="lines", line=dict(color=INK, width=1.6), hovertemplate="%{y:,.2f} " + cur + "<extra></extra>")
    fig.add_annotation(x=x1, y=v, ax=x1, ay=price, xref="x", yref="y", axref="x", ayref="y", showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.6, arrowcolor=RED, text="")
    _labels(fig, [dict(y=v, t=f"<b>{name}</b>  {fnum(v)} · {fpct(v / price - 1, 1)}", col=RED), dict(y=price, t=f"<b>Kurs</b>  {fnum(price)}", col=GREY)], xl, yl, yh)
    _layout(fig, 360, x0, xr, yl, yh, years, x1)
    pchart(fig, use_container_width=True, key=key)

def stress(c, sym, R):
    st.markdown(CSS, unsafe_allow_html=True)
    price = c["price"]; cur = c["currency"]
    wc = sorted(R["wc"], key=lambda x: SORD.index(x[0]) if x[0] in SORD else 9); opts = [SNAME.get(n, n) for n, _, _ in wc]
    if not wc:
        empty("Kein Stressszenario", "Für diese Aktie gibt es weder einen belastbaren Wert noch einen Rückgang unter den heutigen Kurs."); return
    h2("Stressszenario", " · ".join(f"{o}: {s_}" for o, (_, _, s_) in zip(opts, wc)) + ". Keine Prognose, sondern Grundlage für die Positionsgröße.")
    if not R["fv"]:
        m_ = fairvalue.mode(sym)
        st.markdown(f'<p class="muted" style="margin:0 0 8px">{implied_txt(sym) if m_ == "implied_return" else "Bewertung nicht belastbar: kein Stresswert aus der Bewertung, nur der historische Extremfall."}</p>', unsafe_allow_html=True)
    k = f"stress_{sym}"
    if st.session_state.get(k) not in range(len(opts)): st.session_state[k] = 0
    sel = st.session_state[k]
    cols = st.columns(len(opts), gap="small")
    for i, (o, (_, x, s_)) in enumerate(zip(opts, wc)):
        with cols[i], st.container(key=f"{'scardsel' if i == sel else 'scard'}_{i}"):
            st.button(f"{o}\n\n**{fnum(x)} {cur}**\n\n*{sgn(x / price - 1)} zum Kurs*", key=f"scb_{sym}_{i}", width="stretch", on_click=_set, args=(k, i))
    n, v, src = wc[sel]
    stress_chart(sym, cur, price, v, opts[sel], RED, key=f"stc_{sym}_{sel}")
    def num(kk, d):
        x = st.session_state.get(kk, d)
        try: return float(str(x).replace(".", "").replace(",", ".")) if isinstance(x, str) else float(x or d)
        except ValueError: return d
    dep = num(f"dep_{sym}", 100000.0); wt = num(f"wt_{sym}", 5.0); pos = dep * wt / 100
    pstrip([("Verlust je Aktie", fprice(v - price, cur), fpct(v / price - 1, 1), "neg"),
            (f"Verlust bei Zielposition {fprice(pos, cur, 0)}", fprice(pos * (v / price - 1), cur, 0), f"{fpct(pos * (v / price - 1) / dep, 2)} des Depots", "neg"),
            ("Herleitung", opts[sel], src[:70] + ("…" if len(src) > 70 else ""), None)])

# ---------------------------------------------------------------- Unterstützungen
def _zones(m, price):
    """Monatstiefs (lokale Minima, ±2 Monate) unter dem Kurs zu Zonen bündeln (Abstand ≤ 4 %); Stärke = Zahl der Tests."""
    lows, idx = m.low.values, m.index; piv = []
    for i in range(2, len(lows) - 2):
        if lows[i] == min(lows[i - 2:i + 3]) and lows[i] < price: piv.append((float(lows[i]), idx[i]))
    piv.sort(key=lambda x: -x[0]); Z = []
    for v, dt in piv:
        if Z and v >= Z[-1]["lo"] * .96: Z[-1]["lo"] = min(Z[-1]["lo"], v); Z[-1]["n"] += 1; Z[-1]["last"] = max(Z[-1]["last"], dt)
        else: Z.append(dict(lo=v, hi=v, n=1, last=dt))
    for z in Z:
        if z["hi"] - z["lo"] < z["hi"] * .01: z["lo"] *= .99; z["hi"] *= 1.01   # Mindestbreite ±1 %
    return Z

def _drawdowns(close):
    """Abgeschlossene Rückgänge > 15 % vom vorherigen Hoch (Episoden)."""
    run = close.cummax(); dd = close / run - 1; ep, cur = [], 0.0
    for x in dd.values:
        if x < cur: cur = x
        if x == 0 and cur < -.15: ep.append(cur); cur = 0.0
        elif x == 0: cur = 0.0
    if cur < -.15: ep.append(cur)
    return ep

@st.cache_data(show_spinner=False, max_entries=256)
def _support_data(sym, price):
    """Wochen-/Monatsaggregation, Rückgänge und Zonen je Titel einmal rechnen (Tab rendert sonst unter Last langsam)."""
    px = prices_long(sym).set_index("date"); w = px.resample("W-FRI").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    m = px.resample("ME").agg({"low": "min", "close": "last"}).dropna()
    s200, s100 = w.close.rolling(200).mean(), w.close.rolling(100).mean()
    return w, s200, s100, float(px.close.max()), _drawdowns(px.close), _zones(m.tail(96), price)[:4]

@st.cache_data(show_spinner=False, max_entries=256)
def _close_tail(sym, years):
    px = prices_long(sym).set_index("date"); return px.close[px.index >= px.index.max() - pd.Timedelta(days=365 * years)]

def support(c, sym, R):
    st.markdown(CSS, unsafe_allow_html=True)
    price = c["price"]; fv = R["fv"]; cur = c["currency"]
    w, s200, s100, ath, ep, Z = _support_data(sym, price)
    L = []
    for z in Z:
        mid = (z["lo"] + z["hi"]) / 2
        L.append(dict(name=f"Unterstützungszone {fnum(z['lo'], 0)} – {fnum(z['hi'], 0)}", lo=z["lo"], hi=z["hi"], v=mid, col="#7a5a00", art="Monatstiefs",
                      st=f"{z['n']}× getestet, zuletzt {fdate(z['last'])[3:]}"))
    for lab, s_ in (("200-Wochen-Linie", s200), ("100-Wochen-Linie", s100)):
        if not np.isnan(s_.iloc[-1]) and s_.iloc[-1] < price: L.append(dict(name=lab, v=float(s_.iloc[-1]), col="#475467", art="Gleitender Durchschnitt", st="Ø Wochenschluss"))
    if ep:
        med, mx = float(np.median(ep)), float(min(ep))
        for lab, dd_ in ((f"Typische Korrektur ({fpct(med, 0)})", med), (f"Größter Rückgang ({fpct(mx, 0)})", mx)):
            v_ = ath * (1 + dd_)
            if v_ < price: L.append(dict(name=lab, v=v_, col=RED, art="Historischer Rückgang", st=f"vom Hoch {fnum(ath, 0)}, {len(ep)} Rückgänge > 15 % seit {w.index[0].year}"))
    if fv and fv["mos"] < price: L.append(dict(name="Kaufzone (fairer Wert minus Sicherheitsmarge)", v=fv["mos"], col=GREEN, art="Bewertung", st=f"fairer Wert {fnum(fv['med'], 0)}"))
    for x in L: x["d"] = x["v"] / price - 1
    L.sort(key=lambda x: -x["v"])
    near = [x for x in L if x["d"] >= -.45]   # Chart und Tabelle: Marken bis 45 % unter dem Kurs, höchstens sechs; Rest unter "mehr"
    rest = [x for x in L if x not in near[:6]]; L = near[:6] or L[:2]
    h2("Langfristige Unterstützungen", "Wochenchart der letzten acht Jahre. Zonen aus gebündelten Monatstiefs (Abstand bis 4 %), 100- und 200-Wochen-Linie, "
       "Rückgangsmarken vom Allzeithoch (typische und größte Korrektur seit Beginn der Kursdaten) sowie die Kaufzone der Bewertung.")
    if not L:
        empty("Keine Unterstützungen unter dem Kurs", "Unter dem aktuellen Kurs liegen keine langfristigen Marken."); return
    years = 8; ww = w[w.index >= w.index.max() - pd.Timedelta(days=365 * years)]
    x0, x1 = ww.index.min(), ww.index.max(); span = x1 - x0; xl = x1 + span * .012; xr = x1 + span * .27
    ys = [x.get("lo", x["v"]) for x in L] + list(ww.low.values) + list(ww.high.values); yl, yh = max(0, min(ys) * .9), max(ys) * 1.04
    fig = go.Figure()
    for x in L:
        if "lo" in x: fig.add_shape(type="rect", x0=x0, x1=xl, y0=x["lo"], y1=x["hi"], fillcolor=_rgba(x["col"], .14), line_width=0, layer="below")
        elif x["art"] == "Historischer Rückgang": fig.add_shape(type="line", x0=x0, x1=xl, y0=x["v"], y1=x["v"], line=dict(color=x["col"], width=1.2, dash="dot"))
        elif x["art"] == "Bewertung": fig.add_shape(type="line", x0=x0, x1=xl, y0=x["v"], y1=x["v"], line=dict(color=x["col"], width=1.4, dash="dash"))
    fig.add_candlestick(x=ww.index, open=ww.open, high=ww.high, low=ww.low, close=ww.close, increasing=dict(line=dict(color="#98a2b3", width=1), fillcolor="#fff"),
                        decreasing=dict(line=dict(color="#475467", width=1), fillcolor="#475467"), name="Woche", hoverinfo="skip")
    for s_, col, dash, nm in ((s100, "#337ab7", "solid", "100W"), (s200, "#6a5acd", "solid", "200W")):
        s_ = s_[s_.index >= x0]
        fig.add_scatter(x=s_.index, y=s_.values, mode="lines", line=dict(color=col, width=1.6, dash=dash), name=nm, hovertemplate=nm + " %{y:,.2f}<extra></extra>")
    fig.add_scatter(x=ww.index, y=ww.close, mode="lines", line=dict(width=0), hovertemplate="Schluss %{y:,.2f} " + cur + "<extra></extra>", showlegend=False)
    lc = {"200-Wochen-Linie": "#6a5acd", "100-Wochen-Linie": "#337ab7"}
    items = [dict(y=x["v"], t=f"<b>{x['name'].split(' (')[0] if 'lo' not in x else 'Zone'}</b>  {fnum(x['v'], 0)} · {fpct(x['d'], 0)}", col=lc.get(x["name"], x["col"])) for x in L]
    items.append(dict(y=price, t=f"<b>Kurs</b>  {fnum(price, 0)}", col=INK))
    _labels(fig, items, xl, yl, yh); _layout(fig, 460, x0, xr, yl, yh, years, x1)
    fig.update_layout(xaxis_rangeslider_visible=False)
    pchart(fig, use_container_width=True, key=f"spc_{sym}")
    nxt = L[0]
    body = "".join(f'<tr><td><span class="bar" style="--c:{lc.get(x["name"], x["col"])};width:10px;height:10px;border-radius:2px"></span><b>{x["name"]}</b></td><td class="sub">{x["art"]}</td>'
                   f'<td class="r"><b>{fnum(x["lo"], 0) + " – " + fnum(x["hi"], 0) if "lo" in x else fnum(x["v"], 0)}</b></td><td class="r tone-neg"><b>{fpct(x["d"], 1)}</b></td><td class="sub">{x["st"]}</td></tr>' for x in L)
    st.markdown(f'<div class="ivwrap"><table class="ivt"><thead><tr><th>Marke</th><th>Art</th><th class="r">Kurs ({cur})</th><th class="r">Abstand</th><th>Stärke / Basis</th></tr></thead><tbody>{body}</tbody></table></div>', unsafe_allow_html=True)
    st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
    cells = [("Nächste Marke", fnum(nxt["v"], 0), f"{fpct(nxt['d'], 1)} · {nxt['art']}", None)]
    if not np.isnan(s200.iloc[-1]): cells.append(("200-Wochen-Linie", fnum(float(s200.iloc[-1]), 0), f"Kurs {sgn(price / float(s200.iloc[-1]) - 1)} darüber" if price > s200.iloc[-1] else f"Kurs {sgn(price / float(s200.iloc[-1]) - 1)} darunter", None))
    cells.append(("Abstand zum Allzeithoch", fpct(price / ath - 1, 1), f"Hoch {fnum(ath, 0)}", None))
    pstrip(cells)
    if rest:
        with st.expander("mehr"):
            st.markdown(table([{"Marke": x["name"], "Art": x["art"], "Kurs": fnum(x["v"], 0), "Abstand": fpct(x["d"], 1), "Basis": x["st"]} for x in rest],
                              ["Marke", "Art", "Kurs", "Abstand", "Basis"], align={"Kurs": "r", "Abstand": "r"}), unsafe_allow_html=True)
