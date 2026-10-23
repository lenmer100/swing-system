"""Produktteil B: Swing-Tool. (A) Chancen-Board über den Pool, (B) Aktie mit Reitern: Setup und Chart, Einstiegsplan, Hebel und Kosten,
Technik, Ziele, Einschätzung. Das Urteil des Systems steht bewusst im letzten Reiter. Entscheidungshilfe, es wird nichts gehandelt."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from lib import (pad_right, pchart, inote, ibox, pill, spark, h2, footer2, stock_head, prices, fnum, fprice, fpct, fdate, plain, dedupe, badge, table, ii, plot_layout, PLOT_CFG, FONT)
import lwchart
import ag_style as agx
import common
from common import META, CASES
import json as _json
from lib import D as _D; QUARTERS = _json.load(open(_D / 'quarters.json'))
from swing_calc import plan_of, swing_status, STATUS_ORDER, STATUS_TONE, trend_ok, SW, crv, plan_target, row, levels, targets, regime, tdays, PRESETS, turbo_model

TABS = ["Überblick", "Chart und Setup", "Einstiegsplan", "Hebel und Kosten", "Zahlen", "Technik"]
BLUE, POS, NEG, WARN, MUT = "#337ab7", "#1e7b45", "#c0322b", "#b54708", "#5d6b7e"
CSS = """<style>
.sw-kpis{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px;margin:6px 0 4px}
.sw-k{border:1px solid var(--line);border-radius:10px;padding:14px 16px;background:#fff}
.sw-k .l{font-size:12.5px;color:var(--muted);font-weight:500;display:flex;align-items:center}
.sw-k .v{font-size:21px;font-weight:700;color:var(--ink);margin:6px 0 2px;white-space:nowrap;font-variant-numeric:tabular-nums}
.sw-k .s{font-size:12.5px;color:var(--muted)}
.tone-pos{color:#1e7b45 !important} .tone-neg{color:#c0322b !important} .tone-warn{color:#b54708 !important}
.sw-pill{display:inline-block;font-size:12px;font-weight:600;border-radius:5px;padding:2px 8px;background:#eef4fa;color:#2a6496;white-space:nowrap}
.sw-note{font-size:13px;color:var(--muted);line-height:1.55;margin:6px 0 0}
.sw-pool{display:flex;gap:10px;align-items:center;font-size:13.5px;color:var(--ink2);background:#f4f8fb;border:1px solid var(--line);border-radius:8px;padding:9px 14px;margin:4px 0}
.sw-panel{border:1px solid var(--line);border-radius:10px;padding:14px 16px 10px;background:#fff}
.sw-panel .t{font-size:13px;font-weight:700;color:var(--ink);margin-bottom:8px;text-transform:uppercase;letter-spacing:.05em}
.sw-lv{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid #eef2f6;font-size:13.5px;font-variant-numeric:tabular-nums}
.sw-lv:last-child{border-bottom:none} .sw-lv .n{display:flex;align-items:center;gap:8px;color:var(--ink2)} .sw-lv .n i{width:12px;height:12px;border-radius:3px;display:inline-block}
.sw-lv b{color:var(--ink);font-weight:650} .sw-lv small{color:var(--muted);margin-left:8px;font-size:12px}
.sw-lv.cur{background:#f4f8fb;margin:0 -16px;padding:7px 16px}
.steps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin:6px 0}
.step{border:1px solid var(--line);border-radius:10px;padding:16px 18px;background:#fff;position:relative}
.step .no{display:inline-flex;width:26px;height:26px;border-radius:50%;background:#337ab7;color:#fff;font-weight:700;font-size:13px;align-items:center;justify-content:center}
.step .pr{font-size:26px;font-weight:700;color:var(--ink);margin:10px 0 2px;font-variant-numeric:tabular-nums}
.step .d{font-size:13px;color:var(--muted)} .step .a{font-size:12.5px;color:var(--ink2);margin-top:10px;border-top:1px solid #eef2f6;padding-top:8px}
.tl{position:relative;display:grid;grid-template-columns:repeat(4,1fr);margin:10px 0 2px}
.tl:before{content:"";position:absolute;left:6%;right:6%;top:9px;height:3px;background:#e3e8ef}
.tl>div{text-align:center;position:relative;font-size:13px;color:var(--ink2)} .tl>div i{display:block;width:16px;height:16px;border-radius:50%;margin:2px auto 8px;background:#fff;border:3px solid #337ab7}
.tl>div.blk i{border-color:#c0322b} .tl>div b{display:block;color:var(--ink);font-size:14px}
.chk{display:flex;gap:10px;padding:8px 0;border-bottom:1px solid #eef2f6;font-size:13.5px;color:var(--ink2)} .chk:last-child{border-bottom:none}
.chk .m{flex:0 0 18px;height:18px;border-radius:50%;color:#fff;font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;margin-top:1px}
.chk .m.p{background:#1e7b45} .chk .m.f{background:#c0322b} .chk .m.i{background:#98a2b3} .chk .v{margin-left:auto;color:var(--muted);white-space:nowrap;padding-left:12px}
.st-key-sw_inputs{border:1px solid var(--line);border-radius:10px;padding:14px 16px;background:#fafbfd}
.illu{font-size:12.5px;color:#b54708;background:#fffaeb;border:1px solid #fedf89;border-radius:6px;padding:7px 12px;margin:2px 0 6px}
.verd{border:1px solid var(--line);border-radius:12px;padding:20px 24px;background:#fff;display:flex;gap:28px;align-items:center}
.verd .r{font-size:15px;color:var(--ink2);line-height:1.6}
.st-key-board_ctl [data-testid="stSelectbox"]{max-width:250px}
.lcards{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:0 0 16px}
.lc{border:1px solid var(--line);border-radius:10px;padding:16px 20px;background:#fff} .lc:last-child{border-color:#c9dbee;box-shadow:0 0 0 1px #c9dbee inset}
.lc .lh{font-weight:700;font-size:16px;display:flex;justify-content:space-between;align-items:baseline;margin-bottom:10px} .lc .m{font-size:12.5px;color:var(--muted);font-weight:400}
.lcrv{display:flex;align-items:baseline;gap:10px;background:#f4f8fb;border-radius:8px;padding:10px 14px;margin-bottom:8px} .lcrv span:first-child{font-size:13px;color:#5d6b7e}
.lcrv b{font-size:26px;font-variant-numeric:tabular-nums} .lcrv.tone-pos b{color:#1e7b45}.lcrv.tone-warn b{color:#b54708}.lcrv.tone-neg b{color:#c0322b}
.lr{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f2f4f7;font-size:14px} .lr:last-child{border-bottom:0} .lr span{color:#5d6b7e} .lr b{font-weight:600;font-variant-numeric:tabular-nums}
.lr .up{color:#1e7b45}.lr .dn{color:#c0322b}
.csteps{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:14px 0 18px}
.cs{border:1px solid var(--line);border-top:4px solid #98a2b3;border-radius:10px;padding:14px 16px;display:flex;flex-direction:column;gap:4px;background:#fff}
.cs.p{border-top-color:#1e7b45}.cs.w{border-top-color:#f79009}.cs.f{border-top-color:#c0322b}
.cs .n{font-size:12px;color:var(--muted)} .cs .h{font-weight:700;font-size:15px} .cs .v{font-size:14px;color:var(--ink)} .cs .s{font-size:12.5px;color:var(--muted)}
.cs .b{align-self:flex-start;margin-top:auto;font-size:12px;font-weight:600;border-radius:10px;padding:2px 9px;background:#eef4fa;color:#337ab7}
.cs.p .b{background:#e7f5ec;color:#1e7b45}.cs.w .b{background:#fef4e6;color:#b54708}.cs.f .b{background:#fdecea;color:#c0322b}
.st-pos{color:#1e7b45}.st-warn{color:#b54708}.st-neg{color:#c0322b}
.mline{display:flex;flex-wrap:nowrap;gap:22px;align-items:center;border:1px solid var(--line);border-radius:10px;padding:10px 16px;margin:12px 0 16px;font-size:13.5px;white-space:nowrap;overflow:hidden}
.mline .l{color:var(--muted)} .mline b{font-weight:600;color:var(--ink)} .mline b.tone-warn{color:#b54708}.mline b.tone-pos{color:#1e7b45}.mline b.tone-neg{color:#c0322b}
.btb td{padding:0 !important} .btb a.rl{display:block;padding:13px 14px;color:inherit;text-decoration:none;white-space:nowrap} .btb tbody tr{cursor:pointer} .btb tbody tr:hover{background:#f4f8fb}
.btb th{white-space:nowrap} .btb th.r,.btb td.r{text-align:right}
.spill{display:inline-block;font-size:12.5px;font-weight:600;border-radius:12px;padding:2px 10px;background:#f2f4f7;color:#475467}
.spill.pos{background:#e7f5ec;color:#1e7b45}.spill.warn{background:#fef4e6;color:#b54708}.spill.neg{background:#fdecea;color:#c0322b}
.bfoot{font-size:12.5px;color:var(--muted);margin:8px 0 18px}
.pstrip{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));border:1px solid var(--line);border-radius:10px;margin:10px 0 14px;background:#fff}
.pstrip>div{padding:14px 18px;border-right:1px solid var(--line);display:flex;flex-direction:column;gap:3px} .pstrip>div:last-child{border-right:none}
.pstrip .l{font-size:12.5px;color:var(--muted);font-weight:500} .pstrip .v{font-size:24px;font-weight:700;color:var(--ink);font-variant-numeric:tabular-nums;white-space:nowrap}
.pstrip .s{font-size:12.5px;color:var(--muted);white-space:nowrap}
.crumb{font-size:13px;color:var(--muted);margin:14px 0 -6px;display:flex;gap:8px;align-items:center} .crumb a{color:var(--blue);text-decoration:none} .crumb a:hover{text-decoration:underline} .crumb b{color:var(--ink);font-weight:600}
.qbm{display:flex;gap:3px;align-items:flex-end;height:26px} .qbm i{display:block;width:9px;border-radius:2px 2px 0 0;background:#337ab7}
.qbm i.q{background:#1e7b45} .qbm i.v{background:#7a5af8} .qbm i.m{background:#337ab7}
.sw-r52{position:relative;height:8px;background:#e3e8ef;border-radius:4px;margin:10px 0 6px} .sw-r52 i{position:absolute;top:-4px;width:3px;height:16px;background:#1d2939;border-radius:1px}
.mbar{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:6px}
</style>"""

SETUP_RULE = {"Rücktest Ausbruch": "Regel: Kurs kehrt nach einem Ausbruch an die alte Basis-Oberkante zurück; Kauf an der früheren Widerstandszone.",
              "Unterstützungszone": "Regel: Zone aus mindestens zwei Wendepunkten (Hochs und Tiefs, ATR-breit); Kauf per Limit an der Oberkante.",
              "Rücksetzer 100-Tage-Linie": "Regel: Aufwärtstrend, Rücksetzer an die steigende 100-Tage-Linie.",
              "Rücksetzer 50-Tage-Linie": "Regel: Aufwärtstrend, Rücksetzer an die steigende 50-Tage-Linie.",
              "Rücksetzer 200-Tage-Linie": "Regel: Aufwärtstrend, Rücksetzer an die steigende 200-Tage-Linie."}
def qbm(p):
    f = lambda v: max(3, (v or 0) / 100 * 26)
    t = f"Qualität {fnum(p['q'], 0) if p['q'] is not None else 'k. A.'} · Bewertung {fnum(p['v'], 0)} · Momentum {fnum(p['m'], 0)} (Perzentile 0–100)"
    return f'<span class="qbm" title="{t}"><i class="q" style="height:{f(p["q"])}px"></i><i class="v" style="height:{f(p["v"])}px"></i><i class="m" style="height:{f(p["m"])}px"></i></span>'
def k(label, value, sub="", tone=None, info=None):
    return (f'<div class="sw-k"><div class="l">{label}{ii(info) if info else ""}</div><div class="v{" tone-" + tone if tone else ""}">{value}</div>'
            f'<div class="s">{sub}</div></div>')
def kpis(items, n=None):
    st.markdown(f'<div class="sw-kpis" style="grid-template-columns:repeat({n or len(items)},minmax(0,1fr))">{"".join(items)}</div>', unsafe_allow_html=True)
def note(t): st.markdown(inote(t), unsafe_allow_html=True)
def sgn(x, d=1): return fpct(x, d, True)
def de_in(col, label, default, key, d=2, lo=0.0, hi=1e9, disabled=False):
    """Eingabefeld im deutschen Zahlenformat (1.234,56); ungültige Eingaben fallen auf den Vorgabewert zurück."""
    if key not in st.session_state: st.session_state[key] = fnum(default, d)
    v = col.text_input(label, key=key, disabled=disabled)
    try: x = float(v.replace(".", "").replace(" ", "").replace(",", "."))
    except (ValueError, AttributeError): x = None
    if x is None or not lo <= x <= hi:
        col.markdown(f'<span class="sw-note tone-neg" style="font-size:12px">Ungültig, gerechnet wird mit {fnum(default, d)}</span>', unsafe_allow_html=True); x = default
    return x

# ================================================================ (A) Chancen-Board
def market_bar():
    lab, tone, dd = regime(); m = next(iter(CASES.values()))["market"]; q = SW["idx"][1]
    amp = {"grün": "pos", "gelb": "warn", "rot": "neg"}.get(m["regime"], "neu")
    items = [("Marktampel", f'<b class="tone-{amp}">{m["regime"].capitalize()}</b>'), ("Positionsgröße", f'<b>{fpct(m["size_factor"], 0)}</b> der Normalgröße'),
             ("Nasdaq 100", f'<b>{sgn(q["last"] / q["sma50"] - 1)}</b> zur 50-Tage-Linie'), ("Marktbreite", f'<b>{fpct(SW["breadth50"], 0)}</b> über 50-Tage-Linie'), ("VIX", f'<b>{fnum(m["vix"])}</b>')]
    st.markdown('<div class="mline">' + "".join(f'<span><span class="l">{a}</span> {b}</span>' for a, b in items) +
                ii(f"Marktlage {lab}. Marktampel = Systemregel: gelb halbiert jede neue Position, rot erlaubt keine Neukäufe. Marktbreite = Anteil der {fnum(SW['pool_n'], 0)} Pool-Aktien über ihrer 50-Tage-Linie. "
                   f"Verteilungstage der letzten 25 Sitzungen: S&P 500 {SW['idx'][0]['dist_days']}, Nasdaq 100 {q['dist_days']}.") + "</div>", unsafe_allow_html=True)

BCOLS = [("#", "Reihenfolge: zuerst nach Status (in der Zone vor wartend vor gesperrt), dann nach Chance/Risiko."),
         ("Aktie", None),
         ("Setup", "Das Kursmuster, auf dem der Einstiegsplan beruht. Die Regel steht beim Darüberfahren über dem Setup."),
         ("Status", "Wo der Trade heute steht. In Einstiegszone: Kurs liegt in der Kaufzone. Nahe: bis 3 % darüber. Warten auf Rücksetzer: Kurs liegt höher, gekauft wird erst in der Zone. "
                    "Zahlen abwarten: Quartalszahlen in weniger als 5 Handelstagen (Kaufsperre). Trend nicht bestätigt: Kurs unter der 30-Wochen-Linie oder tiefere Hochs. Stopp unterschritten: Setup gescheitert."),
         ("Weg zur Zone", "So weit müsste der Kurs fallen, bis er die Oberkante der Einstiegszone erreicht. „in Zone“ = Kurs liegt bereits darin."),
         ("Chance/Risiko", "(Ziel − Ø Einstieg) ÷ (Ø Einstieg − Stopp), vor Kosten. Ziel = nächster Widerstand, sonst Kursziel-Median der Analysten. Ab 2 gilt ein Trade als lohnend."),
         ("Zahlen in", "Handelstage bis zu den nächsten Quartalszahlen.")]

def board():
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<div class="eyebrow">Swing-Tool</div><h1 class="ptitle">Swing-Kandidaten</h1>', unsafe_allow_html=True)
    market_bar()
    from swing_calc import board_rows; rows = board_rows()
    for r in rows: r["status"] = swing_status(r)
    LISTS = [("alle", "Alle", lambda r: True), ("zone", "In oder nahe Einstiegszone", lambda r: r["status"] in ("In Einstiegszone", "Nahe Einstiegszone")),
             ("warten", "Warten auf Rücksetzer", lambda r: r["status"] == "Warten auf Rücksetzer"), ("zahlen", "Zahlen in 7 Tagen", lambda r: r["n"] is not None and r["n"] <= 7)]
    LISTS = [L for L in LISTS if L[0] == "alle" or 0 < sum(L[2](r) for r in rows) < len(rows)]
    lab = {k_: f"{n} ({sum(f(r) for r in rows)})" for k_, n, f in LISTS}
    q = st.query_params.get("liste")
    if q in lab: st.session_state["bl"] = q
    elif st.session_state.get("bl") not in lab: st.session_state["bl"] = "alle"
    def _l(): st.query_params["liste"] = st.session_state.get("bl") or "alle"
    if len(LISTS) > 1:
        with st.container(key="tabs"):
            cur = st.segmented_control("Liste", list(lab), key="bl", format_func=lambda x: lab[x], on_change=_l, label_visibility="collapsed") or "alle"
    else: cur = "alle"
    f = next(f for k_, _, f in LISTS if k_ == cur)
    v = sorted([r for r in rows if f(r)], key=lambda r: (STATUS_ORDER.index(r["status"]), -(r["crv"] or 0)))
    if len(rows) > len(common.FEATURED):   # ganzer Pool: Schnellwahl, Suche, Filter, je 25 Zeilen
        common.quick_picks("swing")
        v, _tot = common.pool_filter(v, "sb", sym=lambda r: r["sym"], extra=("Setup", sorted({r["setup"] for r in v}), lambda r, x: r["setup"] == x))
    else: _tot = len(v)
    th = "".join(f'<th class="{"r" if n in ("Weg zur Zone", "Chance/Risiko", "Zahlen in") else ""}">{n}{" " + ii(t) if t else ""}</th>' for n, t in BCOLS)
    body = ""
    for i, r in enumerate(v, 1):
        a = lambda x, cls="": f'<td class="{cls}"><a class="rl" href="/swing-tool?t={r["sym"]}" target="_self">{x}</a></td>'
        crv_ = r["crv"]; ct = "pos" if crv_ and crv_ >= 2 else "warn" if crv_ and crv_ >= 1 else "neg"
        body += ("<tr>" + a(f'<span class="muted">{i}</span>') + a(f'<b>{r["c"]["name"]}</b> <span class="muted">{r["sym"]}</span>')
                 + a(f'<span title="{SETUP_RULE.get(r["setup"], "")}">{r["setup"]}</span>')
                 + a(f'<span class="spill {STATUS_TONE[r["status"]]}">{r["status"]}</span>')
                 + a("in Zone" if r["inzone"] else sgn(r["hi"] / r["price"] - 1), "r")
                 + a(f'<b class="tone-{ct}">{fnum(crv_, 1) if crv_ is not None else "k. A."}</b>', "r")
                 + a(f'<span class="{"tone-warn" if r["n"] is not None and r["n"] < 5 else ""}">{r["n"]} Tage</span>' if r["n"] is not None else "k. A.", "r") + "</tr>")
    st.markdown(f'<table class="tbl btb"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>', unsafe_allow_html=True)
    if not v: st.markdown('<div class="bfoot">Keine Treffer für diese Auswahl.</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="bfoot">{len(v)} von {fnum(_tot, 0)} Treffern angezeigt · {fnum(len(rows), 0)} von {fnum(META["pool_n"], 0)} Pool-Titeln mit Einstiegsplan · Stand {fdate(META["pool_asof"])}</div>', unsafe_allow_html=True)
    common.more("sb", _tot)
    board_extras(v or rows)
    footer2(META)

def watch_rows(sym):
    """Merkliste mit Auslösern (W13): im Abendlauf gegen den Schlusskurs geprüft. Es wird nichts versendet."""
    c = CASES[sym]; px = prices(sym); d = px.iloc[-1]; s = SW["stocks"][sym]; lv, lo, hi, avg = levels(c); stop = plan_of(sym)["stop"]
    out = [("Berührt Stufe 1", hi, d.low <= hi, "Tagestief ≤ Stufe 1"), ("Schluss über 20-Tage-Hoch", s["hi20_prev"], d.close > s["hi20_prev"], "Ausbruch"),
           ("Schluss unter Stopp", stop, d.close < stop, "Setup gescheitert"), ("Berührt 50-Tage-Linie", c["sma50"], d.low <= c["sma50"] <= d.high, "Test der Linie")]
    return [(sym, n, lvl, hit, why, d.close / lvl - 1) for n, lvl, hit, why in out]

def board_extras(rows):
    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    with st.expander(f"Zahlentermine im ganzen Pool, nächste 7 Handelstage ({len(SW['earn7'])} Titel)"):
        tb = [{"Aktie": f'<b>{x["sym"]}</b> <span class="muted">{x["name"]}</span>', "In Handelstagen": f'<span class="{"dn" if x["n"] < 5 else ""}">{x["n"]}</span>', } for x in SW["earn7"][:15]]
        st.markdown(table(tb, list(tb[0]), align={"In Handelstagen": "r"}), unsafe_allow_html=True)
        note(f"Stand Abendlauf {fdate(SW['asof'])}; die nächsten 15 nach Termin. Unter 5 Handelstagen gilt die Kaufsperre.")
    with st.expander("Sektor-Rotation (Rotationsdiagramm der elf S&P-Sektoren)"):
        fig = go.Figure(); demo = {CASES[r["sym"]]["sector"] for r in rows}
        ETF_EN = {"XLK": "Information Technology", "XLC": "Communication Services", "XLY": "Consumer Discretionary"}
        for e, v in SW["rrg"].items():
            tr = v["trail"]; xs, ys = [x[1] for x in tr], [x[2] for x in tr]; hl = ETF_EN.get(e) in demo
            col = "#337ab7" if hl else "#98a2b3"
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=col, width=2 if hl else 1), hoverinfo="skip", showlegend=False))
            fig.add_trace(go.Scatter(x=[xs[-1]], y=[ys[-1]], mode="markers+text", marker=dict(color=col, size=10), text=[e], textposition="top center",
                                     textfont=dict(size=12, color="#1d2939"), showlegend=False,
                                     hovertemplate=f"{v['name']} ({e})<br>Relative Stärke %{{x:,.1f}}<br>Momentum der relativen Stärke %{{y:,.1f}}<br>1 Monat {sgn(v['perf1m'])} · 3 Monate {sgn(v['perf3m'])}<extra></extra>"))
        allx = [x[1] for v in SW["rrg"].values() for x in v["trail"]]; ally = [x[2] for v in SW["rrg"].values() for x in v["trail"]]
        rx = max(abs(min(allx) - 100), abs(max(allx) - 100)) * 1.15; ry = max(abs(min(ally) - 100), abs(max(ally) - 100)) * 1.15
        for (x0, y0, t, col) in ((100 + rx * .55, 100 + ry * .9, "führend", POS), (100 + rx * .55, 100 - ry * .9, "schwächer werdend", WARN),
                                 (100 - rx * .55, 100 - ry * .9, "nachhinkend", NEG), (100 - rx * .55, 100 + ry * .9, "sich verbessernd", BLUE)):
            fig.add_annotation(x=x0, y=y0, text=t, showarrow=False, font=dict(color=col, size=13))
        fig.add_hline(y=100, line=dict(color="#d0d7e2")); fig.add_vline(x=100, line=dict(color="#d0d7e2"))
        fig.update_layout(**plot_layout(height=480, margin=dict(l=8, r=8, t=10, b=8), xaxis=dict(range=[100 - rx, 100 + rx], title="Relative Stärke zum S&P 500 (100 = neutral)", gridcolor="#eef2f6"),
                                        yaxis=dict(range=[100 - ry, 100 + ry], title="Momentum der relativen Stärke (4 Wochen)", gridcolor="#eef2f6")))
        pchart(fig, config=PLOT_CFG, key="rrg")
        note("Eigene Näherung an das Relative-Rotation-Graph-Prinzip: Relative Stärke = Sektor-ETF ÷ S&P 500 relativ zu seinem 10-Wochen-Schnitt, Momentum = Veränderung dieses Verhältnisses über 4 Wochen. "
             "Linie = Spur der letzten 12 Wochen. Blau = Sektoren der ausgewählten Aktien. Kürzel: SPDR-Sektor-ETFs (XLK Technologie, XLC Kommunikation, XLY Zyklischer Konsum, XLP Basiskonsum, XLV Gesundheit, XLF Finanzen, XLI Industrie, XLE Energie, XLB Grundstoffe, XLU Versorger, XLRE Immobilien).")
    with st.expander("Korrelation der Kandidaten (Klumpenrisiko)"):
        sy = [r["sym"] for r in rows][:10]
        M = pd.DataFrame({s_: prices(s_).set_index("date").close for s_ in sy}).tail(253).pct_change().corr().round(3).values.tolist()
        fig = go.Figure(go.Heatmap(z=M, x=sy, y=sy, zmin=-1, zmax=1, colorscale=[[0, "#c0322b"], [.5, "#ffffff"], [1, "#337ab7"]], text=[[fnum(v, 2) for v in r_] for r_ in M],
                                   texttemplate="%{text}", hovertemplate="%{y} / %{x}: %{text}<extra></extra>", showscale=False))
        fig.update_layout(**plot_layout(height=360, margin=dict(l=8, r=8, t=10, b=8), yaxis=dict(autorange="reversed")))
        l, r = st.columns([1, 1.2], gap="large")
        with l: pchart(fig, config=PLOT_CFG, key="corr")
        with r: note("Korrelation der Tagesrenditen über ein Jahr bis zum Stichtag. Werte nahe 1 bedeuten: Die Titel bewegen sich fast gleich, zwei Swings darin sind fast ein doppelter Einsatz auf dasselbe Risiko.")

# ================================================================ (B) Aktie mit Reitern
def lv_row(col, name, val, price, cur=False):
    return (f'<div class="sw-lv{" cur" if cur else ""}"><span class="n"><i style="background:{col}"></i>{name}</span>'
            f'<span><b>{fnum(val)}</b><small>{sgn(val / price - 1) if not cur else "aktuell"}</small></span></div>')

def t_case(c, sym):
    """Überblick (Swing): ruhiger Einstieg in den Trade für Außenstehende. Langfristiges steht im Bereich Investment."""
    r = row(sym); r["status"] = swing_status(r); lv, lo, hi, avg = levels(c); n = r["n"]; tl, tok = trend_label(c)
    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
    zst = "p" if r["inzone"] else ("o" if r["dist"] > 0 else "w")
    blk = c.get("stage_block")
    steps = [("Trend", "Aufwärtstrend bestätigt" if tok else (f"Phase {c.get('stage')}: gesperrt" if blk else tl), "Phase 3/4 = harte Sperre" if blk else "30-Wochen-Linie und Hochs/Tiefs", "p" if tok else ("f" if blk else "w")),
             ("Setup", r["setup"], (f'{r["plan"]["touches"]} Berührungen' + (f' · {", ".join(str(x) for x in r["plan"]["conf"])}-Tage-Linie in der Zone' if r["plan"]["conf"] else "")) if r["plan"]["touches"] else "steigende 50-Tage-Linie", "p"),
             ("Einstiegszone", "Kurs in der Zone" if r["inzone"] else f"noch {sgn(hi / c['price'] - 1)} bis zur Zone", f"Zone {fnum(lo)} – {fnum(hi)}", zst),
             ("Timing", f"Zahlen am {fdate(c['next_earnings'])}", f"in {n} Handelstagen" + (", Kaufsperre" if n is not None and n < 5 else ""), "w" if n is not None and n < 5 else "p")]
    lab = {"p": "erfüllt", "w": "mit Vorbehalt", "f": "nicht erfüllt", "o": "offen"}
    st.markdown('<div class="csteps">' + "".join(f'<div class="cs {t}"><span class="n">Schritt {i + 1}</span><span class="h">{a}</span><span class="v">{b}</span><span class="s">{d}</span><span class="b">{lab[t]}</span></div>'
                for i, (a, b, d, t) in enumerate(steps)) + "</div>", unsafe_allow_html=True)
    plan_strip(c, sym)
    with st.container(key="to_invest_row", horizontal=True, vertical_alignment="center", gap="small"):
        st.markdown('<span class="muted" style="font-size:13.5px">Langfristige Sicht mit Tranchenplan, Positionsgröße und Stressszenario:</span>', unsafe_allow_html=True)
        st.page_link(common.PAGES["invest"], label="Investment", query_params={"t": sym})

import re as _re
_DE = [(r"SMA50/200-Pullback", "Rücksetzer an 50- oder 200-Tage-Linie"), (r"Composite p(\d+) im Typ \(([^)]+)\)", r"Qualitäts-Perzentil \1 in der Vergleichsgruppe \2"), (r"\bUniversum\b", "Gesamtpool"), (r"\bPlattform\b", "Plattformen"),
       (r"Basis-Retest", "Rücktest der Ausbruchsbasis"), (r"\bPullback\b", "Rücksetzer"), (r"\bEarnings\b", "Zahlen"), (r"\bStage 2\b", "Aufwärtstrend (Phase 2)"),
       (r"SMA(\d+)", r"\1-Tage-Linie"), (r"EMA(\d+)/(\d+)", r"\1-/\2-Tage-Durchschnitt"), (r"EMA(\d+)", r"\1-Tage-Durchschnitt"), (r"\b30W\b", "30-Wochen-Linie"),
       (r"Basis-CAGR 5 J\.", "Basisrendite 5 J."), (r"Konservativ \(p25\) CAGR 5 J\.", "konservative Rendite 5 J."), (r"\bCAGR\b", "Rendite p. a."),
       (r"Impl\. Wachstum als Base-Rate-Perzentil", "eingepreistes Wachstum im historischen Vergleich"), (r"\bBase-Rate\b", "Basisrate"), (r"\bGate:", "Prüfgrenze:"),
       (r"Wertfalle/Datenfehler prüfen", "mögliche Wertfalle oder Datenfehler"), (r"Capex-Spitze", "Investitionsspitze"), (r"\bCapex\b", "Investitionen"), (r"\bD&A\b", "Abschreibungen"),
       (r"\bOCF\b", "operativer Cashflow"), (r"\bFCF\b", "freier Cashflow"), (r"\bGJ\b", "Geschäftsjahr"), (r"\bMrd\b", "Mrd. USD"),
       (r"Funds payable to customers", "Kundengelder"), (r"Amounts payable due to credit and debit card transactions", "Verbindlichkeiten aus Kartenzahlungen"),
       (r"Communication Services", "Kommunikation"), (r"Consumer Discretionary", "Zyklischer Konsum"), (r"\(Rang (\d+)\.0\)", r"(Rang \1 von 11)"), (r"→ ½ Größe", "→ halbe Positionsgröße"),
       (r"\(<5\)", "(weniger als 5)"), (r" \([A-Z]+_10-K_[\d-]+\.html\)", ""), (r"Kaufzone bei", "Einstiegszone bei"), (r"⚠ ?", ""), (r"\bvs\.", "gegenüber"), (r"(\d)×", r"\1-fach")]
def de_txt(t):
    t = plain(t)
    for a, b in _DE: t = _re.sub(a, b, t)
    t = _re.sub(r"(\d{4})-(\d{2})-(\d{2})", r"\3.\2.\1", t)
    t = _re.sub(r"(?<![\d.])(-?)(\d+)\.(\d+) %", lambda m: ("−" if m.group(1) else "") + f"{float(m.group(2) + '.' + m.group(3)):.1f}".replace(".", ",") + " %", t)
    t = _re.sub(r"(?<![\d.])(\d+)\.(\d+)(?![\d.])", lambda m: f"{float(m.group(0)):.2f}".replace(".", ",") if len(m.group(2)) > 2 or "." in m.group(0) else m.group(0), t)
    return t

def fair_range(c):
    """Faire Spanne = pessimistisches bis optimistisches Szenario der Bewertung v3 (wie Aktienanalyse und Investment)."""
    import fairvalue; v = fairvalue.get(c["symbol"]); return (v["pess"], v["opt"]) if v else (None, None)

def trend_label(c):
    """Klare Kurzform der Trendprüfung statt 'Phase 2, Trend nicht intakt'."""
    t = c.get("stage_text") or ""
    if c.get("stage") == 2 and "kein Stage 2" not in t: return "Aufwärtstrend intakt", True
    if "Abwärtsstruktur" in t: return "Tiefere Hochs trotz steigender 30-Wochen-Linie", False
    if c.get("stage_block"): return {3: "Phase 3 (Topbildung): Kurs unter steigender 30-Wochen-Linie", 4: "Phase 4 (Abwärtstrend)"}.get(c.get("stage"), "gesperrt"), False
    if "unter 30W" in t: return "Kurs unter der 30-Wochen-Linie", False
    if "Steigung" in t: return "30-Wochen-Linie steigt nur schwach", False
    return {1: "Bodenbildung", 3: "Topbildung", 4: "Abwärtstrend"}.get(c.get("stage"), "Trend unklar"), False

def pstrip(cells):
    st.markdown(f'<div class="pstrip" style="grid-template-columns:repeat({len(cells)},minmax(0,1fr))">' + "".join(f'<div><span class="l">{a}</span><span class="v{" tone-" + t if t else ""}">{b}</span><span class="s">{c_}</span></div>' for a, b, c_, t in cells) + "</div>", unsafe_allow_html=True)

def _pl(sym):
    from swing_levels import analyse
    an = analyse(sym); return an, an["plan"]

def plan_strip(c, sym):
    an, p = _pl(sym); price = an["price"]; cur = c["currency"]
    cells = [("Einstieg", fnum(p["entry"]), f"Zone {fnum(p['lo'])} – {fnum(p['hi'])}", None),
             ("Stopp", fnum(p["stop"]), f"{sgn(p['stop'] / p['entry'] - 1)} · {fnum(p['stop_atr'], 1)} ATR unter der Zone", "neg"),
             ("Ziel 1", fnum(p["t1"]), f"{sgn(p['t1'] / p['entry'] - 1)} · {p['t1src']}", "pos"),
             ("Chance/Risiko", "gesperrt" if c.get("stage_block") else fnum(p["crv"], 1), f"Phase {c.get('stage')}: kein Einstieg" if c.get("stage_block") else "vor Kosten, bis Ziel 1",
              None if c.get("stage_block") else ("pos" if p["crv"] >= 2 else "warn" if p["crv"] >= 1 else "neg")),
             ("Abstand zur Zone", "in Zone" if p["inside"] else sgn(price / p["hi"] - 1), "Schlusskurs zur Oberkante", None)]
    pstrip(cells)

ZONE_INFO = ("Erkennung: bestätigte Swing-Hochs und -Tiefs (5 Handelstage links und rechts) der letzten 2 Jahre. Hochs und Tiefs werden gemeinsam nach Preis gruppiert "
             "(Rollentausch: alter Widerstand wird Unterstützung), solange sie höchstens 0,6 ATR vom Zonenmittel entfernt liegen. Breite mindestens 0,5, höchstens 1,5 ATR. "
             "Zone ab 2 Berührungen. Stärke = Berührungen gewichtet nach Aktualität (Halbwertszeit 6 Monate) und Volumen am Wendetag, plus gleitende Durchschnitte (20/50/100/200 Tage) in der Zone. "
             "ATR = durchschnittliche Tagesspanne über 14 Tage. Gleiche Regeln für jede Aktie.")

def t_chart(c, sym):
    import swing_chart
    an, p = _pl(sym); price = an["price"]
    plan_strip(c, sym)
    swing_chart.render(prices(sym), an, p, height=540, cur=c["currency"], key=f"sc_{sym}")
    st.markdown('<div class="h2">Unterstützungen und Widerstände ' + ii(ZONE_INFO) + '</div>', unsafe_allow_html=True)
    MA_N = {20: "20-Tage", 50: "50-Tage", 100: "100-Tage", 200: "200-Tage"}
    res = [z for z in an["res"] if z["lo"] > price][:3][::-1]; sup = [z for z in an["sup"] if z["hi"] < price or z is p["zone"]][:4]
    rows = []
    for z in res + sup:
        ent = p and z is p["zone"]
        kind = "Einstiegszone" if ent else ("Widerstand" if z["lo"] > price else "Unterstützung")
        tone = "pos" if ent else ("neg" if kind == "Widerstand" else "")
        rows.append({"Art": f'<span class="spill {tone}">{kind}</span>', "Zone": f'{fnum(z["lo"])} – {fnum(z["hi"])}',
                     "Abstand": "aktuell" if z["lo"] <= price <= z["hi"] else sgn(((z["lo"] if z["lo"] > price else z["hi"]) / price) - 1),
                     "Berührungen": fnum(z["touches"], 0), "Zuletzt": fdate(z["last"]) if z.get("last") else "–",
                     "Linien in der Zone": ", ".join(MA_N[m] for m in z["conf"]) or "–", "Stärke": _bar(z["score"])})
    rows.insert(len(res), {"Art": "<b>Schlusskurs</b>", "Zone": f"<b>{fnum(price)}</b>", "Abstand": "", "Berührungen": "", "Zuletzt": fdate(an["asof"]), "Linien in der Zone": "", "Stärke": ""})
    st.markdown(table(rows, list(rows[0]), align={"Abstand": "r", "Berührungen": "r"}), unsafe_allow_html=True)
    ma = an["mas"]
    kpis([k(f"{MA_N[n]}-Linie", fnum(d["v"]), f'Kurs {sgn(price / d["v"] - 1)} · Linie {"steigend" if d["rising"] else "fallend"}', "pos" if price > d["v"] else "neg") for n, d in ma.items()]
         + [k("ATR 14 Tage", fnum(an["atr"]), f'{fpct(an["atr_pct"], 1)} vom Kurs', None, "Durchschnittliche wahre Tagesspanne (Wilder, 14 Tage). Maßstab für Zonenbreite und Stoppabstand.")])

def _bar(sc):
    w = max(6, min(100, sc / 4 * 100))
    return f'<span style="display:inline-block;width:70px;height:6px;background:#eef2f6;border-radius:3px;vertical-align:middle"><i style="display:block;width:{w:.0f}%;height:6px;background:#337ab7;border-radius:3px"></i></span>'

PLAN_INFO = ("Eine Einstiegszone statt drei Stufen: Bei einem Swing-Trade mit Hebel bestimmt der Abstand zum Stopp Positionsgröße und Knock-out. Drei gestaffelte Käufe verschieben den "
             "Durchschnittspreis, verkleinern den Abstand zum Stopp und machen Chance/Risiko erst nach der Ausführung bekannt. Mit einer Zone stehen Einstieg, Stopp und Risiko vor dem Kauf fest. "
             "Gekauft wird per Limit an der Oberkante der nächsten belastbaren Unterstützung (mindestens 2 Berührungen oder steigende 50/100/200-Tage-Linie in der Zone, höchstens 4 ATR bzw. 15 % unter dem Kurs). "
             "Eine zweite Tranche gibt es nur nach weiteren 5 % Rückgang und nur, wenn sie mindestens 0,5 ATR über dem Stopp liegt.")
STOP_INFO = ("Stopp = tiefster Punkt der Einstiegszone bzw. ihres tiefsten Wendetiefs minus 1 ATR. Damit liegt er logisch unter dem Swing-Tief, das die Zone bildet, und außerhalb des normalen "
             "Tagesrauschens. Fiele er in eine tiefere Unterstützung, liegt er stattdessen 0,5 ATR unter deren Unterkante. Ein Schlusskurs darunter beendet den Trade. Knock-out-Vorschlag = Stopp minus 1 weitere ATR als Puffer für Kurslücken.")

def _ev_info(ev):
    v = ev.get("val") or {}
    return (f"Gemessen an {fnum(ev['test']['n'], 0)} historischen Setups derselben Gruppe ({ev['cell']}), Testzeitraum 2016–2019, mit genau dieser Stopp-, Ziel- und Knock-out-Regel. "
            "Gruppe = Volatilitätsdrittel (ATR in % vom Kurs) und Lage zur 200-Tage-Linie. Einstieg per Limit an der Zonen-Oberkante, Ausstieg am Stopp oder an Ziel 1, spätestens nach 6 Monaten. "
            "Gewinnquote = Anteil mit Gewinn; Erwartungswert in R = durchschnittlicher Ertrag in Vielfachen des Risikos (Einstieg − Stopp), vor Kosten. "
            f"Kontrolle im Validierungszeitraum 2020–2021 ({fnum(v.get('n'), 0)} Setups): Stopp {fpct(v.get('stop'), 0)}, Ziel 1 {fpct(v.get('t1'), 0)}, Erwartungswert {fnum(v.get('er'), 2)} R. "
            "Kurze Haltedauern bedeuten viel Zufall im Einzelfall: Die Werte gelten für viele Trades, nicht für diesen einen.")

def ev_strip(an):
    from stop_evidence import lookup
    ev = lookup(an)
    if not ev or not ev.get("test"): return
    t = ev["test"]
    st.markdown('<div class="h2">Historische Trefferquoten ' + ii(_ev_info(ev)) + '</div>', unsafe_allow_html=True)
    kpis([k("Stopp erreicht", fpct(t["stop"], 0), ev["cell"], "neg"), k("Ziel 1 erreicht", fpct(t["t1"], 0), "vor dem Stopp", "pos"),
          k("Knock-out berührt", fpct(t["ko"], 0), "vor Ziel 1"), k("Gewinnquote", fpct(t["win"], 0), "Anteil mit Gewinn"),
          k("Erwartungswert", f'{fnum(t["er"], 2)} R', "je Trade, vor Kosten", "pos" if t["er"] > 0 else "neg"), k("Haltedauer", f'{fnum(t["days_med"], 0)} Tage', "Median, Handelstage")])

def t_plan(c, sym):
    an, p = _pl(sym); price = an["price"]; m = c["market"]; cur = c["currency"]
    st.markdown('<div class="h2">Einstiegsplan ' + ii(PLAN_INFO) + '</div>', unsafe_allow_html=True)
    two = p["second"] is not None
    z = p["zone"]; MA_N = {20: "20-Tage", 50: "50-Tage", 100: "100-Tage", 200: "200-Tage"}
    why = (f'{z["touches"]} Berührungen, zuletzt {fdate(z["last"])}' if z.get("last") else "steigende 50-Tage-Linie") + (f' · {", ".join(MA_N[x] for x in z["conf"])}-Linie in der Zone' if z["conf"] and z.get("last") else "")
    cards = [("Einstiegszone", f'{fnum(p["lo"])} – {fnum(p["hi"])}', why, "#1e7b45"),
             ("Kauf-Limit", fnum(p["entry"]), ("Kurs liegt in der Zone" if p["inside"] else f'Oberkante der Zone, {sgn(p["entry"] / price - 1)} vom Kurs'), "#1e7b45"),
             ("Stopp (Schlusskurs)", fnum(p["stop"]), f'{sgn(p["stop"] / p["entry"] - 1)} vom Einstieg · {fnum(p["stop_atr"], 1)} ATR unter der Zone', "#c0322b"),
             ("Ziel 1", fnum(p["t1"]), f'{sgn(p["t1"] / p["entry"] - 1)} · {p["t1src"]}', "#337ab7")]
    st.markdown('<div class="steps" style="grid-template-columns:repeat(4,minmax(0,1fr))">' + "".join(
        f'<div class="step" style="border-top:4px solid {col}"><div class="d" style="font-weight:600;color:#344054">{a}</div><div class="pr">{b}</div><div class="d">{d}</div></div>' for a, b, d, col in cards) + '</div>', unsafe_allow_html=True)
    kpis([k("Risiko je Aktie", fnum(p["risk"]), f'{fpct(p["risk_pct"], 1)} vom Einstieg', None, STOP_INFO),
          k("Chance/Risiko", fnum(p["crv"], 1), "bis Ziel 1, vor Kosten", "pos" if p["crv"] >= 2 else "warn" if p["crv"] >= 1 else "neg"),
          k("Ziel 2", fnum(p["t2"]) if p["t2"] else "–", f'{sgn(p["t2"] / p["entry"] - 1)} · nächster Widerstand' if p["t2"] else "kein weiterer Widerstand"),
          k("Knock-out-Vorschlag", fnum(p["ko"]), f'{sgn(p["ko"] / p["entry"] - 1)} · Hebel {fnum(p["entry"] / (p["entry"] - p["ko"]), 1)}×', None, "Stopp minus 1 ATR."),
          k("Positionsgröße", fpct(m["size_factor"], 0), "der Normalgröße (Marktampel)", "warn" if m["size_factor"] < 1 else None)])
    ev_strip(an)
    h2("Tranchen")
    t2p = p["entry"] * .95
    rows = [{"Tranche": "1", "Auslöser": "Limit an der Zonen-Oberkante" if not p["inside"] else "Kurs in der Zone", "Kurs": fnum(p["entry"]), "Anteil": "⅔ der Position" if two else "ganze Position",
             "Abstand zum Stopp": sgn(p["stop"] / p["entry"] - 1)},
            {"Tranche": "2 (optional)", "Auslöser": "weitere 5 % Rückgang, Zone hält", "Kurs": fnum(t2p) if two else f'{fnum(t2p)} liegt unter dem Stopp' if t2p <= p["stop"] else f'{fnum(t2p)} zu nah am Stopp',
             "Anteil": "⅓ der Position" if two else "entfällt", "Abstand zum Stopp": sgn(p["stop"] / t2p - 1) if two else "–"}]
    st.markdown(table(rows, list(rows[0]), align={"Kurs": "r", "Abstand zum Stopp": "r"}), unsafe_allow_html=True)
    h2("Zeitplan", "Kaufsperre: kein Neukauf in den 5 Handelstagen vor Quartalszahlen")
    e = pd.Timestamp(c["next_earnings"]); asof = pd.Timestamp(c["asof"]); n = tdays(c["asof"], c["next_earnings"])
    blk = (e - pd.offsets.BDay(5)); after = e + pd.offsets.BDay(1)
    ev = sorted([(asof, "Datenstand", ""), (blk, "Kaufsperre beginnt", "blk"), (e, "Quartalszahlen", "blk"), (after, "Plan wieder aktiv, Zone neu prüfen", "")], key=lambda x: x[0])
    st.markdown('<div class="tl">' + "".join(f'<div class="{cl}"><i></i><b>{fdate(str(d.date()))}</b>{t}</div>' for d, t, cl in ev) + '</div>', unsafe_allow_html=True)
    h2("Bedingungen für die Ausführung")
    chk = [("p" if x["status"] == "pass" else "f" if x["status"] == "fail" else "i", de_txt(x["text"]).replace("≥50 %", "mindestens 50 %"), de_txt(x["value"]).replace(" vs ", " zu ")) for x in m["checks"]]
    sc = m.get("sector") or {}
    if sc: chk.append(("p" if sc.get("ok") else "f", f"Sektor {de_txt(sc.get('name', ''))} ({sc.get('etf', '')}) relativ stark", f"Rang {fnum(sc.get('rank'), 0)} von 11"))
    chk.append(("p" if trend_ok(c) else "f", "Aufwärtstrend (Phase 2)", trend_label(c)[0]))
    chk.append(("p" if p["crv"] >= 2 else "f", "Chance/Risiko mindestens 2", fnum(p["crv"], 1)))
    chk.append(("f" if n is not None and n < 5 else "p", "Kein Quartalstermin in den nächsten 5 Handelstagen", f"{n} Handelstage"))
    st.markdown('<div class="sw-panel">' + "".join(f'<div class="chk"><span class="m {s}">{"✓" if s == "p" else "✕" if s == "f" else "i"}</span><span>{t}</span><span class="v">{v}</span></div>' for s, t, v in chk) + '</div>', unsafe_allow_html=True)

LEV_INFO = ("Gleiches Risikobudget für jede Zeile: Die Stückzahl wird so gewählt, dass der Verlust am Stopp vor Kosten dem Budget entspricht. Turbo-Long: Preis ≈ (Kurs − Knock-out) × Bezugsverhältnis, "
            "Finanzierung ≈ Knock-out × Satz × Tage ÷ 365 × Bezugsverhältnis. Ein Hebel ist nur möglich, wenn der Knock-out mindestens 0,5 ATR unter dem Stopp liegt. "
            "Verlust bei Knock-out = gesamter Einsatz (Kurslücke über Stopp und Knock-out). Illustratives Rechenmodell, keine Produktempfehlung.")

def t_lever(c, sym):
    an, p = _pl(sym); cur = c["currency"]; a = an["atr"]
    with st.container(key="sw_inputs"):
        c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, .4], gap="small", vertical_alignment="bottom")
        acct = de_in(c1, f"Kontogröße ({cur})", 25000, f"acct_{sym}", 0, 1000, 1e8)
        rp = de_in(c2, "Risiko je Trade (%)", 1.0, f"rp_{sym}", 1, 0.1, 10)
        days = de_in(c3, "Haltedauer (Tage)", 20, f"days_{sym}", 0, 1, 365)
        fin = de_in(c4, "Finanzierung p. a. (%)", round(SW["tbill3m"] * 100 + 2.5, 2), f"fin_{sym}", 2, 0, 30)
        c5.markdown(inote(LEV_INFO, "Rechenweg"), unsafe_allow_html=True)
    with st.expander("Kosten und Bezugsverhältnis"):
        c1, c2, c3, c4 = st.columns(4, gap="medium")
        sprT = de_in(c1, "Spread Turbo (%)", 0.2, f"sprT_{sym}", 2, 0, 10)
        sprA = de_in(c2, "Spread Aktie (%)", 0.05, f"sprA_{sym}", 2, 0, 10)
        fee = de_in(c3, f"Ordergebühr ({cur})", 1.0, f"fee_{sym}", 2, 0, 1000)
        ratio = de_in(c4, "Bezugsverhältnis", 0.1, f"ratio_{sym}", 2, 0.001, 1)
    entry, stop, target = p["entry"], p["stop"], p["t1"]
    sf = c["market"]["size_factor"]; budget = acct * rp / 100 * sf
    st.markdown(f'<p class="muted" style="margin:6px 0 10px">Risikobudget <b>{fprice(budget, cur, 0)}</b> · Einstieg <b>{fnum(entry)}</b> · Stopp <b>{fnum(stop)}</b> · Ziel 1 <b>{fnum(target)}</b></p>', unsafe_allow_html=True)
    prods = [("Aktie", 1.0, None)] + [(f"Turbo {fnum(L, 0)}×", L, entry * (1 - 1 / L)) for L in (2, 3, 5, 10)] + [("Turbo, Knock-out-Vorschlag", entry / (entry - p["ko"]), p["ko"])]
    prods.sort(key=lambda x: x[1])
    rows, chart = [], []
    for name, L, ko in prods:
        if ko is None: R = turbo_model(entry, stop, target, 0, ratio, fin / 100, sprA / 100, int(days), fee, budget, "Aktie")
        elif ko > stop - .5 * a:
            rows.append({"Produkt": name, "Hebel": f"{fnum(L, 1)}×", "Knock-out": fnum(ko), "Abstand Knock-out": sgn(ko / entry - 1),
                         "Stück": "–", "Einsatz": "–", "Am Ziel": "–", "Am Stopp": "–", "Bei Knock-out": "–", "Kosten": "–",
                         "Chance/Risiko nach Kosten": '<span class="spill neg">Knock-out zu nah am Stopp</span>'}); continue
        else: R = turbo_model(entry, stop, target, ko, ratio, fin / 100, sprT / 100, int(days), fee, budget, "Turbo-Long")
        if not R or R.get("err") or R["n"] <= 0: continue
        g, l = R["gain"] - R["cost"], -(R["loss"] + R["cost"]); rn = R["rr_net"] or 0; tone = "pos" if rn >= 2 else "warn" if rn >= 1 else "neg"
        kov = -(R["invest"] + R["cost"] - R["fin"]) if ko else None
        rows.append({"Produkt": f"<b>{name}</b>", "Hebel": f"{fnum(R['lev'], 1)}×", "Knock-out": fnum(ko) if ko else "–", "Abstand Knock-out": sgn(ko / entry - 1) if ko else "–",
                     "Stück": fnum(R["n"], 0), "Einsatz": fprice(R["invest"], cur, 0), "Am Ziel": f'<span class="up">{fprice(g, cur, 0)}</span>',
                     "Am Stopp": f'<span class="dn">{fprice(l, cur, 0)}</span>', "Bei Knock-out": f'<span class="dn">{fprice(kov, cur, 0)}</span>' if ko else "–",
                     "Kosten": fprice(R["cost"], cur, 0), "Chance/Risiko nach Kosten": f'<b class="tone-{tone}">{fnum(rn, 2)}</b> <span class="muted">vor Kosten {fnum(R["rr_gross"], 2)}</span>'})
        chart.append((name.replace("Turbo, Knock-out-Vorschlag", "Turbo KO-Vorschlag"), g, l, R["cost"], R["invest"]))
    h2("Szenarien je Hebel")
    st.markdown(table(rows, list(rows[0]), align={x: "r" for x in list(rows[0])[1:]}), unsafe_allow_html=True)
    if not chart: return
    l, r = st.columns([1.3, 1], gap="large")
    with l:
        st.markdown('<div class="h2" style="margin-top:12px">Ergebnis nach Kosten am Ziel und am Stopp</div>', unsafe_allow_html=True)
        fig = go.Figure()
        ys = [x[0] for x in chart]
        fig.add_bar(y=ys, x=[x[1] for x in chart], orientation="h", name="am Ziel 1", marker_color=POS, text=[fprice(x[1], cur, 0) for x in chart], textposition="outside", cliponaxis=False,
                    hovertemplate="%{y}: am Ziel %{text}<extra></extra>")
        fig.add_bar(y=ys, x=[x[2] for x in chart], orientation="h", name="am Stopp", marker_color=NEG, text=[fprice(x[2], cur, 0) for x in chart], textposition="outside", cliponaxis=False,
                    hovertemplate="%{y}: am Stopp %{text}<extra></extra>")
        mx = max(max(abs(x[1]), abs(x[2])) for x in chart) * 1.35
        fig.update_layout(**plot_layout(height=70 + 52 * len(chart), barmode="relative", showlegend=True, legend=dict(orientation="h", y=-0.12, x=0), margin=dict(l=8, r=8, t=6, b=8),
                                        xaxis=dict(range=[-mx, mx], gridcolor="#f2f4f7", tickformat=",.0f", zeroline=True, zerolinecolor="#98a2b3"), yaxis=dict(autorange="reversed")))
        pchart(fig, config=PLOT_CFG, key=f"lev_{sym}")
    with r:
        st.markdown('<div class="h2" style="margin-top:12px">Kosten je Variante</div>', unsafe_allow_html=True)
        fc = go.Figure(go.Bar(y=[x[0] for x in chart], x=[x[3] for x in chart], orientation="h", marker_color="#9ec5e8", text=[f'{fprice(x[3], cur, 0)} · {fpct(x[3] / budget, 0)} des Risikos' for x in chart],
                              textposition="outside", cliponaxis=False, hovertemplate="%{y}: %{text}<extra></extra>"))
        fc.update_layout(**plot_layout(height=70 + 52 * len(chart), showlegend=False, margin=dict(l=8, r=8, t=6, b=8), xaxis=dict(range=[0, max(x[3] for x in chart) * 1.9], gridcolor="#f2f4f7", tickformat=",.0f"),
                                       yaxis=dict(autorange="reversed", showticklabels=True)))
        pchart(fc, config=PLOT_CFG, key=f"cost_{sym}")

def t_earn(c, sym):
    an, p = _pl(sym); s = SW["stocks"][sym]; n = tdays(c["asof"], c["next_earnings"]); im = (SW.get("implied") or {}).get(sym)
    re_ = [list(x) + [None] * (5 - len(x)) for x in s["reactions"]]
    beats = [x for x in re_ if x[2] is not None and x[2] > 0]; miss = [x for x in re_ if x[2] is not None and x[2] <= 0]
    avg = lambda L: sum(x[1] for x in L) / len(L) if L else None
    last8 = re_[-8:]; absmv = sum(abs(x[1]) for x in last8) / len(last8) if last8 else None
    cells = [("Nächste Zahlen", fdate(c["next_earnings"]), f"in {n} Handelstagen" + (", Kaufsperre aktiv" if n is not None and n < 5 else ""), "neg" if n is not None and n < 5 else None)]
    if im: cells.append(("Erwartete Bewegung", f"±{fpct(im['move'], 1)}", f"Optionen, Verfall {fdate(im['expiry'])}", None))
    if absmv is not None:
        cells.append(("Ø Kurssprung", f"±{fpct(absmv, 1)}", f"letzte {len(last8)} Quartale", None))
        ratio_ = absmv / p["risk_pct"] if p else None
        if ratio_: cells.append(("Sprung zum Stoppabstand", f"{fnum(ratio_, 1)}×", f"Stopp {fpct(p['risk_pct'], 1)} unter Einstieg", "neg" if ratio_ >= 1 else "pos"))
    bc = _beat_cell(sym, beats, miss, "")
    if bc[1] != "k. A.": cells.append(("Erwartung übertroffen", bc[1], "Quartale" + (f", Quote {fpct(int(bc[1].split()[0]) / max(1, int(bc[1].split()[-1])), 0)}" if bc[1][0].isdigit() else ""), bc[3]))
    if beats and miss: cells.append(("Ø Reaktion", f'{sgn(avg(beats))} / {sgn(avg(miss))}', "übertroffen / verfehlt", None))
    pstrip(cells)
    if not re_: return
    qs = QUARTERS.get(sym, [])
    def q_at(d):
        prev = [q for q in qs if q["end"] < d and (pd.Timestamp(d) - pd.Timestamp(q["end"])).days <= 100]; return prev[-1] if prev else None
    l, r = st.columns([1.2, 1], gap="large")
    with l:
        st.markdown('<div class="h2">Kursreaktion am Tag nach den Zahlen ' + ii("Schlusskurs am ersten Handelstag nach dem Bericht gegenüber dem Schluss davor. Grün = Gewinnerwartung übertroffen, rot = verfehlt; "
                    "Höhe des Balkens = Kursreaktion. Gestrichelte Linien = Abstand Einstieg–Stopp des aktuellen Plans.") + '</div>', unsafe_allow_html=True)
        rr = re_[-12:]
        lab = [((q_at(d) or {}).get("label") or ("Bericht " + fdate(d)[3:])).replace(" 20", " ") for d, *_ in rr]
        fig = go.Figure()
        fig.add_bar(x=lab, y=[x[1] for x in rr], marker_color=[POS if (x[2] or 0) > 0 else NEG for x in rr], text=[sgn(x[1], 0) for x in rr], textposition="outside", cliponaxis=False, textfont=dict(size=12),
                    customdata=[[fdate(x[0]), ("übertroffen" if (x[2] or 0) > 0 else "verfehlt")] for x in rr], hovertemplate="<b>%{x}</b> · Bericht %{customdata[0]}<br>Reaktion %{y:+.1%}<br>Erwartung %{customdata[1]}<extra></extra>")
        if p:
            for y in (-p["risk_pct"], p["risk_pct"]): fig.add_hline(y=y, line=dict(color="#c0322b", width=1, dash="dot"))
            fig.add_annotation(x=0, xref="paper", y=1.0, yref="paper", text=f"Gestrichelt: Stoppabstand ±{fpct(p['risk_pct'], 1)}", showarrow=False, xanchor="left", yanchor="bottom", font=dict(color="#c0322b", size=12))
        fig.update_layout(**plot_layout(height=360, margin=dict(l=8, r=8, t=30, b=8), showlegend=False, yaxis=dict(tickformat="+.0%", gridcolor="#f2f4f7"), xaxis=dict(tickangle=-45, tickfont=dict(size=11))))
        pchart(fig, config=PLOT_CFG, key=f"reac_{sym}")
    with r:
        st.markdown('<div class="h2">Quartale: Ist gegen Erwartung ' + ii("Umsatz und Gewinn je Aktie (EPS) je Quartal. EPS ist grün = Erwartung übertroffen, rot = verfehlt. Reaktion = Kursveränderung am Tag nach dem Bericht.") + '</div>', unsafe_allow_html=True)
        rows = []
        byl = {q["label"]: q for q in qs}
        for d, v, sp, est, e in list(reversed(re_)):
            q = q_at(d); lab_ = q["label"] if q else fdate(d)
            yq = byl.get(f'{lab_[:2]} {int(lab_[3:]) - 1}') if q and lab_[3:].isdigit() else None
            ok_ = sp is not None and sp > 0
            rows.append({"Quartal": lab_, "Umsatz": (fnum(q["revenue"] / 1e9, 2) + " Mrd.") if q and q.get("revenue") else "–",
                         "ggü. Vorjahr": sgn(q["revenue"] / yq["revenue"] - 1) if q and yq and yq.get("revenue") and q.get("revenue") else "–",
                         "EPS erwartet": fnum(est) if est is not None else "–", "EPS ist": (f'<span class="{"up" if ok_ else "dn"}">{fnum(e)}</span>' if sp is not None else fnum(e)) if e is not None else "–",
                         "Reaktion": f'<span class="{"up" if v > 0 else "dn"}">{sgn(v)}</span>'})
        cols_ = [c_ for c_ in rows[0] if any(r_[c_] != "–" for r_ in rows)]; al = {x: "r" for x in cols_[1:]}
        st.markdown(table(rows[:8], cols_, align=al), unsafe_allow_html=True)
        if len(rows) > 8:
            with st.expander(f"Weitere {len(rows) - 8} Quartale"): st.markdown(table(rows[8:], cols_, align=al), unsafe_allow_html=True)

def t_tech(c, sym):
    s = SW["stocks"][sym]; px = prices(sym); price = c["price"]
    wk = px.set_index("date").close.resample("W-FRI").last(); mo = px.set_index("date").close.resample("ME").last()
    w30 = wk.rolling(30).mean().iloc[-1]; m10 = mo.rolling(10).mean().iloc[-1]; e20 = px.close.ewm(span=20).mean().iloc[-1]
    ph = c.get("stage"); ok2 = ph == 2 and "kein Stage 2" not in c["stage_text"]
    kpis([k("Trendprüfung", "bestanden" if ok2 else "nicht bestanden", trend_label(c)[0], "pos" if ok2 else "warn",
            "Phasen nach Weinstein: 1 Boden, 2 Aufwärtstrend, 3 Top, 4 Abwärtstrend. Gekauft wird nur in Phase 2 über steigender 30-Wochen-Linie."),
          k("30-Wochen-Linie", sgn(c["sma30w_slope"]), "Steigung über 4 Wochen", "pos" if c["sma30w_slope"] > 0 else "neg"),
          k("Relative Stärke", f"Rang {s['rank']}", f"Linie der relativen Stärke, 3 Monate {sgn(s['rs_chg3m'])}", "pos" if s["rank"] >= 70 else None, "Rang 0–99 im Pool (SCTR-Gewichtung). RS-Linie = Kurs ÷ S&P 500."),
          k("Volumen", f"{fnum(s['updown_vol'], 2)}", f"Auf-/Abwärtsvolumen 50 Tage · {__import__('live').day_tag(c['asof'])} {fnum(s['vol_rel'], 1)}× Ø", "pos" if (s["updown_vol"] or 0) >= 1 else "neg",
            "Volumen an Plustagen ÷ Volumen an Minustagen der letzten 50 Sitzungen. Über 1 = Akkumulation."),
          k("RSI (14 Tage)", fnum(c["rsi14"], 1), f"Tagesspanne Ø {fpct(c['adr20'])}")])
    l, r = st.columns([1.6, 1], gap="large")
    with l:
        st.markdown('<div class="h2">Relative Stärke zum S&amp;P 500' + ii("Kurs der Aktie geteilt durch den S&P-500-ETF, wöchentlich, zwei Jahre. Steigt die Linie, ist die Aktie stärker als der Markt. Der Punkt markiert ein neues 52-Wochen-Hoch der Linie.") + '</div>', unsafe_allow_html=True)
        rs = pd.DataFrame(s["rs_w"], columns=["d", "v"]); rs["d"] = pd.to_datetime(rs["d"]); rs["v"] = rs.v / rs.v.iloc[0] * 100
        fig = go.Figure(go.Scatter(x=rs.d, y=rs.v, mode="lines", line=dict(color=BLUE, width=2), hovertemplate="%{x|%d.%m.%Y}<br>Relative Stärke %{y:,.1f}<extra></extra>"))
        hi = rs.v.rolling(52, min_periods=1).max(); new = rs[(rs.v >= hi) & (rs.index >= 52)]
        if len(new): fig.add_trace(go.Scatter(x=new.d, y=new.v, mode="markers", marker=dict(color="#1849a9", size=8), hovertemplate="neues 52-Wochen-Hoch der relativen Stärke<extra></extra>"))
        fig.update_layout(**plot_layout(height=320, showlegend=False, margin=dict(l=8, r=8, t=10, b=8), xaxis=dict(gridcolor="#eef2f6", tickformat="%m.%Y"), yaxis=dict(gridcolor="#eef2f6", title="Index (Start = 100)")))
        pchart(pad_right(fig), config=PLOT_CFG, key=f"rs_{sym}")
        note("Linie der relativen Stärke am 52-Wochen-Hoch: " + ("ja, Führungsstärke." if s["rs_high52"] else "nein.") + " Punkte zeigen frühere Hochs der Linie.")
    with r:
        st.markdown('<div class="h2">Gleitende Durchschnitte</div>', unsafe_allow_html=True)
        mas = [("10-Tage-EMA", px.close.ewm(span=10).mean().iloc[-1]), ("20-Tage-EMA", e20), ("50-Tage-Linie", c["sma50"]), ("100-Tage-Linie", s["sma100"]),
               ("200-Tage-Linie", c["sma200"]), ("30-Wochen-Linie", c["sma30w"])]
        tb = [{"Linie": n, "Wert": fnum(v), "Kurs dazu": f'<span class="{"up" if price > v else "dn"}">{sgn(price / v - 1)}</span>'} for n, v in mas]
        st.markdown(table(tb, ["Linie", "Wert", "Kurs dazu"], align={"Wert": "r", "Kurs dazu": "r"}), unsafe_allow_html=True)
        st.markdown('<div class="h2" style="margin-top:14px">Zeitebenen</div>', unsafe_allow_html=True)
        tf = [("Tag", "über 20-Tage-EMA", price > e20), ("Woche", "über 30-Wochen-Linie", price > w30), ("Monat", "über 10-Monats-Linie", price > m10)]
        st.markdown('<div class="sw-panel">' + "".join(f'<div class="chk"><span class="m {"p" if ok else "f"}">{"✓" if ok else "✕"}</span><span><b>{a}</b> · Kurs {b}</span></div>' for a, b, ok in tf) + "</div>", unsafe_allow_html=True)
    note(f"Trendstruktur: {plain(c['structure']['label'])}. {plain(c['trend_text'])}.")
    if (SW["stocks"].get(sym) or {}).get("season"):   # ohne Kurshistorie bis 2022 keine Saisonalität
        with st.expander("Saisonalität (Ø-Monatsrendite und Anteil positiver Monate)"):
            se = SW["stocks"][sym]["season"]; y0, y1 = SW["stocks"][sym]["season_years"]
            MO = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
            fig = go.Figure(go.Bar(x=[MO[m - 1] for m, *_ in se], y=[v for _, v, *_ in se], marker_color=[POS if v > 0 else NEG for _, v, *_ in se],
                                   customdata=[[fpct(h, 0), n] for _, _, h, n in se], text=[fpct(h, 0) for _, _, h, _ in se], textposition="outside", cliponaxis=False,
                                   hovertemplate="%{x}: Ø %{y:+.1%}<br>positiv in %{customdata[0]} von %{customdata[1]} Jahren<extra></extra>"))
            fig.update_layout(**plot_layout(height=300, margin=dict(l=8, r=8, t=20, b=8), yaxis=dict(tickformat="+.0%", gridcolor="#eef2f6")))
            pchart(fig, config=PLOT_CFG, key=f"season_{sym}")
            note(f"Monatsrenditen {y0}–{y1}; Zahl über dem Balken = Anteil positiver Monate. Ab 2023 ausgeschlossen (versiegelter Testzeitraum). Saisonalität ist ein schwacher Hinweis, kein Signal.")

def _beat_cell(sym, beats, miss, yr):
    """Beat-Rate nur auf einheitlicher Basis (bereinigt vs. bereinigt, data/earnings_v3.json); gemischte Basis -> ausgeblendet."""
    import fairvalue
    br = fairvalue.beat_rate(sym)
    if br:
        b, n = br
        return ("Gewinnerwartung übertroffen", f"{b} von {n}", f"Quartale, einheitlich bereinigt, Basisrate {fpct(b / max(1, n), 0)}", "pos" if b > n - b else None)
    if fairvalue.has_earnings_basis(sym):
        return ("Gewinnerwartung übertroffen", "k. A.", "Basis gemischt (bereinigt/GAAP), Quote ausgeblendet", None)
    return ("Gewinnerwartung übertroffen", f"{len(beats)} von {len(beats) + len(miss)}", f"Quartale {yr}, Basisrate {fpct(len(beats) / max(1, len(beats) + len(miss)), 0)}", "pos" if len(beats) > len(miss) else None)


def t_targets(c, sym):
    tg = targets(sym); price = c["price"]; a = c["analyst"]; t = a.get("targets") or {}; lv, lo, hi, avg = levels(c); stop = plan_of(sym)["stop"]
    rows = [("Stopp", stop, NEG, "Systemstopp")] + [(f"Stufe {i}", v, POS, "Kaufstufe") for i, v in enumerate(lv, 1)]
    if tg["t1"]: rows.append(("Ziel 1", tg["t1"], BLUE, tg["t1_src"]))
    rows += [(f"Analysten {n}", t[kk], "#1849a9", "Kursziel 12 Monate") for kk, n in (("low", "tief"), ("median", "Median"), ("high", "hoch")) if t.get(kk)]
    if (a.get("targets_30d") or {}).get("median"): rows.append(("Median 30 Tage", a["targets_30d"]["median"], "#6172f3", f"{a['targets_30d']['n']} neue Kursziele"))
    rows.sort(key=lambda x: x[1])
    kpis([k("Ziel 1", fnum(tg["t1"]) if tg["t1"] else "k. A.", f"{tg['t1_src']}, {sgn(tg['t1'] / avg - 1)} vom Ø Einstieg" if tg["t1"] else "kein Widerstand über dem Kurs"),
          k("Ziel 2", fnum(tg["t2"]) if tg["t2"] else "k. A.", f"Analysten-Median, {sgn(tg['t2'] / avg - 1)} vom Ø Einstieg" if tg["t2"] else ""),
          k("Chance/Risiko Ziel 1", fnum(crv(avg, stop, tg["t1"]), 1) if crv(avg, stop, tg["t1"]) is not None else "k. A.", "ab Ø Einstieg bis Stopp"),
          k("Chance/Risiko Ziel 2", fnum(crv(avg, stop, tg["t2"]), 1) if crv(avg, stop, tg["t2"]) is not None else "k. A.", "ab Ø Einstieg bis Stopp"),
          k("Analysten", fnum(a.get("n"), 0), f"Kursziele, Spanne {fnum(t.get('low'), 0)} – {fnum(t.get('high'), 0)}")])
    fig = go.Figure(go.Bar(y=[f"{r[0]} · {fnum(r[1])}" for r in rows], x=[r[1] / price - 1 for r in rows], orientation="h", marker_color=[r[2] for r in rows],
                           text=[sgn(r[1] / price - 1) for r in rows], textposition="outside", cliponaxis=False,
                           customdata=[r[3] for r in rows], hovertemplate="%{y}: %{customdata}<extra></extra>"))
    fig.add_vline(x=0, line=dict(color="#344054", width=1.5)); fig.add_annotation(x=0, y=1.02, yref="paper", text=f"Kurs {fnum(price)}", showarrow=False, yanchor="bottom")
    fig.update_layout(**plot_layout(height=60 + 38 * len(rows), showlegend=False, margin=dict(l=8, r=20, t=30, b=8),
                                    xaxis=dict(tickformat="+.0%", gridcolor="#eef2f6", title="Abstand zum aktuellen Kurs", range=[min(0, min(r[1] / price - 1 for r in rows)) - .09, max(r[1] / price - 1 for r in rows) + .09])))
    st.markdown('<div class="h2">Alle Kursmarken im Abstand zum Kurs</div>', unsafe_allow_html=True)
    pchart(fig, config=PLOT_CFG, key=f"tg_{sym}")
    sc = c["scenarios"]
    st.markdown('<div class="h2">Langfrist-Rahmen: Szenarien in 5 Jahren</div>', unsafe_allow_html=True)
    tb = [{"Szenario": n.capitalize(), "Kurs in 5 J.": fnum(sc[n]["price"]), "Rendite p. a.": sgn(sc[n]["cagr"]), "Fairer Wert heute": fnum(((__import__("fairvalue").get(sym) or {}).get({"konservativ": "pess", "basis": "base", "positiv": "opt"}[n])), 0)} for n in ("konservativ", "basis", "positiv")]
    st.markdown(table(tb, list(tb[0]), align={x: "r" for x in list(tb[0])[1:]}), unsafe_allow_html=True)
    note("Wahrscheinlichkeiten für das Erreichen der Ziele weist das System nicht aus: Die Trefferquoten je Setup werden erst im versiegelten Test ab 2023 geprüft. "
         "Die Szenarien stammen aus dem Bewertungsmodell der Aktienanalyse und sind keine Swing-Ziele.")

def t_verdict(c, sym):
    r = row(sym); m = c["market"]
    st.markdown(f'<div class="verd"><div>{badge(c["category"])}</div><div class="r"><b>Begründung des Systems:</b> {de_txt(dedupe(c["reason"]))}</div></div>', unsafe_allow_html=True)
    q = c["quality"]; vc = c.get("val_criteria") or []
    ok_val = all(x.get("ampel") != "rot" for x in vc[:2]) if vc else None
    chk = [("p" if q["ok"] else "f", "Qualität", de_txt(q["why"])),
           ("p" if ok_val else "f", "Bewertung (Basisrendite 5 J.)", sgn(c["scenarios"]["basis"]["cagr"])),
           ("p" if c.get("stage") == 2 and "kein Stage 2" not in c["stage_text"] else "f", "Aufwärtstrend intakt", "erfüllt" if trend_label(c)[1] else trend_label(c)[0]),
           ("p" if r["near"] else "f", "Kurs nahe oder in der Zone", "in Zone" if r["inzone"] else f"{sgn(r['dist'])} zur Oberkante"),
           ("p" if m["regime"] == "grün" else "i" if m["regime"] == "gelb" else "f", "Marktampel", f'{m["regime"].capitalize()} · Größe {fpct(m["size_factor"], 0)}'),
           ("f" if r["n"] is not None and r["n"] < 5 else "p", "Kein Zahlentermin in 5 Handelstagen", f"{r['n']} Handelstage")]
    l, rr = st.columns([1.4, 1], gap="large")
    with l:
        st.markdown('<div class="h2">Prüfschritte</div><div class="sw-panel">' + "".join(f'<div class="chk"><span class="m {s}">{"✓" if s == "p" else "✕" if s == "f" else "i"}</span><span><b>{t}</b></span><span class="v">{v}</span></div>' for s, t, v in chk) + "</div>", unsafe_allow_html=True)
    with rr:
        w = [de_txt(x) for x in (c.get("veto") or [])] + [de_txt(x) for x in (c.get("warnings") or [])]
        st.markdown('<div class="h2">Sperren und Hinweise</div><div class="sw-panel">' + ("".join(f'<div class="chk"><span class="m i">i</span><span>{x}</span></div>' for x in w) or '<div class="chk">Keine.</div>') + "</div>", unsafe_allow_html=True)
        st.markdown(f'<div class="sw-panel" style="margin-top:12px"><div class="t">Nächster Schritt</div><div style="font-size:14px;color:#344054">{de_txt(c["trade_detail"])}</div></div>', unsafe_allow_html=True)
    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
    note("Die Einstufung ist eine Lesehilfe aus festen Regeln. Die Entscheidung trifft der Mensch; das System gibt keine Orders.")

def detail(sym):
    st.markdown(CSS, unsafe_allow_html=True)
    c = CASES[sym]
    st.markdown(f'<div class="crumb"><a href="/swing-tool" target="_self">Swing-Tool</a><span>›</span><a href="/swing-tool" target="_self">Chancen-Board</a><span>›</span><b>{c["name"]}</b></div>', unsafe_allow_html=True)
    l, r = st.columns([5, 1.1], vertical_alignment="top")
    agx.inject()
    with l: agx.head(c, prices(sym))
    with r:
        st.markdown('<div style="height:22px"></div>', unsafe_allow_html=True)
        if st.button("Aktienanalyse", key="to_analyse", width="stretch", type="primary"): common.go("analyse", sym)
    key = f"stab_{sym}"; q = st.query_params.get("tab")
    if q in ("Ziele", "Einschätzung", "Investment-Case", "Setup und Chart"): q = "Überblick" if q != "Setup und Chart" else "Chart und Setup"
    if q in TABS: st.session_state[key] = q
    elif key not in st.session_state: st.session_state[key] = TABS[0]
    def _tab():
        v = st.session_state.get(key) or TABS[0]; st.session_state[key] = v; st.query_params["tab"] = v
    with st.container(key="tabs"):
        tab = st.segmented_control("Bereich", TABS, key=key, on_change=_tab, label_visibility="collapsed") or TABS[0]
    dict(zip(TABS, [t_case, t_chart, t_plan, t_lever, t_earn, t_tech]))[tab](c, sym)
    footer2(META)

def no_plan(sym):
    """Titel ohne Swing-Einstiegsplan (keine Zone/kein Stopp oder keine Swing-Daten): Kopf + Hinweis statt leerer Reiter."""
    st.markdown(CSS, unsafe_allow_html=True); c = CASES[sym]; agx.inject()
    st.markdown(f'<div class="crumb"><a href="/swing-tool" target="_self">Swing-Tool</a><span>›</span><b>{c["name"]}</b></div>', unsafe_allow_html=True)
    agx.head(c, prices(sym))
    st.markdown(f'<div class="card" style="padding:18px 20px;margin:14px 0"><b>Für {c["name"].split(" (")[0]} gibt es heute keinen Swing-Einstiegsplan.</b> '
                f'Das System hat im Abendlauf vom {fdate(c["asof"])} keine Einstiegszone mit Stopp gefunden. '
                f'<a href="/aktienanalyse?t={sym}" target="_self">Aktienanalyse</a> · <a href="/investment?t={sym}" target="_self">Investment</a></div>', unsafe_allow_html=True)
    footer2(META)

def _has_plan(sym):
    from swing_calc import plan_of
    try: return sym in SW["stocks"] and plan_of(sym) is not None
    except Exception: return False

def page():
    sym = common.current()
    if sym in CASES: detail(sym) if _has_plan(sym) else no_plan(sym)
    else: board()
