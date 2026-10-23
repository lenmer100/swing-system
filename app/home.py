"""Startseite: Markt heute (live, alle 5 Min.), Chancen aus dem Swing-Pool, Tagesgewinner/-verlierer, Zahlentermine der Woche.
Live sind nur Kurs, Tagesveränderung und Intraday-Chart; alle Langfrist-Rechnungen bleiben auf dem Vortagesschluss."""
import datetime as dt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from lib import fnum, fpct, fdate, pill, spark, footer2, FONT
import common, live, ecal
from common import META, CASES

CSS = """<style>
.hm-head{display:flex;align-items:flex-end;justify-content:space-between;margin:26px 0 6px}
.hm-head h1{font-size:28px;font-weight:700;margin:0;padding:0;color:var(--ink)}
.hm-asof{font-size:12.5px;color:var(--muted);font-variant-numeric:tabular-nums}
.hm-asof .dotl{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--pos);margin-right:6px;vertical-align:1px}
.hm-asof .doto{background:#98a2b3}
.hm-h2{font-size:18px;font-weight:700;color:var(--ink);margin:30px 0 10px;display:flex;justify-content:space-between;align-items:baseline}
.hm-h2 a{font-size:13px;font-weight:600;text-decoration:none}
.hm-panel{border:1px solid var(--line);border-radius:12px;background:#fff}
[class*="st-key-mrow_"]{position:relative}
[class*="st-key-mrow_"] [data-testid="stElementContainer"]:has(button){position:absolute !important;inset:0;z-index:3;margin:0 !important;width:100% !important;height:100% !important}
[class*="st-key-mrow_"] button{width:100% !important;height:100% !important;opacity:0;cursor:pointer}
.mr{display:grid;grid-template-columns:1fr auto 64px 76px;gap:10px;align-items:center;padding:9px 14px;border-bottom:1px solid var(--line);font-variant-numeric:tabular-nums}
.mr .n{font-size:13.5px;font-weight:600;color:var(--ink);white-space:nowrap} .mr .v{font-size:13.5px;color:var(--ink);text-align:right;white-space:nowrap}
.mr .pill{font-size:12px;padding:1px 7px;justify-self:end} .mr svg{display:block}
[class*="st-key-mrow_"]:hover .mr{background:var(--card)} .mr.on{background:var(--card);box-shadow:inset 3px 0 0 var(--blue)}
[class*="st-key-mlist"] [data-testid="stVerticalBlock"]{gap:0 !important}
.mlist-wrap{border:1px solid var(--line);border-radius:12px;overflow:hidden}
.ch-name{font-size:13px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.dtag{font-size:11px;color:var(--muted);white-space:nowrap} .mr .pc{display:flex;flex-direction:column;align-items:flex-end;justify-self:end;line-height:1.2}
.ch-head{display:flex;align-items:baseline;gap:12px;padding:2px 2px 0}
.ch-head .t{font-size:15px;font-weight:600;color:var(--muted)} .ch-head .v{font-size:30px;font-weight:700;color:var(--ink);font-variant-numeric:tabular-nums}
.ch-head .pill{font-size:13.5px}
.ch-sub{font-size:12.5px;color:var(--muted);margin:0 2px 2px;font-variant-numeric:tabular-nums}
[class*="st-key-chartbox"]{border:1px solid var(--line);border-radius:12px;padding:16px 18px 6px}
[class*="st-key-tfsel"] button{font-size:12.5px !important;padding:2px 12px !important;min-height:28px !important}
.otb{width:100%;border-collapse:collapse;font-size:13.5px;font-variant-numeric:tabular-nums}
.otb th{font-size:12px;font-weight:600;color:var(--muted);text-align:left;padding:9px 12px;border-bottom:1px solid var(--line);background:#fafbfd;white-space:nowrap}
.otb td{padding:0;border-bottom:1px solid var(--line);white-space:nowrap} .otb tr:last-child td{border-bottom:none}
.otb td a{display:block;padding:10px 12px;color:var(--ink);text-decoration:none} .otb tr:hover td{background:var(--card)}
.otb .r{text-align:right} .otb .mut{color:var(--muted)} .otb .nm{font-weight:600}
.otb .spill{display:inline-block;font-size:12px;font-weight:600;border-radius:999px;padding:2px 9px}
.spill.pos{background:var(--posbg);color:var(--pos)} .spill.warn{background:#fef0c7;color:#93370d} .spill.neg{background:var(--negbg);color:var(--neg)} .spill.neu{background:#eef2f6;color:var(--ink2)}
.tone-pos{color:var(--pos)} .tone-warn{color:#b54708} .tone-neg{color:var(--neg)}
.mvw{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.mv{border:1px solid var(--line);border-radius:12px;overflow:hidden}
.mv .hd{font-size:13px;font-weight:700;color:var(--ink);padding:10px 14px;border-bottom:1px solid var(--line);background:#fafbfd}
.mv a{display:grid;grid-template-columns:1fr auto 84px;gap:10px;align-items:center;padding:9px 14px;border-bottom:1px solid var(--line);color:var(--ink);text-decoration:none;font-size:13.5px;font-variant-numeric:tabular-nums}
.mv a:last-child{border-bottom:none} .mv a:hover{background:var(--card)} .mv .s{font-weight:600} .mv .s span{color:var(--muted);font-weight:400;margin-left:6px}
.mv .pill{justify-self:end}
.wk{display:grid;grid-template-columns:repeat(5,1fr);border:1px solid var(--line);border-radius:12px;overflow:hidden}
.wk .day{border-right:1px solid var(--line);min-height:120px} .wk .day:last-child{border-right:none}
.wk .dh{font-size:12.5px;font-weight:700;color:var(--ink);padding:9px 12px;border-bottom:1px solid var(--line);background:#fafbfd}
.wk .dh span{color:var(--muted);font-weight:500;margin-left:4px} .wk .dh.today{color:var(--blue)}
.wk a{display:flex;justify-content:space-between;gap:6px;padding:7px 12px;font-size:13px;color:var(--ink);text-decoration:none;border-bottom:1px solid #f0f2f5}
.wk a:hover{background:var(--card)} .wk a b{font-weight:600} .wk a i{font-style:normal;color:var(--muted);font-size:12px}
.wk .none{padding:10px 12px;font-size:12.5px;color:var(--muted)}
.wk .more{font-size:12.5px;color:var(--blue) !important;font-weight:600}
.hm-panel{overflow-x:auto !important}
@media (max-width:640px){.wk{grid-template-columns:1fr}.wk .day{border-right:none;border-bottom:1px solid var(--line);min-height:0}
.mvw{grid-template-columns:1fr}.hm-head h1{font-size:22px}.ch-head .v{font-size:24px}.otb{min-width:860px}
.mr{grid-template-columns:1fr auto 76px}.mr svg{display:none}.mr span:nth-child(3){display:none}}
</style>"""

WD = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
TF = ["1T", "5T", "1M", "YTD", "1J", "5J"]

def _search():
    v = st.session_state.get("home_search")
    if v: st.session_state.home_go = v
    st.session_state.home_search = None

def _fmt(k, v):
    return fnum(v, live.DEC[k]) + live.UNIT.get(k, "")

def _quotes():
    """Live-Kurse der Marktwerte; Fallback Snapshot (market.json)."""
    q = live.index_quotes()
    if len(q) >= 5: return q, True
    from lib import load_v3
    m = {x["key"]: x for x in load_v3()[0]}
    out = {}
    for k, s in live.SNAP.items():
        x = m.get(s)
        if x and x.get("last") is not None: out[k] = dict(last=x["last"], prev=x["prev"], ts=None, live=False)
    return out, False

def _chart(k, tf, q):
    ser = live.index_series(tf).get(k); src = "live"
    if (ser is None or len(ser) < 2) and tf not in ("1T", "5T"):
        s = live.snapshot_series(k)
        if s is not None:
            src = "snap"
            start = {"1M": 31, "1J": 365, "5J": 1826}.get(tf)
            ser = s[s.index >= (pd.Timestamp(f"{s.index[-1].year}-01-01") if tf == "YTD" else s.index[-1] - pd.Timedelta(days=start))]
    if ser is None or len(ser) < 2:
        st.markdown('<div class="ch-sub" style="padding:120px 0;text-align:center">Für diesen Zeitraum liegen gerade keine Daten vor.</div>', unsafe_allow_html=True)
        return
    base = q[k]["prev"] if tf == "1T" and k in q else float(ser.iloc[0])
    up = float(ser.iloc[-1]) >= base; col = "#1e7b45" if up else "#c0322b"
    intr = tf in ("1T", "5T")
    x = list(range(len(ser))) if tf == "5T" else ser.index
    hover = [f"{t.strftime('%d.%m. %H:%M') if intr else t.strftime('%d.%m.%Y')}  ·  {_fmt(k, v)}" for t, v in zip(ser.index, ser.values)]
    fig = go.Figure(go.Scatter(x=x, y=ser.values, mode="lines", line=dict(color=col, width=2), fill="tozeroy",
                               fillcolor="rgba(30,123,69,.07)" if up else "rgba(192,50,43,.07)", hovertext=hover, hoverinfo="text"))
    lo, hi = float(ser.min()), float(ser.max())
    if tf == "1T": lo, hi = min(lo, base), max(hi, base)
    pad = (hi - lo) * 0.08 or abs(hi) * 0.01
    if tf == "1T":
        fig.add_hline(y=base, line=dict(color="#98a2b3", width=1, dash="dot"))
    xa = dict(showgrid=False, fixedrange=True, range=[x[0], x[-1]] if tf == "5T" else [ser.index[0], ser.index[-1]], linecolor="#e3e8ef", tickfont=dict(size=11, color="#5d6b7e"))
    if tf == "5T":
        days = pd.Series(range(len(ser)), index=ser.index).groupby(ser.index.date).first()
        xa.update(tickvals=days.values.tolist(), ticktext=[pd.Timestamp(d).strftime("%d.%m.") for d in days.index])
    elif tf == "1T": xa.update(tickformat="%H:%M")
    else: xa.update(tickformat="%b %Y" if tf in ("1J", "5J") else "%d.%m.")
    fig.update_layout(height=330, margin=dict(l=4, r=4, t=8, b=4), plot_bgcolor="#fff", paper_bgcolor="#fff", showlegend=False, dragmode=False, uirevision=f"{k}_{tf}",
                      font=dict(family=FONT, size=12, color="#344054"), hovermode="x", hoverlabel=dict(bgcolor="#fff", font_size=12),
                      xaxis=xa, yaxis=dict(range=[lo - pad, hi + pad], side="right", gridcolor="#f0f2f5", fixedrange=True, zeroline=False,
                                           tickfont=dict(size=11, color="#5d6b7e"), separatethousands=True, tickformat=",." + str(0 if hi >= 1000 else min(live.DEC[k], 2)) + "f"),
                      separators=",.")
    st.plotly_chart(fig, config={"displayModeBar": False, "scrollZoom": False, "doubleClick": False, "showAxisDragHandles": False}, key=f"mchart_{k}_{tf}")
    lab = (f"Live · Stand {ser.index[-1].strftime('%H:%M')} Uhr · Aktualisierung alle 5 Min." if src == "live" and intr and live.day_tag(ser.index[-1]) == "heute"
           else f"Letzte Sitzung · Schluss {ser.index[-1].strftime('%d.%m.%Y')}" if intr else f"Stand Schluss {ser.index[-1].strftime('%d.%m.%Y')}")
    st.markdown(f'<div class="ch-sub" style="text-align:right;font-size:12px;color:var(--muted)">{lab}</div>', unsafe_allow_html=True)

def _dt(v, is_live, long=False):
    """Tagesänderung kennzeichnen: aus laufender Sitzung = heute, sonst Schluss mit Datum."""
    tg = live.day_tag(v.get("ts")) if is_live else f"Schluss {fdate(META['asof'])[:6]}"
    if tg == "heute": return '<span class="dtag">heute</span>' if long else ""
    return f'<span class="dtag">{"Vortag · " if long else ""}{tg}</span>'

def market_section():
    q, is_live = _quotes()
    keys = [k for k, *_ in live.IDX if k in q]
    sel = st.session_state.get("hm_sel")
    if sel not in keys: sel = st.session_state["hm_sel"] = keys[0]
    tf = st.session_state.get("hm_tf") or "1T"
    ts = max((v["ts"] for v in q.values() if v.get("ts") is not None), default=None)
    asof = (f'<span class="dotl"></span>Live · Stand {ts.strftime("%H:%M")} Uhr MESZ' if is_live and ts is not None and live.day_tag(ts) == "heute"
            else f'<span class="dotl doto"></span>Letzte Sitzung · Schluss {ts.strftime("%d.%m.")}' if is_live and ts is not None
            else f'<span class="dotl doto"></span>Schlusskurse {fdate(META["asof"])}')
    st.markdown(f'<div class="hm-head"><h1>Markt heute</h1><div class="hm-asof">{asof}</div></div>', unsafe_allow_html=True)
    left, right = st.columns([1.75, 1], gap="medium")
    spk = live.index_series("1T")
    with right, st.container(key="mlist"):
        st.markdown('<div style="height:0"></div>', unsafe_allow_html=True)
        for k in keys:
            v = q[k]; ch = v["last"] / v["prev"] - 1
            sp = spark((spk.get(k) if spk.get(k) is not None else pd.Series(dtype=float)).tolist()[-80:], 64, 24)
            with st.container(key=f"mrow_{k}"):
                st.markdown(f'<div class="mr{" on" if k == sel else ""}"><span class="n">{live.NAME[k]}</span><span class="v">{_fmt(k, v["last"])}</span>'
                            f'<span>{sp}</span><span class="pc">{pill(ch, 2)}{_dt(v, is_live)}</span></div>', unsafe_allow_html=True)
                if st.button(live.NAME[k], key=f"mbtn_{k}"):
                    st.session_state["hm_sel"] = k; st.rerun(scope="fragment")
    with left, st.container(key="chartbox"):
        v = q[sel]; ch = v["last"] / v["prev"] - 1
        st.markdown(f'<div class="ch-name">{live.NAME[sel]}</div><div class="ch-head"><span class="v">{_fmt(sel, v["last"])}</span>{pill(ch, 2, txt=fpct(abs(ch), 2))}'
                    f'<span class="t">{("+" if v["last"] >= v["prev"] else "−") + fnum(abs(v["last"] - v["prev"]), live.DEC[sel])}</span>{_dt(v, is_live, True)}</div>',
                    unsafe_allow_html=True)
        with st.container(key="tfsel"):
            st.segmented_control("Zeitraum", TF, key="hm_tf", default="1T", label_visibility="collapsed")
        _chart(sel, st.session_state.get("hm_tf") or "1T", q)

def _rows():
    try:
        from swing_calc import board_rows, swing_status
        rows = board_rows()
        for r in rows: r["status"] = swing_status(r)
        return rows
    except Exception:
        return []

def _short(n, k=26):
    n = n.split(" (")[0]
    for suf in (" Inc.", ", Inc.", " Corporation", " Corp.", " GmbH & Co. KGaA", " Limited", " Ltd.", " plc", " N.V.", " SE", " AG"):
        n = n.replace(suf, "")
    return n if len(n) <= k else n[:k - 1].rstrip() + "…"

def _qlab(pts):
    return (f"Kurs live · Stand {pts.strftime('%H:%M')} Uhr · Zonen Stand Schluss {fdate(META['asof'])}" if pts is not None
            else f"Stand Schluss {fdate(META['asof'])}")

def opportunities(quotes, lab=""):
    rows = [dict(r) for r in _rows() if r["status"] in ("In Einstiegszone", "Nahe Einstiegszone") and (r["crv"] or 0) >= 1 and r["risk"] >= 0.015]
    for r in rows:   # Status zum Live-Kurs, nicht zum Vortagesschluss: Kurs unter der Zone oder am Stopp nicht als "In Einstiegszone" zeigen
        try:
            last = (quotes.get(r["sym"]) or live.snap_quote(r["sym"]))[0]
            if last <= r["stop"]: r["status"] = "Stopp unterschritten"
            elif last < r["lo"]: r["status"] = "Unter Einstiegszone"
            elif last <= r["hi"]: r["status"] = "In Einstiegszone"
            elif last <= r["hi"] * 1.03: r["status"] = "Nahe Einstiegszone"
            else: r["status"] = "Warten auf Rücksetzer"
        except Exception:
            pass
    rows = [r for r in rows if r["status"] in ("In Einstiegszone", "Nahe Einstiegszone", "Unter Einstiegszone")]
    rows = sorted(rows, key=lambda r: ({"In Einstiegszone": 0, "Nahe Einstiegszone": 1}.get(r["status"], 2), -(r["crv"] or 0)))[:8]
    if not rows: return
    ds = [q[2] for q in (quotes.get(r["sym"]) for r in rows) if q]
    dlab = live.day_tag(max(set(ds), key=ds.count)) if ds else f"Schluss {fdate(META['asof'])[:6]}"
    dlab = "Heute" if dlab == "heute" else dlab
    n_all = sum(1 for r in _rows() if r["status"] in ("In Einstiegszone", "Nahe Einstiegszone"))
    st.markdown(f'<div class="hm-h2"><span>Chancen aus dem Swing-Pool</span><span class="hm-asof" style="margin-left:auto;margin-right:14px">{lab if dlab == "Heute" else f"Kurse {dlab} · Zonen Stand Schluss {fdate(META['asof'])}"}</span><a href="/swing-tool?liste=zone" target="_self">Alle {n_all} in oder nahe Einstiegszone</a></div>', unsafe_allow_html=True)
    from swing_calc import STATUS_TONE
    ext = live.ext_quotes(common.SYMS)
    th = (f"<tr><th>Aktie</th><th>Setup</th><th>Status</th><th class='r'>Kurs</th><th class='r'>{dlab}</th><th class='r'>Einstiegszone</th>"
          "<th class='r'>Stopp</th><th class='r'>Chance/Risiko</th><th class='r'>Zahlen</th></tr>")
    body = ""
    for r in rows:
        s = r["sym"]; c = r["c"]; last, prev, _ = quotes.get(s) or live.snap_quote(s)
        a = lambda x, cls="": f'<td class="{cls}"><a href="/swing-tool?t={s}" target="_self">{x}</a></td>'
        crv = r["crv"]; ct = "pos" if crv >= 2 else "warn"
        body += ("<tr>" + a(f'<span class="nm">{_short(c["name"])}</span> <span class="mut">{s}</span>') + a(r["setup"])
                 + a(f'<span class="spill {STATUS_TONE.get(r["status"], "warn")}">{r["status"]}</span>')
                 + a(f'{fnum(last)} <span class="mut">{c["currency"]}</span>' + (f'<div class="dtag">{live.ext_tag(ext[s])}</div>' if s in ext else ""), "r") + a(pill(last / prev - 1, 2), "r")
                 + a(f'{fnum(r["lo"])} – {fnum(r["hi"])}', "r") + a(fnum(r["stop"]), "r")
                 + a(f'<b class="tone-{ct}">{fnum(crv, 1)}</b>', "r")
                 + a(fdate(c["next_earnings"])[:6] if c.get("next_earnings") else "–", "r mut") + "</tr>")
    st.markdown(f'<div class="hm-panel" style="overflow:hidden"><table class="otb"><thead>{th}</thead><tbody>{body}</tbody></table></div>', unsafe_allow_html=True)

def movers(quotes, is_live, pts=None):
    big = [s for s, c in CASES.items() if (c.get("keystats") or {}).get("mcap", 0) >= 10e9 and s in quotes]
    if len(big) < 10: return
    ext = live.ext_quotes(common.SYMS); eb = [s for s in big if s in ext and ext[s]["sess"] == "pre"]
    pre = len(eb) >= 0.2 * len([s for s in big if "." not in s])
    if pre:   # vor US-Börsenstart: Bewegungen vorbörslich gegenüber dem letzten Schluss
        quotes = dict(quotes); quotes.update({s: (ext[s]["last"], ext[s]["close"], None) for s in eb})
        ch = sorted(((ext[s]["last"] / ext[s]["close"] - 1, s) for s in eb), reverse=True)
    else:
        ch = sorted(((quotes[s][0] / quotes[s][1] - 1, s) for s in big if quotes[s][1]), reverse=True)
    ds = [quotes[s][2] for s in big if quotes[s][2]]
    tg = live.day_tag(max(set(ds), key=ds.count)) if ds else None
    lab = (f"Heute · live, Stand {pts.strftime('%H:%M')} Uhr" if tg == "heute" and pts is not None else tg or "Letzte Sitzung") if is_live else f"Schluss {fdate(META['asof'])}"
    def box(title, items):
        return (f'<div class="mv"><div class="hd">{title}</div>' + "".join(
            f'<a href="/aktienanalyse?t={s}" target="_self"><span class="s">{_short(CASES[s]["name"])}<span>{s}</span></span>'
            f'<span>{fnum(quotes[s][0])} <span class="mut" style="color:var(--muted)">{CASES[s]["currency"]}</span></span>{pill(x, 2)}</a>' for x, s in items) + "</div>")
    if pre: lab = f"Vorbörslich (US) · Stand {max(ext[s]['ts'] for s in eb).strftime('%H:%M')} Uhr · gegenüber letztem Schluss"
    st.markdown(f'<div class="hm-h2"><span>Größte Bewegungen im Pool</span><span class="hm-asof">{lab} · Marktwert ab 10 Mrd.</span></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="mvw">{box("Gewinner", ch[:6])}{box("Verlierer", ch[::-1][:6])}</div>', unsafe_allow_html=True)

def _ename(sym):
    c = CASES.get(sym)
    return f'{_short(c["name"], 20)} <span class="mut">({sym})</span>' if c and c.get("name") else sym

def earnings_week():
    today = dt.date.today()
    days = [d.date() for d in pd.bdate_range(today, periods=5)]
    ev = ecal.events(days[0], days[-1], important=True)
    st.markdown(f'<div class="hm-h2"><span>Zahlentermine der nächsten Tage</span><a href="/zahlentermine" target="_self">Alle Zahlentermine</a></div>', unsafe_allow_html=True)
    html = ""
    for d in days:
        e = [x for x in ev if x["date"] == d.isoformat()]
        items = "".join(f'<a href="/zahlentermine?e={x["symbol"]}" target="_self"><b>{_ename(x["symbol"])}</b><i>{ecal.TIME_SHORT.get(x.get("time"), "") if ecal.confirmed(x) else "unbestätigt"}</i></a>' for x in e[:7])
        if len(e) > 7: items += f'<a class="more" href="/zahlentermine?d={d.isoformat()}" target="_self">+ {len(e) - 7} weitere</a>'
        html += (f'<div class="day"><div class="dh{" today" if d == today else ""}">{"Heute" if d == today else WD[d.weekday()]}<span>{d.strftime("%d.%m.")}</span></div>'
                 + (items or '<div class="none">Keine Termine</div>') + "</div>")
    st.markdown(f'<div class="wk">{html}</div>', unsafe_allow_html=True)

def _warm():   # Board-Zeilen und Pool-Kurse beim Serverstart vorbereiten, damit der erste Aufruf nicht wartet
    import threading
    threading.Thread(target=_rows, daemon=True).start()
    live._pool(tuple(common.SYMS)); live._ext(tuple(common.SYMS))
_warm()

@st.fragment(run_every=live.REFRESH)
def live_body():
    market_section()
    pq, pts = live.pool_quotes(common.SYMS)
    quotes = pq if pq else {}
    is_live = bool(pq)
    if is_live and pts is not None and not hasattr(pts, "strftime"): pts = None
    opportunities(quotes, _qlab(pts if is_live else None))
    if not is_live:
        try:
            from swing_calc import SW
            quotes = {s: (CASES[s]["price"], v["close_prev"], None) for s, v in SW["stocks"].items() if s in CASES and v.get("close_prev")}
        except Exception:
            quotes = {}
    movers(quotes, is_live, pts)

def home():
    st.markdown(CSS, unsafe_allow_html=True)
    if t := st.session_state.pop("home_go", None):
        common.go("analyse", t)
    with st.container(key="homesearch"):
        pass
    live_body()
    earnings_week()
    footer2(META)
