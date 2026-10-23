"""aktien.guide-Designsprache für die Aktienanalyse: Kopfzeile mit Performance-Chips, Infokasten, Pill-Tabellen,
Akkordeon-Abschnitte, Prognose-Chart mit Band, einheitliche Tooltips. Geteilt nutzbar (z. B. perf_row im Swing-Tool)."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from lib import fnum, fpct, fdate, pill, FONT, plot_layout, load_v3, fbig, sector_de, ICONS

BLUE, BAND, INK, MUTED, GRID = "#3d6fb6", "rgba(61,111,182,.22)", "#1d2939", "#5d6b7e", "#eef2f6"

CSS = """<style>
.agperf{display:flex;flex-wrap:nowrap;gap:14px;align-items:baseline;font-size:12px;color:#8a94a6;white-space:nowrap;font-variant-numeric:tabular-nums;margin:6px 0 0}
.agperf span b{font-weight:600;margin-left:4px;font-size:12.5px} .agperf b.up{color:#2e9e5b} .agperf b.dn{color:#d64541} .agperf b.nu{color:#5d6b7e}
.agbox{background:#f3f6fa;border-radius:8px;padding:14px 22px;margin:18px 0 8px}
.agbox .r{display:flex;gap:16px;align-items:flex-start;padding:9px 0;font-size:14px;line-height:1.7;color:#475467}
.agbox svg{flex:0 0 18px;margin-top:4px}
.agbox .pill,.agacc .pill,.agft .pill,.agpt .pill{font-size:11.5px;padding:1px 7px;margin:0 2px;border-radius:4px}
.agcard{border:1px solid #e4e7ec;border-radius:8px;padding:14px 16px;background:#fff;margin-bottom:12px}
.agcard .t{font-weight:700;font-size:14.5px;color:#1d2939;margin-bottom:8px}
.agrt{display:grid;grid-template-columns:118px 1fr 44px;white-space:nowrap;align-items:center;gap:10px;font-size:13.5px;color:#344054;margin:5px 0}
.agrt .bar{height:12px;border-radius:6px;background:#e4e7ec;overflow:hidden} .agrt .bar i{display:block;height:100%;border-radius:6px}
.agrt b{text-align:right;font-weight:600}
.agkv{width:100%;border-collapse:collapse;font-size:14px;border:0 !important} .agkv td{border-left:0 !important;border-right:0 !important;border-top:0 !important;padding:9px 2px;border-bottom:1px solid #eef2f6;color:#344054}
.agkv tr:last-child td{border-bottom:0} .agkv td.r{text-align:right;font-variant-numeric:tabular-nums;color:#1d2939}
.agft{border:1px solid #e4e7ec;border-radius:8px;padding:6px 14px;background:#fff;font-size:13.5px}
.agft table{width:100%;border-collapse:collapse} .agft th{text-align:right;font-weight:700;color:#1d2939;padding:10px 4px;font-size:13.5px;vertical-align:bottom}
.agft td{padding:8px 4px;text-align:right;font-variant-numeric:tabular-nums;color:#1d2939} .agft td.k{text-align:left;font-weight:700}
.agft td.k small{font-weight:400;color:#8a94a6;font-size:11px;margin-left:3px} .agft tr.p td{border-bottom:1px solid #eef2f6;padding-top:0}
.agacc-h{font-size:14.5px;line-height:1.75;color:#475467;margin:6px 4px 14px}
.agpt{background:#f3f6fa;border-radius:8px;padding:14px 20px;margin:4px auto 10px;width:max-content;min-width:260px;font-size:13px}
.agpt .h{font-weight:700;font-size:16px;color:#1d2939;margin-bottom:8px}
.agpt table{border-collapse:collapse} .agpt td{padding:2px 10px 2px 0;font-variant-numeric:tabular-nums;color:#344054} .agpt td.v{text-align:right;padding-left:36px}
.agpt td.y{font-weight:700;color:#1d2939}
.agtag{font-size:10.5px;font-weight:600;border-radius:4px;padding:1px 6px;margin-left:6px} .agtag.ist{background:#eef2f6;color:#5d6b7e} .agtag.konsens{background:#e3edf8;color:#2f62a8} .agtag.modell{background:#fdf0e3;color:#b35c0e}
.tcard{background:#fff !important;border:1px solid #e4e7ec !important;box-shadow:none !important;border-radius:8px !important}
.tcard .row{border-color:#eef2f6 !important}
.kpis .kpi{background:#fff !important;border:1px solid #e4e7ec !important;border-radius:8px !important;box-shadow:none !important}
.agsec{font-size:21px;font-weight:700;color:#1d2939;margin:34px 0 10px;letter-spacing:-.2px}
[class*="st-key-agacc"] [data-testid="stExpander"] details{border:0 !important;border-radius:6px !important;background:#fff}
[class*="st-key-agacc"] [data-testid="stExpander"] summary{background:#dce6f2;border-radius:6px;padding:14px 16px}
[class*="st-key-agacc"] [data-testid="stExpander"] summary p{color:#2f62a8 !important;font-size:15px !important;font-weight:600 !important}
[class*="st-key-agacc"] [data-testid="stExpander"]{margin-bottom:6px}
.kpis.c3{margin-bottom:18px}
.agft td,.agft th,.agkv td,.agpt td,.agft tr,.agpt tr{border:0 !important;background:transparent !important}
.agft tr.p td{border-bottom:1px solid #eef2f6 !important} .agkv td{border-bottom:1px solid #eef2f6 !important} .agkv tr:last-child td{border-bottom:0 !important}
.agft thead th{border-bottom:1px solid #e4e7ec !important}
.agrt span{white-space:nowrap}
[class*="st-key-agacc"] [data-testid="stExpander"] summary > span{display:flex !important;flex-direction:row-reverse;justify-content:space-between;width:100%}
[class*="st-key-agcardbtn"]{position:relative}
[class*="st-key-agcardbtn"] [class*="st-key-open_"]{position:absolute !important;inset:0;z-index:3;margin:0 !important;width:100% !important;max-width:none !important}
[class*="st-key-agcardbtn"] [class*="st-key-open_"] button{min-width:100% !important;max-width:none !important}
[class*="st-key-agcardbtn"] [class*="st-key-open_"] *{width:100% !important;height:100% !important}
[class*="st-key-agcardbtn"] [class*="st-key-open_"] button{opacity:0;cursor:pointer}
[class*="st-key-agcardbtn"]:hover .card{border-color:#3d6fb6;box-shadow:0 2px 10px rgba(16,24,40,.08)}
[class*="st-key-agper"] [data-testid="stButtonGroup"]{justify-content:flex-end}
</style>"""

def inject(): st.markdown(CSS, unsafe_allow_html=True)

def perf_row(px):
    """Performance-Chips 1 Woche … 3 Jahre: eine dezente Zeile, graue Labels, farbige Werte, keine Kästchen. px: DataFrame mit date, close."""
    last = px.close.iloc[-1]
    def v(x):
        if x is None: return '<b class="nu">k. A.</b>'
        return f'<b class="{"up" if x > 0 else "dn" if x < 0 else "nu"}">{fpct(x, 1, True)}</b>'
    def n(k): return v(last / px.close.iloc[-1 - k] - 1) if len(px) > k else v(None)
    ytd = px[px.date.dt.year == px.date.iloc[-1].year].close.iloc[0]
    items = [("1 Woche", n(5)), ("1 Monat", n(21)), ("3 Monate", n(63)), ("lfd. Jahr", v(last / ytd - 1)), ("1 Jahr", n(252)), ("3 Jahre", n(756))]
    return '<div class="agperf">' + "".join(f"<span>{a}{b}</span>" for a, b in items) + "</div>"

def _dtag(sym, px):
    """'heute' nur bei Werten der laufenden Sitzung, sonst 'Schluss TT.MM.'; plus vor-/nachbörslicher Kurs wie auf der Startseite."""
    import live
    t = live.day_tag(px.date.iloc[-1])
    try:
        import common; e = live.ext_quotes(common.SYMS).get(sym)
        if e: t += " · " + live.ext_tag(e)
    except Exception: pass
    return t

def head(c, px):
    """Aktienkopf (Name, Kurs + Pille, Performance-Zeile, Stammdaten) ohne Urteil."""
    _, cons = load_v3(); k = cons.get(c["symbol"], {})
    last, prev = px.close.iloc[-1], px.close.iloc[-2]
    y = px.tail(252); lo52, hi52 = y.low.min(), y.high.max()
    mono = c["symbol"][:2] if c["symbol"] != "GOOGL" else "GO"
    from lib import INDUSTRY_DE
    st.markdown(
        f'<div class="shead"><div class="nm"><span class="mono">{mono}</span>{c["name"]}</div>'
        f'<div class="pxrow"><span class="px">{fnum(last)}<small>{c["currency"]}</small></span>{pill(last / prev - 1, 2, big=True)}<span class="dtag" style="margin-left:8px;color:#667085;font-size:13px">{_dtag(c["symbol"], px)}</span></div>'
        f'{perf_row(px)}'
        f'<div class="sub">{k.get("exchange", "NASDAQ")}, Schlusskurs {fdate(str(px.date.iloc[-1])[:10])}</div>'
        f'<div class="mgrid"><div><span>Symbol</span>{c["symbol"]}</div><div><span>Index</span><b>{k.get("index") or "k. A."}</b></div>'
        f'<div><span>52 Wochen</span><span style="color:#1d2939">{fnum(lo52)} – {fnum(hi52)}</span></div>'
        f'<div><span>Börse</span>{k.get("exchange", "NASDAQ")}</div><div><span>Sektor</span><b>{sector_de(c["sector"])}</b></div>'
        f'<div><span>Börsenwert</span>{fbig(c["keystats"]["mcap"], c["currency"])}</div>'
        f'<div><span>Währung</span>{c["currency"]}</div><div><span>Industrie</span><b>{INDUSTRY_DE.get(c["industry"], c["industry"])}</b></div>'
        f'<div><span>Nächste Zahlen</span>{fdate(c["next_earnings"])}</div></div></div>', unsafe_allow_html=True)

def ii(text):
    return f'<span class="ii" tabindex="0" aria-label="Erklärung">i<span class="tip">{text}</span></span>'

def sec(title, info=None):
    st.markdown(f'<div class="agsec">{title}{ii(info) if info else ""}</div>', unsafe_allow_html=True)

def box(items):
    """Infokasten: [(icon, html)] mit Symbol links, Sätzen mit eingebetteten Pills."""
    row = lambda ic, t: (f'<div class="r"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#3d6fb6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                         f'{ICONS.get(ic, ICONS["info"])}</svg><div>{t}</div></div>')
    st.markdown('<div class="agbox">' + "".join(row(i, t) for i, t in items) + "</div>", unsafe_allow_html=True)

def p(x, d=2):
    """Inline-Pill im Fließtext."""
    return pill(x, d)

def pill_table(title, rows, tags=None):
    """Kleine zentrierte Tabelle: rows = [(label, wert_html, pill_html, info oder None)]; tags: optional je Zeile 'Ist'/'Konsens'/'Modell'."""
    tg = lambda x: (f'<span class="agtag {x.lower()}">{x}</span>' if x else "")
    tags = tags or [None] * len(rows)
    body = "".join(f'<tr><td class="y">{a}{(" " + ii(i)) if i else ""}</td><td>{tg(t_)}</td><td class="v">{b}</td><td>{c}</td></tr>' for (a, b, c, i), t_ in zip(rows, tags))
    return f'<div class="agpt"><div class="h">{title}</div><table>{body}</table></div>'

def acc(key, title, sentence, table_html="", expanded=False, body=None):
    """Akkordeon wie bei aktien.guide: hellblaue Kopfzeile mit Chevron, Satz mit Pills, zentrierte Pill-Tabelle, optional weiterer Inhalt (Callable)."""
    with st.container(key=f"agacc_{key}"):
        with st.expander(title, expanded=expanded):
            st.markdown(f'<div class="agacc-h">{sentence}</div>{table_html}', unsafe_allow_html=True)
            if body: body()

from contextlib import contextmanager
@contextmanager
def acc_ctx(key, title, sentence="", expanded=False):
    """Akkordeon als Kontext: Inhalt direkt im Block."""
    with st.container(key=f"agacc_{key}"):
        with st.expander(title, expanded=expanded):
            if sentence: st.markdown(f'<div class="agacc-h">{sentence}</div>', unsafe_allow_html=True)
            yield

def fc_table(cols, rows):
    """Kompakte Tabelle rechts neben dem Prognose-Chart. cols: Spaltenköpfe; rows: [(name, einheit, [werte], [pills])]."""
    th = "<th></th>" + "".join(f"<th>{c}</th>" for c in cols)
    body = ""
    for n, u, vals, pills in rows:
        body += f'<tr><td class="k">{n}{f"<small>{u}</small>" if u else ""}</td>' + "".join(f"<td>{v}</td>" for v in vals) + "</tr>"
        body += '<tr class="p"><td></td>' + "".join(f"<td>{x}</td>" for x in pills) + "</tr>"
    return f'<div class="agft"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'

def unified(fig, header="%{x}"):
    """Einheitlicher Tooltip für Mehrfach-Reihen: fette Kopfzeile, je Reihe 'Name: Wert Einheit'."""
    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(unifiedhovertitle=dict(text=f"<b>{header}</b>"))
    return fig

def tpl(name, fmt=",.2f", unit="", var="y"):
    return f"{name}: %{{{var}:{fmt}}}{(' ' + unit) if unit else ''}<extra></extra>"

def single(header="%{x}", name="", fmt=",.2f", unit="", var="y"):
    """Tooltip für Einzelreihen: fette Kopfzeile + 'Name: Wert Einheit'."""
    return f"<b>{header}</b><br>{name}: %{{{var}:{fmt}}}{(' ' + unit) if unit else ''}<extra></extra>"

def layout(h, **kw):
    base = dict(height=h, margin=dict(l=4, r=8, t=30, b=4), showlegend=False, font=dict(family=FONT, size=12, color=MUTED),
                hoverlabel=dict(bgcolor="#ffffff", bordercolor="#d0d7e2", font=dict(family=FONT, size=13, color=INK), align="left"))
    base.update(kw); return plot_layout(**base)

def forecast_fig(title, hx, hy, fx, fy, flo, fhi, unit, prog_from, h=400, yfmt=",.0f", name="Wert", header="%{x|%Y}", n_cons=None):
    """Linienchart wie aktien.guide: Ist-Verlauf, schattierter Prognosebereich, Median-Linie mit Punkten, Band tief–hoch."""
    f = go.Figure()
    xs_all = list(hx) + list(fx)
    f.add_vrect(x0=prog_from, x1=xs_all[-1], fillcolor="#f2f4f7", opacity=1, line_width=0, layer="below")
    f.add_annotation(x=prog_from, y=1, yref="paper", xanchor="left", yanchor="top", xshift=6, yshift=-4, showarrow=False, text="Prognose", font=dict(size=11, color=MUTED))
    if fx:
        bx = [hx[-1]] + list(fx); blo = [hy[-1]] + list(flo); bhi = [hy[-1]] + list(fhi)
        f.add_trace(go.Scatter(x=bx, y=bhi, mode="lines", line=dict(width=0, color=BAND), hoverinfo="skip", showlegend=False))
        f.add_trace(go.Scatter(x=bx, y=blo, mode="lines", line=dict(width=0, color=BAND), fill="tonexty", fillcolor=BAND, hoverinfo="skip", showlegend=False))
    f.add_trace(go.Scatter(x=list(hx), y=list(hy), mode="lines", line=dict(color=BLUE, width=2.4), fill="tozeroy", fillcolor="rgba(61,111,182,.10)",
                           name=name, hovertemplate=tpl(name, ",.1f", unit)))
    if fx:
        nc = len(fx) if n_cons is None else n_cons
        segs = [("Konsens", 0, nc, BLUE, "solid"), ("Modell", nc, len(fx), "#e8892c", "dash")]
        for lab, a0, a1, col, dash in segs:
            if a1 <= a0: continue
            px_ = ([hx[-1]] if a0 == 0 else [fx[a0 - 1]]) + list(fx[a0:a1]); py_ = ([hy[-1]] if a0 == 0 else [fy[a0 - 1]]) + list(fy[a0:a1])
            cd = [[None, None]] + [[a, b] for a, b in zip(flo[a0:a1], fhi[a0:a1])]
            src = "Analystenkonsens" if lab == "Konsens" else "Eigenes Modell"
            f.add_trace(go.Scatter(x=px_, y=py_, mode="lines+markers", line=dict(color=col, width=2.4, dash=dash),
                                   marker=dict(size=[0] + [7] * (a1 - a0), color=col, line=dict(color="#fff", width=1.5)), customdata=cd, name=src,
                                   hovertemplate=f"{src}: %{{y:,.1f}} {unit}<br>Spanne: %{{customdata[0]:,.1f}} – %{{customdata[1]:,.1f}} {unit}<extra></extra>"))
        if 0 < nc < len(fx):
            f.add_vline(x=fx[nc - 1], line=dict(color="#98a2b3", width=1.2, dash="dot"))
            f.add_annotation(x=fx[nc - 1], y=1, yref="paper", xanchor="right", yanchor="top", xshift=-6, yshift=-20, showarrow=False, text="Konsens", font=dict(size=11, color=BLUE))
            f.add_annotation(x=fx[nc - 1], y=1, yref="paper", xanchor="left", yanchor="top", xshift=6, yshift=-20, showarrow=False, text="Modell", font=dict(size=11, color="#e8892c"))
    allv = [v for v in list(hy) + list(fhi) if v is not None]
    f.update_layout(**layout(h, title=dict(text=title, x=.5, font=dict(size=13, color=INK)),
                              yaxis=dict(gridcolor=GRID, tickformat=yfmt, range=[0, max(allv) * 1.08]),
                              xaxis=dict(showgrid=False, tickformat="%Y", dtick="M12", tick0=xs_all[-1], range=[xs_all[0], xs_all[-1] + pd.Timedelta(days=75)])))
    return unified(f, header)
