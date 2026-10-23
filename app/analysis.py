"""Produktteil A: Aktienanalyse. Reine Analyse: Fakten, Bewertungsmodelle, Analysten, Szenarien, Finanzdaten. Keine Urteile, keine Einstiegsdaten."""
import os
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from lib import (pad_right, pchart, inote, ka, KA_NOTE, prices, prices_long, load_v3, fields, fnum, fprice, fpct, fmult, fbig, fdate, plain, table, h2, pill, arrow, spark,
                 stock_head, footer2, plot_layout, PLOT_CFG, FONT, sector_de, ii)
import lwchart
import ag_style as agx
import common
import valuation_ui, fairvalue
from common import META, CASES

TABS = ["Übersicht", "Analysten", "Bewertung", "Szenarien", "Finanzdaten"]
BLUE, BLUE_L, GREEN, RED, GREY, INK = "#337ab7", "#9cc0e2", "#2e9e5b", "#d64541", "#98a2b3", "#1d2939"
MON = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
GRADE = {"Buy": "Kaufen", "Strong Buy": "Starker Kauf", "Hold": "Halten", "Sell": "Verkaufen", "Strong Sell": "Starker Verkauf",
         "Overweight": "Übergewichten", "Underweight": "Untergewichten", "Equal-Weight": "Marktgewichten", "Equal Weight": "Marktgewichten",
         "Neutral": "Neutral", "Outperform": "Outperform", "Underperform": "Underperform", "Market Perform": "Marktperformance",
         "Sector Perform": "Sektorperformance", "Peer Perform": "Peer Perform", "Market Outperform": "Outperform", "Positive": "Positiv",
         "Sector Outperform": "Sektor-Outperform", "Sector Weight": "Sektorgewichtung"}

def cons(sym): return load_v3()[1][sym]
def chg(sym):
    px = prices(sym); return px.close.iloc[-1] / px.close.iloc[-2] - 1
def pe(c):
    e = c["keystats"].get("eps_ttm"); return c["price"] / e if e else None

def fig_base(h, **kw):
    base = dict(height=h, margin=dict(l=4, r=4, t=10, b=4), showlegend=False, font=dict(family=FONT, size=12, color="#5d6b7e"))
    base.update(kw); return plot_layout(**base)

# ================================================================ Startseite (ohne Aktie)
def overview():
    agx.inject()
    st.markdown(f'<h1 class="ptitle">Aktienanalyse</h1><p class="muted">Schlusskurse vom {fdate(META["asof"])}</p>', unsafe_allow_html=True)
    cols = st.columns(len(common.FEATURED), gap="small")
    for col, (s, c) in zip(cols, ((s_, CASES[s_]) for s_ in common.FEATURED)):
        px = prices(s); t = cons(s)["targets"]
        with col.container(key=f"agcardbtn_{s}"):
            st.markdown(f'<div class="card tcard"><div class="top"><div style="min-width:0"><div class="tk">{s}</div><div class="nm">{c["name"]}</div></div>'
                        f'<span class="mono">{s[:2]}</span></div>'
                        f'<div style="display:flex;justify-content:space-between;align-items:flex-end;gap:6px;margin:4px 0 8px"><div><div style="font-size:18px;font-weight:700;color:#1d2939;white-space:nowrap">{fnum(c["price"])} <span style="font-size:13px">{c["currency"]}</span></div>'
                        f'<div style="margin-top:4px">{pill(chg(s))}</div></div>{spark(px.close.tail(63).tolist(), 64, 30)}</div>'
                        f'<div class="row"><span>Börsenwert</span><b>{fbig(c["keystats"]["mcap"], "")}</b></div>'
                        f'<div class="row"><span>KGV (12 M.)</span><b>{fmult(pe(c))}</b></div>'
                        f'<div class="row"><span>Kursziel</span><b>{fnum(t.get("median"))}</b></div></div>', unsafe_allow_html=True)
            if st.button(f'{c["name"]}', key=f"open_{s}"):
                common.set_ticker(s); st.rerun()
    h2("Vergleich", None, info=f"Kennzahlen zum Schlusskurs, letzte 12 Monate. Kursziel = Median der Analysten. Kurse und Beträge in der Handelswährung der Aktie. ¹ {KA_NOTE}")
    rows = []
    _pool = sorted(CASES, key=lambda s_: -((CASES[s_].get("keystats") or {}).get("mcap") or 0))   # ganzer Pool: nach Börsenwert
    if len(CASES) > len(common.FEATURED): _pool, _tot = common.pool_filter(_pool, "ab")
    else: _tot = len(_pool)
    for s in _pool:
        c = CASES[s]; k = c["keystats"]; t = (load_v3()[1].get(s) or {}).get("targets") or {}
        rows.append({"Aktie": f"<a class='rl' href='/aktienanalyse?t={s}' target='_self'><b>{s}</b> <span class='muted'>{c['name'].split(' (')[0][:26]}</span></a>", "Kurs": fnum(c["price"]),
                     "Börsenwert": fbig(k["mcap"], ""), "KGV": fmult(pe(c)), "Forward-KGV": ka(k.get("pe_fwd"), fmult), "KUV": fmult(k["ps_ttm"]),
                     "Umsatz-Wachstum": arrow(k["rev_yoy"]), "Nettomarge": fpct(k["net_margin"]),
                     "Fairer Wert": fnum((fairvalue.get(s) or {}).get("base"), 0), "Kursziel": fnum(t.get("median")),
                     "Potenzial": arrow(t["median"] / c["price"] - 1) if t.get("median") else "k. A."})
    if rows: st.markdown(table(rows, list(rows[0]), align={k: "r" for k in list(rows[0])[1:]}), unsafe_allow_html=True)
    else: st.markdown('<div class="bfoot">Keine Treffer für diese Auswahl.</div>', unsafe_allow_html=True)
    if _tot > len(common.FEATURED): st.markdown(f'<div class="bfoot" style="font-size:12.5px;color:#5d6b7e;margin:8px 0">{len(rows)} von {fnum(_tot, 0)} Treffern, sortiert nach Börsenwert</div>', unsafe_allow_html=True)
    common.more("ab", _tot)
    footer2(META)

# ================================================================ Detail
def detail(sym):
    agx.inject()
    c = CASES[sym]
    l, r = st.columns([5, 1.1], vertical_alignment="top")
    with l: agx.head(c, prices(sym))
    with r:
        st.markdown('<div style="height:22px"></div>', unsafe_allow_html=True)
        if st.button("Swing-Tool", key="to_swing", width="stretch", type="primary"):
            common.go("swing", sym)
    q = st.query_params.get("tab")
    key = f"tab_{sym}"
    if q in TABS: st.session_state[key] = q          # URL ist maßgeblich: Deep-Link, Neuladen, Zurück/Vor
    elif key not in st.session_state: st.session_state[key] = "Übersicht"
    def _tab():
        v = st.session_state.get(key) or "Übersicht"; st.session_state[key] = v
        st.query_params["tab"] = v
    with st.container(key="tabs"):
        tab = st.segmented_control("Bereich", TABS, key=key, on_change=_tab, label_visibility="collapsed") or "Übersicht"
    {"Übersicht": t_overview, "Analysten": t_analyst, "Bewertung": valuation_ui.render, "Szenarien": t_scen, "Finanzdaten": t_data}[tab](c, sym)
    footer2(META)


# ---------------------------------------------------------------- Übersicht
def more(key, n_more=None, label="Mehr anzeigen"):
    """'Mehr anzeigen / Weniger anzeigen': reduziert die Dichte beim ersten Blick."""
    k = f"more_{key}"; on = st.session_state.get(k, False)
    lab = "Weniger anzeigen" if on else (label + (f" ({n_more})" if n_more else ""))
    with st.container(key=f"morebtn_{key}"):
        if st.button(lab, key=f"btn_{k}", type="tertiary", icon=":material/expand_less:" if on else ":material/expand_more:"):
            st.session_state[k] = not on; st.rerun()
    return on

INFO = {
 "Börsenwert": "Marktwert aller Aktien: Kurs × Anzahl Aktien.",
 "KGV": "Kurs-Gewinn-Verhältnis: Kurs ÷ Gewinn je Aktie der letzten 12 Monate. Zeigt, wie viele Jahresgewinne der Kurs enthält.",
 "Umsatz": "Erlöse der letzten 12 Monate laut SEC-Abschlüssen (Summe der letzten vier Quartale).",
 "Nettomarge": "Nettogewinn ÷ Umsatz. Anteil des Umsatzes, der nach allen Kosten und Steuern bleibt.",
 "Gewinn je Aktie": "Nettogewinn ÷ verwässerte Aktienanzahl (US-GAAP, laut SEC-Abschluss).",
 "Free Cashflow": "Operativer Cashflow − Investitionen (Capex). Geld, das für Rückkäufe, Dividenden oder Schuldenabbau frei ist.",
 "Bruttomarge": "(Umsatz − Herstellkosten) ÷ Umsatz.",
 "Operative Marge": "Operatives Ergebnis (EBIT) ÷ Umsatz.",
 "Kapitalrendite (ROIC)": "Operatives Ergebnis nach Steuern ÷ investiertes Kapital (Eigenkapital + Schulden − Cash).",
 "Aktienrückkäufe": "Ausgaben für den Rückkauf eigener Aktien im Geschäftsjahr (Cashflow-Rechnung).",
 "Aktien (verwässert)": "Durchschnittliche Aktienanzahl inklusive Optionen und Wandelrechten.",
}
def kpi(label, value, sub="", extra="", info=None):
    info = info or next((v for k_, v in INFO.items() if label.startswith(k_)), None)
    label = label + (ii(info) if info else "")
    return f'<div class="kpi"><div class="l">{label}</div><div class="v">{value}</div><div class="s"><span>{sub}</span>{extra}</div></div>'

def kc(title, rows):
    return f'<div class="kc"><div class="h3">{title}</div>' + "".join(f'<div class="row"><span>{a}</span><b>{b}</b></div>' for a, b in rows) + "</div>"

def t_overview(c, sym):
    k = c["keystats"]; cur = c["currency"]; cs = cons(sym); an = c["annual"]
    lwchart.render_clean(prices_long(sym), height=430, cur=cur)
    h2("Kennzahlen", None, info="Letzte 12 Monate, bewertet zum Schlusskurs. Basis-Kennzahlen aus den letzten vier Quartalsabschlüssen (SEC) und dem Schlusskurs. Weitere Werte über „Mehr anzeigen“.")
    last = an[-1] if an else {}
    div_y = (last.get("dividends_paid") or 0) / k["mcap"] if k.get("mcap") else None
    bb_y = ((last.get("buybacks") or 0) + (last.get("dividends_paid") or 0)) / k["mcap"] if k.get("mcap") else None
    st.markdown('<div class="kpis">' + kpi("Börsenwert", fbig(k["mcap"], ""), cur) + kpi("KGV", fmult(pe(c)), f'Forward-KGV {fmult(fpe12(c, sym)) if fpe12(c, sym) else "k. A."}',
                info=f'Kurs ÷ Gewinn je Aktie (letzte 12 Monate): {fnum(c["price"])} ÷ {fnum(k["eps_ttm"])} = {fmult(pe(c))}. Forward-KGV = Kurs ÷ Konsens-Gewinn je Aktie der nächsten 12 Monate (zeitgewichtet aus laufendem und nächstem Geschäftsjahr).')
                + kpi("Umsatz", fbig(k["revenue_ttm"], ""), f'{arrow(k["rev_yoy"])} ggü. Vorjahr') + kpi("Nettomarge", fpct(k["net_margin"]), f'ROIC {fpct(k["roic"])}')
                + "</div>", unsafe_allow_html=True)
    with agx.acc_ctx("kennzahlen", "Alle Kennzahlen", "18 Kennzahlen zu Basis, Bewertung, Rentabilität und Ausschüttung."):
        st.markdown('<div class="kcards">'
          + kc("Basis", [("Börsenwert", fbig(k["mcap"], cur)), ("Unternehmenswert (EV)", fbig(k["ev"], cur)), ("Umsatz", fbig(k["revenue_ttm"], cur)),
                         ("Nettogewinn", fbig(k["net_income_ttm"], cur)), ("Free Cashflow", fbig(k["fcf_ttm"], cur)), ("Gewinn je Aktie", fprice(k["eps_ttm"], cur))])
          + kc("Bewertung", [("KGV", fmult(pe(c))), ("Forward-KGV (12 Monate)", fmult(fpe12(c, sym)) if fpe12(c, sym) else "k. A."), ("KGV historisch (Median)", fmult(k.get("pe_hist_median"))),
                             ("KUV", fmult(k["ps_ttm"])), ("FCF-Rendite", fpct(k["fcf_yield"])), ("Fairer Wert (Bewertung)", fprice((fairvalue.get(sym) or {}).get("base"), cur, 0))])
          + kc("Rentabilität und Ausschüttung", [("Bruttomarge", fpct(k.get("gross_margin"))), ("Nettomarge", fpct(k["net_margin"])),
                             ("Kapitalrendite (ROIC)", fpct(k["roic"])), ("Eigenkapitalrendite", fpct(k["roe"])),
                             ("Dividendenrendite", fpct(div_y, 2) if div_y else "keine Dividende"), ("Ausschüttung inkl. Rückkäufe", fpct(bb_y, 1))])
          + "</div>", unsafe_allow_html=True)
    l, r = st.columns([1, 1], gap="large")
    with r:
        h2("Termine")
        ev = [(c["next_earnings"], "Quartalszahlen", "nächster Termin (Unternehmensangabe)")]
        _h = earnings(sym).get("history") or []
        if _h: ev.append((_h[0]["date"], "Quartalszahlen veröffentlicht", "letzter Bericht"))
        if an: ev.append((an[-1]["fy_end"], f'Geschäftsjahr {an[-1]["fy_end"][:4]} beendet', "letzter Jahresabschluss (SEC EDGAR)"))
        html = ""
        for d, t, s in sorted(ev, key=lambda x: x[0], reverse=True):
            ts = pd.Timestamp(d)
            html += f'<div class="ev"><div class="d"><b>{ts.day:02d}</b><span>{MON[ts.month - 1]} {str(ts.year)[2:]}</span></div><div class="t">{t}<span>{s} · {fdate(d)}</span></div></div>'
        st.markdown(f'<div class="card">{html}</div>', unsafe_allow_html=True)
        e = earnings(sym); seen = set(); peers = []
        for p_ in e.get("peers", []):
            if p_["name"] in seen or p_["symbol"] == sym: continue
            seen.add(p_["name"]); peers.append(p_)
        if peers:
            with agx.acc_ctx("peers", "Zahlentermine im selben Sektor", "Nächste drei Wochen."):
                st.markdown('<div class="h3" style="margin:10px 0 4px">Zahlentermine im selben Sektor (nächste drei Wochen)</div>'
                            + table([{"Datum": fdate(p_["date"]), "Unternehmen": f'<b>{p_["symbol"]}</b> <span class="muted">{p_["name"]}</span>'} for p_ in peers[:6]], ["Datum", "Unternehmen"]), unsafe_allow_html=True)
    with l:
        h2("Analysten in Kürze")
        t = cs["targets"]; rec = cs["rec"]["0m"]; tot = sum(v or 0 for v in rec.values())
        b = (rec["strongBuy"] or 0) + (rec["buy"] or 0); hld = rec["hold"] or 0; s_ = (rec["sell"] or 0) + (rec["strongSell"] or 0)
        st.markdown(f'<div class="card">{rating_bars(rec)}<table class="kt" style="margin-top:8px">'
                    f'<tr><td>Kursziel (Median)</td><td class="r">{fprice(t.get("median"), cur)}</td></tr>'
                    f'<tr><td>Kurspotenzial</td><td class="r">{pill(t["median"] / c["price"] - 1) if t.get("median") else "k. A."}</td></tr>'
                    f'<tr><td>Anzahl Einstufungen</td><td class="r">{fnum(tot, 0)}</td></tr></table></div>', unsafe_allow_html=True)
    hist = earnings(sym).get("history") or []
    if hist:
        h2("Vergangene Quartalszahlen", None,
           info="Gewinn je Aktie: Schätzung vor dem Termin und gemeldeter Wert; Kursreaktion am folgenden Handelstag. Schätzung = Konsens vor dem Termin; gemeldet = Wert laut Datenquelle (häufig GAAP, die Schätzung oft bereinigt; Sondereffekte erzeugen große Abweichungen). Reaktion = Schlusskurs am ersten Handelstag nach dem Termin ÷ Schlusskurs am Termintag − 1.")
        r_ = [h["reaction"] for h in hist if h.get("reaction") is not None]
    if hist:
        with agx.acc_ctx("zahlen", "Schätzung und Ist je Quartal", "Gewinn je Aktie je Quartal; Kursreaktion im Tooltip."):
            hx = list(reversed(hist)); X_ = [fdate(h["date"]) for h in hx]
            f = go.Figure()
            f.add_trace(go.Bar(x=X_, y=[h["eps_est"] for h in hx], name="Schätzung", marker_color="#c9d3df", hovertemplate=agx.tpl("Schätzung", ",.2f", c["currency"])))
            f.add_trace(go.Bar(x=X_, y=[h["eps_rep"] for h in hx], name="Gemeldet", marker_color=BLUE, customdata=[fpct(h["reaction"], 1, True) if h.get("reaction") is not None else "–" for h in hx], hovertemplate=f"Gemeldet: %{{y:,.2f}} {c['currency']}<br>Kursreaktion: %{{customdata}}<extra></extra>"))
            f.update_layout(**fig_base(320, barmode="group", bargap=.35, showlegend=True, legend=dict(orientation="h", y=1.12, x=0), xaxis=dict(type="category"),
                                       yaxis=dict(gridcolor="#eef2f6", range=[0, max(max(h["eps_est"] or 0, h["eps_rep"] or 0) for h in hx) * 1.25])))
            pchart(agx.unified(f), width="stretch", config=PLOT_CFG)
    if an:
        h2("Umsatz und Gewinn", None, info="Geschäftsjahre laut SEC-Abschluss, Beträge in Mrd. " + cur)
        yrs = [r["fy_end"][:4] for r in an]
        f = go.Figure()
        f.add_trace(go.Bar(x=yrs, y=[r["revenue"] / 1e9 for r in an], name="Umsatz", marker_color=BLUE, text=[fnum(r["revenue"] / 1e9, 1) for r in an], textposition="outside", cliponaxis=False, hovertemplate=agx.tpl("Umsatz", ",.1f", "Mrd. " + cur)))
        f.add_trace(go.Bar(x=yrs, y=[(r["net_margin"] or 0) * r["revenue"] / 1e9 for r in an], name="Nettogewinn", marker_color=BLUE_L,
                           text=[fnum((r["net_margin"] or 0) * r["revenue"] / 1e9, 1) for r in an], textposition="outside", cliponaxis=False, hovertemplate=agx.tpl("Nettogewinn", ",.1f", "Mrd. " + cur)))
        f.update_layout(**fig_base(400, barmode="group", bargap=.3, showlegend=True, legend=dict(orientation="h", y=1.12, x=0),
                                   yaxis=dict(gridcolor="#eef2f6", tickformat=",.0f"), xaxis=dict(type="category")))
        pchart(agx.unified(f), width="stretch", config=PLOT_CFG)

# ---------------------------------------------------------------- Analysten
RATING = (("strongBuy", "Starker Kauf", "#1f7a45"), ("buy", "Kaufen", "#3f9f5f"), ("hold", "Halten", "#e8b23a"),
          ("sell", "Verkaufen", "#e8803a"), ("strongSell", "Starker Verkauf", "#c0392b"))
def rating_bars(rec):
    tot = sum(rec.get(k) or 0 for k, _, _ in RATING)
    if not tot: return '<p class="muted">Einstufungen: k. A.</p>'
    return "".join(f'<div class="agrt"><span>{lab}</span><div class="bar"><i style="width:{(rec.get(k) or 0) / tot * 100:.1f}%;background:{col}"></i></div>'
                   f'<b>{fnum((rec.get(k) or 0) / tot * 100, 0)} %</b></div>' for k, lab, col in RATING)

def period_toggle(sym):
    """Quartal | Jährlich wie bei aktien.guide, oben rechts; Zustand in der URL (?per=)."""
    key = f"per_{sym}"
    q = {"Jahr": "Jährlich"}.get(st.query_params.get("per"), st.query_params.get("per"))
    if q in ("Quartal", "Jährlich"): st.session_state[key] = q
    elif key not in st.session_state: st.session_state[key] = "Jährlich"
    def _per(): st.query_params["per"] = st.session_state.get(key) or "Jährlich"
    with st.container(key=f"agper_{sym}"):
        return st.segmented_control("Zeitraum", ["Quartal", "Jährlich"], key=key, on_change=_per, label_visibility="collapsed") or "Jährlich"

def scen_path(c, sym, key):
    """Umsatz- und Margenpfad eines Szenarios über die fünf modellierten Jahre ab dem letzten Ist-Jahr (Mrd., %). Keine Fortschreibung danach."""
    an = c["annual"]; b = c["scenarios"][key]; y1 = int(an[-1]["fy_end"][:4]) + 1
    r = an[-1]["revenue"] / 1e9; m0 = (an[-1].get("net_margin") or 0) * 100; out = {}
    for yr in range(y1, y1 + 5):
        t = yr - y1 + 1; g = b["g_start"] + (b["g_end"] - b["g_start"]) * (min(t, 5) - 1) / 4
        r *= 1 + g; out[yr] = (r, m0 + (b["margin"] * 100 - m0) * min(1, t / 5))
    return out

def fc_data(c, sym, quarter):
    """Ist (Jahr oder TTM je Quartal), Konsens-Jahre mit Spanne tief–hoch, danach Basisszenario mit Spanne konservativ–positiv."""
    an = c["annual"]; ys = [y for y in cons(sym)["years"] if y.get("rev")]; sh = an[-1].get("diluted_shares")
    if quarter:
        q = quarters(sym)
        hx, hy, hm = [], [], []
        for i in range(3, len(q)):
            w = q[i - 3:i + 1]; rv = sum(x["revenue"] for x in w)
            hx.append(pd.Timestamp(q[i]["end"])); hy.append(rv / 1e9)
            hm.append(sum(x["revenue"] * (x["net_margin"] or 0) for x in w) / rv * 100)
    else:
        hx = [pd.Timestamp(r_["fy_end"]) for r_ in an[-6:]]; hy = [r_["revenue"] / 1e9 for r_ in an[-6:]]; hm = [(r_.get("net_margin") or 0) * 100 for r_ in an[-6:]]
    end = pd.Timestamp(an[-1]["fy_end"]); last_y = end.year
    fx, fy, flo, fhi, fm, fmlo, fmhi, kind = [], [], [], [], [], [], [], []
    for y in ys:
        if y["fy"] <= last_y: continue
        fx.append(end + pd.DateOffset(years=y["fy"] - last_y)); fy.append(y["rev"] / 1e9)
        flo.append((y.get("rev_low") or y["rev"]) / 1e9); fhi.append((y.get("rev_high") or y["rev"]) / 1e9)
        mm = y["eps"] * sh / y["rev"] * 100 if sh and y.get("eps") else None
        fm.append(mm); fmlo.append(y["eps_low"] * sh / y["rev"] * 100 if sh and y.get("eps_low") else mm); fmhi.append(y["eps_high"] * sh / y["rev"] * 100 if sh and y.get("eps_high") else mm)
        kind.append("Konsens")
    P = {k: scen_path(c, sym, k) for k in ("konservativ", "basis", "positiv")}
    last_c = max([y["fy"] for y in ys if y["fy"] > last_y] or [last_y])
    for yr in range(last_c + 1, last_y + 6):
        # Modelljahre: Pfad ab dem letzten Konsensjahr mit den Szenario-Wachstumsraten fortgeschrieben
        def grow(k, base):
            return base * P[k][yr][0] / P[k][yr - 1][0] if yr - 1 in P[k] else P[k][yr][0]
        fy.append(grow("basis", fy[-1] if fy else hy[-1])); flo.append(grow("konservativ", flo[-1] if flo else hy[-1])); fhi.append(grow("positiv", fhi[-1] if fhi else hy[-1]))
        fx.append(end + pd.DateOffset(years=yr - last_y))
        fm.append(P["basis"][yr][1]); fmlo.append(min(P["konservativ"][yr][1], P["positiv"][yr][1])); fmhi.append(max(P["konservativ"][yr][1], P["positiv"][yr][1]))
        kind.append("Modell")
    return dict(hx=hx, hy=hy, hm=hm, fx=fx, fy=fy, flo=flo, fhi=fhi, fm=fm, fmlo=fmlo, fmhi=fmhi, kind=kind, end=end)

FC_INFO = ("Ist-Werte laut SEC-Abschlüssen. Prognose: zuerst Analystenkonsens mit Spanne tiefste bis höchste Schätzung, "
           "danach eigenes Basisszenario mit Spanne konservativ bis positiv. Das Modell rechnet fünf Jahre; danach wird nichts fortgeschrieben. "
           "Konsens-Nettomarge = Konsens-Gewinn je Aktie × aktuelle Aktienanzahl ÷ Konsens-Umsatz (Näherung).")

FCQ_INFO = ("Ist-Werte je Quartal laut SEC-Quartalsberichten (10-Q; viertes Quartal aus dem 10-K abgeleitet). Prognose: Analystenkonsens (Durchschnitt) "
            "für das laufende und das nächste Quartal; Veränderung jeweils zum Vorjahresquartal. Für Quartale liegt keine Spanne des Umsatzkonsens vor.")

def q_cons(c, sym):
    """Konsens für laufendes und nächstes Quartal mit Quartalsende (aus dem letzten gemeldeten Quartal fortgezählt)."""
    q = quarters(sym); qs = [x for x in ((c.get("analyst") or {}).get("quarters") or []) if x.get("rev_avg")]
    if not q or not qs: return []
    end = pd.Timestamp(q[-1]["end"]); out = []
    for i, x in enumerate(qs[:2], start=1):
        e = (end + pd.DateOffset(months=3 * i)) + pd.offsets.MonthEnd(0)
        out.append({**x, "end": e, "qlab": f"Q{(e.month - 1) // 3 + 1} {e.year}"})
    return out

def forecast_block_q(c, sym):
    """Quartalsansicht: Umsatz je Quartal (Ist) und Konsens der nächsten zwei Quartale; Tabelle mit Quartalsspalten."""
    cur = c["currency"]; q = quarters(sym)[-12:]; qc = q_cons(c, sym); sh = c["annual"][-1].get("diluted_shares")
    hx = [pd.Timestamp(x["end"]) for x in q]; hy = [x["revenue"] / 1e9 for x in q]
    fx = [x["end"] for x in qc]; fy = [x["rev_avg"] / 1e9 for x in qc]
    l, r = st.columns([1.7, 1], gap="medium", vertical_alignment="top")
    with l:
        f = agx.forecast_fig(f'{c["name"].split(" (")[0]} – Umsatz je Quartal (Mrd. {cur})', hx, hy, fx, fy, fy, fy, f"Mrd. {cur}", hx[-1], h=420, name="Umsatz",
                             header="%{x|%m/%Y}", n_cons=len(fx))
        pchart(f, width="stretch", config=PLOT_CFG)
    with r:
        last = q[-1]; ya = q[-5] if len(q) >= 5 else None
        cols = [last["label"]] + [f'{x["qlab"]}<br>Prognose' for x in qc]
        rev = [last["revenue"] / 1e9] + fy
        rg = [last["revenue"] / ya["revenue"] - 1 if ya else None] + [x["rev_avg"] / x["rev_year_ago"] - 1 if x.get("rev_year_ago") else None for x in qc]
        eps = [last["eps"]] + [x["eps_avg"] for x in qc]
        eg = [last["eps"] / ya["eps"] - 1 if ya and ya.get("eps") and ya["eps"] > 0 else None] + [x["eps_avg"] / x["eps_year_ago"] - 1 if x.get("eps_year_ago") and x["eps_year_ago"] > 0 else None for x in qc]
        nm = [(last.get("net_margin") or 0) * 100] + [x["eps_avg"] * sh / x["rev_avg"] * 100 if sh else None for x in qc]
        st.markdown('<div style="height:34px"></div>' + agx.fc_table(cols, [
            ("Umsatz", f"Mrd. {cur}", [fnum(v, 2) for v in rev], [pill(g) if g is not None else "" for g in rg]),
            ("Nettomarge", "", [f"{fnum(v, 2)} %" if v is not None else "k. A." for v in nm], [""] * len(nm)),
            ("Gewinn je Aktie", cur, [fnum(v, 2) for v in eps], [pill(g) if g is not None else "" for g in eg])]), unsafe_allow_html=True)
    return q, qc

def forecast_accordions_q(c, sym, q, qc, key):
    cur = c["currency"]; nm = c["name"].split(" (")[0]
    rows, tags = [], []
    for i, x in enumerate(q[-6:]):
        j = len(q) - 6 + i; ya = q[j - 4] if j >= 4 else None
        rows.append((x["label"], f'{fnum(x["revenue"] / 1e9, 1)} Mrd. {cur}', pill(x["revenue"] / ya["revenue"] - 1) if ya else "", None)); tags.append("Ist")
    for x in qc:
        rows.append((x["qlab"], f'{fnum(x["rev_avg"] / 1e9, 1)} Mrd. {cur}', pill(x["rev_avg"] / x["rev_year_ago"] - 1) if x.get("rev_year_ago") else "",
                     f'Konsens von {fnum(x["rev_n"], 0)} Analysten')); tags.append("Konsens")
    x0 = qc[0] if qc else None
    s1 = (f'{fnum(x0["rev_n"], 0)} Analysten erwarten für {nm} im {x0["qlab"]} einen Umsatz von {fnum(x0["rev_avg"] / 1e9, 1)} Mrd. {cur}, '
          f'das sind {pill(x0["rev_avg"] / x0["rev_year_ago"] - 1)} gegenüber dem Vorjahresquartal. Veränderung in der Tabelle jeweils zum Vorjahresquartal:' if x0 and x0.get("rev_year_ago") else "Quartalskonsens: k. A.")
    agx.acc(f"{key}_qrev", "Umsatz je Quartal", s1, agx.pill_table("Umsatz je Quartal", rows, tags=tags), expanded=True)
    rows, tags = [], []
    for i, x in enumerate(q[-6:]):
        j = len(q) - 6 + i; ya = q[j - 4] if j >= 4 else None
        rows.append((x["label"], f'{fnum(x["eps"])} {cur}', pill(x["eps"] / ya["eps"] - 1) if ya and ya.get("eps") and ya["eps"] > 0 else "", None)); tags.append("Ist")
    for x in qc:
        rows.append((x["qlab"], f'{fnum(x["eps_avg"])} {cur}', pill(x["eps_avg"] / x["eps_year_ago"] - 1) if x.get("eps_year_ago") and x["eps_year_ago"] > 0 else "",
                     f'Spanne {fnum(x["eps_low"])} bis {fnum(x["eps_high"])} {cur}, {fnum(x["eps_n"], 0)} Analysten; Konsens häufig bereinigt')); tags.append("Konsens")
    s2 = (f'Für das {x0["qlab"]} liegt der Konsens für den Gewinn je Aktie bei {fnum(x0["eps_avg"])} {cur}, die Spanne reicht von {fnum(x0["eps_low"])} bis {fnum(x0["eps_high"])} {cur}.' if x0 else "")
    agx.acc(f"{key}_qeps", "Gewinn je Aktie je Quartal", s2, agx.pill_table("Gewinn je Aktie", rows, tags=tags))

def forecast_block(c, sym, title_prefix="", toggle=True, accordions_key=None):
    """Umsatz- und Margenprognose: Chart links (Prognosebereich + Band), Toggle und kompakte Tabelle rechts. Toggle nur, wo Quartalsdaten die Ansicht wirklich ändern."""
    cur = c["currency"]; name = c["name"]
    has_q = toggle and len(quarters(sym)) >= 8 and bool(q_cons(c, sym))
    hl, hr = st.columns([3, 1], vertical_alignment="bottom")
    per = "Jährlich"
    if has_q:
        with hr: per = period_toggle(sym)
    quarter = per == "Quartal"
    end_y = int(c["annual"][-1]["fy_end"][:4]) + 5
    with hl: agx.sec(f"{title_prefix}Umsatz- und Margenprognose" + (" je Quartal" if quarter else f" bis {end_y}"), FCQ_INFO if quarter else FC_INFO)
    if quarter:
        q, qc = forecast_block_q(c, sym)
        if accordions_key: forecast_accordions_q(c, sym, q, qc, accordions_key)
        return None, None
    d = fc_data(c, sym, False)
    l, r = st.columns([1.7, 1], gap="medium", vertical_alignment="top")
    with l:
        f = agx.forecast_fig(f'{name.split(" (")[0]} – {"TTM" if quarter else "Geschäftsjahr"} (Mrd. {cur})', d["hx"], d["hy"], d["fx"], d["fy"], d["flo"], d["fhi"],
                             f"Mrd. {cur}", d["hx"][-1], h=420, name="Umsatz", header="%{x|%m/%Y}" if quarter else "Geschäftsjahr %{x|%Y}", n_cons=d["kind"].count("Konsens"))
        pchart(f, width="stretch", config=PLOT_CFG)
    an = c["annual"]; ys = [y for y in cons(sym)["years"] if y.get("rev") and y["fy"] > int(an[-1]["fy_end"][:4])]
    with r:
        lab0 = d["end"].strftime("%b '%y").replace("Dec", "Dez").replace("Mar", "Mär").replace("May", "Mai").replace("Oct", "Okt")
        cols = [lab0] + [f'{y["fy"]}<br>Prognose' for y in ys[:2]]
        r0, r1 = an[-1], (an[-2] if len(an) > 1 else {})
        rev = [r0["revenue"] / 1e9] + [y["rev"] / 1e9 for y in ys[:2]]
        rg = [r0["revenue"] / r1["revenue"] - 1 if r1.get("revenue") else None] + [rev[i + 1] / rev[i] - 1 for i in range(len(ys[:2]))]
        nm = [(r0.get("net_margin") or 0) * 100] + d["fm"][:len(ys[:2])]
        nm_prev = (r1.get("net_margin") or 0) * 100 if r1 else None
        nmc = [nm[0] - nm_prev if nm_prev is not None else None] + [(nm[i + 1] - nm[i]) if nm[i + 1] is not None else None for i in range(len(ys[:2]))]
        eps = [r0.get("eps_diluted")] + [y.get("eps") for y in ys[:2]]
        eg = [r0["eps_diluted"] / r1["eps_diluted"] - 1 if r1.get("eps_diluted") and r1["eps_diluted"] > 0 else None] + [y.get("eps_growth") for y in ys[:2]]
        pp = lambda x: pill(x / 100, txt=f'{fnum(abs(x), 2)} Pp.') if x is not None else ""
        st.markdown('<div style="height:34px"></div>' + agx.fc_table(cols, [
            ("Umsatz", f"Mrd. {cur}", [fnum(v, 2) for v in rev], [pill(g) for g in rg]),
            ("Nettomarge", "", [f"{fnum(v, 2)} %" if v is not None else "k. A." for v in nm], [pp(x) for x in nmc]),
            ("Gewinn je Aktie", cur, [fnum(v, 2) for v in eps], [pill(g) if g is not None else "" for g in eg])]), unsafe_allow_html=True)
    return d, ys

def growth_rows(xs, vals, unit, info_fn=None, d=0):
    out = []
    for i, (x, v) in enumerate(zip(xs, vals)):
        g = vals[i] / vals[i - 1] - 1 if i and vals[i - 1] and vals[i - 1] > 0 and v is not None else None
        out.append((x, f"{fnum(v, d)} {unit}" if v is not None else "k. A.", pill(g) if g is not None else "", info_fn(x) if info_fn else None))
    return out

def forecast_accordions(c, sym, d, ys, key):
    cur = c["currency"]; nm = c["name"].split(" (")[0]; an = c["annual"]; ttm = (c["keystats"].get("revenue_ttm") or float("nan")) / 1e9
    y0 = ys[0] if ys else None
    yrs = [int(an[-1]["fy_end"][:4])] + [x.year for x in d["fx"]]
    vals = [an[-1]["revenue"] / 1e9] + d["fy"]
    def src(y):
        return "Analystenkonsens (Durchschnitt)" if any(v["fy"] == y for v in ys) else "Eigenes Basisszenario, keine Analystenprognose"
    def tag(y, i):
        return "Ist" if i == 0 else ("Konsens" if any(v["fy"] == y for v in ys) else "Modell")
    s1 = (f'{fnum(y0["rev_n"], 0)} Analysten haben eine {nm} Umsatzprognose {y0["fy"]} abgegeben. Die durchschnittliche Schätzung beträgt {fnum(y0["rev"] / 1e9, 0)} Mrd. {cur}. '
          f'Das ist {pill(y0["rev"] / 1e9 / ttm - 1)} höher als der Umsatz der letzten 12 Monate. Die höchste Umsatzprognose liegt bei {fnum(y0["rev_high"] / 1e9, 0)} Mrd. {cur} '
          f'{pill(y0["rev_high"] / 1e9 / ttm - 1)}, die niedrigste bei {fnum(y0["rev_low"] / 1e9, 0)} Mrd. {cur} {pill(y0["rev_low"] / 1e9 / ttm - 1)}.'
          if y0 and y0.get("rev_high") else "Umsatzprognose: k. A.")
    agx.acc(f"{key}_rev", "Umsatz & -wachstum", s1 + (f"<br><br>Daraus ergeben sich folgende potenzielle Wachstumszahlen. Bis {ys[-1]['fy']} Konsens der Analysten, ab {ys[-1]['fy'] + 1} eigenes Modell (Basisszenario), keine Analystenprognose:" if ys else ""),
            agx.pill_table("Umsatzprognose", growth_rows(yrs, vals, f"Mrd. {cur}", lambda y: None if y == yrs[0] else src(y)), tags=[tag(y, i) for i, y in enumerate(yrs)]), expanded=True)
    eps_y = [(int(r_["fy_end"][:4]), r_.get("eps_diluted")) for r_ in an[-1:]] + [(y["fy"], y.get("eps")) for y in ys]
    s2 = (f'{fnum(y0["eps_n"], 0)} Analysten schätzen den Gewinn je Aktie {y0["fy"]} auf durchschnittlich {fnum(y0["eps"])} {cur} {pill(y0.get("eps_growth"))}. '
          f'Die Spanne reicht von {fnum(y0["eps_low"])} bis {fnum(y0["eps_high"])} {cur}.' if y0 and y0.get("eps") else "Gewinnprognose: k. A.")
    agx.acc(f"{key}_eps", "Gewinn je Aktie & -wachstum", s2,
            agx.pill_table("Gewinn je Aktie", growth_rows([y for y, _ in eps_y], [v for _, v in eps_y], cur,
                           lambda y: "Ist: verwässert nach US-GAAP (SEC)" if y == eps_y[0][0] else "Konsens, häufig bereinigt; nur eingeschränkt mit dem Ist-Wert vergleichbar", d=2), tags=["Ist"] + ["Konsens"] * (len(eps_y) - 1)))
    mrows = [(y, f'{fnum(m, 1)} %' if m is not None else "k. A.", pill((m - pm) / 100, txt=f"{fnum(abs(m - pm), 1)} Pp.") if m is not None and pm is not None else "", None if i == 0 else src(y))
             for i, (y, m, pm) in enumerate(zip(yrs, [(an[-1].get("net_margin") or 0) * 100] + d["fm"], [None] + ([(an[-1].get("net_margin") or 0) * 100] + d["fm"])[:-1]))]
    s3 = f'Die Nettomarge lag im Geschäftsjahr {yrs[0]} bei {fpct(an[-1].get("net_margin"), 1)}. Im Basisszenario nähert sie sich bis {yrs[-1]} (Jahr 5 des Modells) {fpct(c["scenarios"]["basis"]["margin"], 1)}; danach wird nichts fortgeschrieben.'
    agx.acc(f"{key}_nm", "Nettomarge", s3, agx.pill_table("Nettomarge", mrows, tags=[tag(y, i) for i, y in enumerate(yrs)]))

def target_chart(c, sym):
    cs = cons(sym); t = cs["targets"]; px = prices_long(sym); cur = c["currency"]
    hist = px[px.date >= px.date.max() - pd.Timedelta(days=730)]
    d0, p0 = hist.date.iloc[-1], hist.close.iloc[-1]; d1 = d0 + pd.DateOffset(months=12)
    f = go.Figure()
    f.add_vrect(x0=d0, x1=d1, fillcolor="#f2f4f7", opacity=1, line_width=0, layer="below")
    f.add_annotation(x=d0, y=1, yref="paper", xanchor="left", yanchor="top", xshift=6, yshift=-4, showarrow=False, text="Prognose", font=dict(size=11, color="#5d6b7e"))
    f.add_trace(go.Scatter(x=hist.date, y=hist.close, mode="lines", line=dict(color=agx.BLUE, width=2), fill="tozeroy", fillcolor="rgba(61,111,182,.12)",
                           hovertemplate=agx.single("%{x|%d.%m.%Y}", "Schlusskurs", ",.2f", cur)))
    if t.get("high") and t.get("low"):
        f.add_trace(go.Scatter(x=[d0, d1, d1, d0], y=[p0, t["high"], t["low"], p0], fill="toself", fillcolor="rgba(46,158,91,.22)", line=dict(width=0), mode="lines", hoverinfo="skip"))
        f.add_trace(go.Scatter(x=[d0, d1, d1, d1], y=[p0, t["median"], t["high"], t["low"]], mode="markers", marker=dict(size=[0, 7, 0, 0], color=GREEN), hoverinfo="skip"))
        f.add_trace(go.Scatter(x=[d0, d1], y=[p0, t["median"]], mode="lines", line=dict(color=GREEN, width=1.8, dash="dot"),
                               customdata=[[t["low"], t["high"]]] * 2,
                               hovertemplate=f"<b>Kursziel 12 Monate</b><br>Median: %{{y:,.2f}} {cur}<br>Tief: %{{customdata[0]:,.2f}} {cur}<br>Hoch: %{{customdata[1]:,.2f}} {cur}<extra></extra>"))
        up = t["median"] / p0 - 1
        f.add_annotation(x=d1, y=t["median"], xanchor="right", yanchor="bottom", yshift=8, showarrow=False, text=f"{'↑' if up >= 0 else '↓'} {fpct(abs(up), 2)}",
                         font=dict(size=11.5, color=GREEN if up >= 0 else RED), bgcolor="#eaf6ee" if up >= 0 else "#fdecea", bordercolor=GREEN if up >= 0 else RED, borderwidth=1, borderpad=3)
    lo = min(hist.close.min(), t.get("low") or 1e9) * .9; hi = max(hist.close.max(), t.get("high") or 0) * 1.04
    f.update_layout(**agx.layout(440, title=dict(text=f'{c["name"]} – Kursziel ({cur})', x=.5, font=dict(size=13, color=INK)),
                                 yaxis=dict(range=[lo, hi], gridcolor="#eef2f6", tickformat=",.0f"),
                                 xaxis=dict(range=[hist.date.iloc[0], d1 + pd.Timedelta(days=12)], tickformat="%b %Y", showgrid=False)))
    pchart(f, width="stretch", config=PLOT_CFG)

def t_analyst(c, sym):
    cs = cons(sym); t = cs["targets"]; cur = c["currency"]; a = c["analyst"]; nm = c["name"]
    rec = cs["rec"]["0m"]; tot = sum(v or 0 for v in rec.values())
    agx.sec(f'{nm} Kursziel – Einstufung und Empfehlung von Analysten',
            f"Kursziele für die nächsten 12 Monate. Konsens-Snapshot vom {fdate(cs['snapshot'])}, öffentliche Konsensdaten. Die grüne Fläche verbindet den Schlusskurs mit dem tiefsten und höchsten Kursziel.")
    l, r = st.columns([1.7, 1], gap="medium", vertical_alignment="top")
    with l: target_chart(c, sym)
    with r:
        up = t["median"] / c["price"] - 1 if t.get("median") else None
        t30 = (a or {}).get("targets_30d") or {}
        st.markdown(f'<div class="agcard"><div class="t">{nm} Einstufungen &amp; Empfehlung{agx.ii(f"{fnum(tot, 0)} Einstufungen, Stand {fdate(cs["snapshot"])}.")}</div>{rating_bars(rec)}</div>'
                    f'<div class="agcard"><div class="t">{nm} Kursziel</div><table class="agkv">'
                    f'<tr><td>Kursziel (Median)</td><td class="r">{fprice(t.get("median"), cur)}</td></tr>'
                    f'<tr><td>Kurs</td><td class="r">{fprice(c["price"], cur)}</td></tr>'
                    f'<tr><td>Kurspotenzial</td><td class="r">{pill(up) if up is not None else "k. A."}</td></tr>'
                    f'<tr><td>Anzahl Schätzungen</td><td class="r">{fnum(cs.get("n_opinions"), 0)}</td></tr>'
                    + (f'<tr><td>Median letzte 30 Tage{agx.ii(f"{fnum(t30.get("n"), 0)} Kursziele aus den letzten 30 Tagen.")}</td><td class="r">{fprice(t30["median"], cur)}</td></tr>' if t30.get("median") else "")
                    + '</table></div>', unsafe_allow_html=True)
    if t.get("median"):
        g = lambda k: (rec.get(k) or 0)
        agx.box([("chart", f'{fnum(cs.get("n_opinions"), 0)} Analysten haben ein {nm} Kursziel abgegeben. Der Median liegt bei {fprice(t["median"], cur)}. Das sind {pill(up)} '
                           f'gegenüber dem Schlusskurs. Das höchste Kursziel liegt bei {fprice(t["high"], cur)} {pill(t["high"] / c["price"] - 1)}, das niedrigste bei {fprice(t["low"], cur)} {pill(t["low"] / c["price"] - 1)}.'),
                 ("info", f'Eine Einstufung wurde von {fnum(tot, 0)} Analysten vorgenommen: {fnum(g("strongBuy"), 0)} Starker Kauf, {fnum(g("buy"), 0)} Kaufen, {fnum(g("hold"), 0)} Halten, '
                          f'{fnum(g("sell"), 0)} Verkaufen und {fnum(g("strongSell"), 0)} Starker Verkauf.'),
                 ("alert", "Kursziele und Einstufungen sind Meinungen der Analysten, keine Prognose.")])
    d, ys = forecast_block(c, sym, accordions_key="an")
    if d is not None: forecast_accordions(c, sym, d, ys, "an")
    agx.sec("Hochstufungen und Abstufungen", "Die jüngsten Änderungen von Einstufung oder Kursziel bis zum Snapshot.")
    acts = cs["actions"]
    if acts:
        def gr(x):
            if not x: return "–"
            de_ = GRADE.get(x, x); low = x.lower()
            cls = "pos" if any(k in low for k in ("buy", "outperform", "overweight", "positive")) else "neg" if any(k in low for k in ("sell", "underperform", "underweight", "negative")) else "neu"
            return f'<span class="pill {cls}" style="font-size:12px">{de_}</span>'
        rows = [{"Datum": fdate(x["date"]), "Analysehaus": f"<b>{x['firm']}</b>", "Aktion": x["action"],
                 "Einstufung": (f'{gr(x["from_grade"])} → {gr(x["to_grade"])}' if x["from_grade"] and x["from_grade"] != x["to_grade"] else gr(x["to_grade"])),
                 "Kursziel": (f'{fnum(x["pt_prior"], 0)} → <b>{fnum(x["pt"], 0)}</b>' if x["pt_prior"] and x["pt"] and x["pt_prior"] != x["pt"] else (fnum(x["pt"], 0) if x["pt"] else "k. A.")),
                 "Änderung": arrow(x["pt"] / x["pt_prior"] - 1) if x["pt"] and x["pt_prior"] else "–"} for x in acts]
        st.markdown(table(rows[:5], list(rows[0]), align={"Kursziel": "r", "Änderung": "r"}), unsafe_allow_html=True)
        if len(rows) > 5:
            with agx.acc_ctx("aktionen", "Weitere Änderungen", "Ältere Änderungen von Einstufung und Kursziel."):
                st.markdown(table(rows[5:], list(rows[0]), align={"Kursziel": "r", "Änderung": "r"}), unsafe_allow_html=True)
    else:
        st.markdown('<p class="muted">k. A.</p>', unsafe_allow_html=True)
    def _q():
        qs = a.get("quarters") or []
        st.markdown(table([{"Zeitraum": f"<b>{ {'lfd. Quartal': 'laufendes Quartal'}.get(q['label'], q['label']) }</b>", "Gewinn je Aktie (Ø)": fnum(q["eps_avg"]),
                            "Spanne": f'{fnum(q["eps_low"])} – {fnum(q["eps_high"])}', "Analysten": fnum(q["eps_n"], 0), "Vorjahr": fnum(q["eps_year_ago"]),
                            "Umsatz (Ø)": fbig(q["rev_avg"], ""), "Umsatz-Revision 30 Tage": arrow(q.get("rev_30d"))} for q in qs],
                          ["Zeitraum", "Gewinn je Aktie (Ø)", "Spanne", "Analysten", "Vorjahr", "Umsatz (Ø)", "Umsatz-Revision 30 Tage"],
                          align={x: "r" for x in ["Gewinn je Aktie (Ø)", "Spanne", "Analysten", "Vorjahr", "Umsatz (Ø)", "Umsatz-Revision 30 Tage"]}), unsafe_allow_html=True)
        st.markdown(table([{"Monat": {"0m": "aktuell", "-1m": "vor 1 Monat", "-2m": "vor 2 Monaten", "-3m": "vor 3 Monaten"}[p_],
                            **{lab: fnum(v[k], 0) for k, lab, _ in RATING}} for p_, v in cs["rec"].items()],
                          ["Monat"] + [lab for _, lab, _ in RATING], align={lab: "r" for _, lab, _ in RATING}), unsafe_allow_html=True)
    qs = a.get("quarters") or []
    agx.acc("an_q", "Konsens je Quartal & Einstufungen im Zeitverlauf",
            f'Für das laufende Quartal erwarten {fnum(qs[0]["eps_n"], 0)} Analysten einen Gewinn je Aktie von {fnum(qs[0]["eps_avg"])} {cur} (Vorjahr {fnum(qs[0]["eps_year_ago"])} {cur}).' if qs else "", body=_q)


# ---------------------------------------------------------------- Bewertung
def earnings(sym):
    import json
    from lib import D as DATA
    if not hasattr(earnings, "_c"):
        p_ = DATA / "earnings.json"; earnings._c = json.loads(p_.read_text()) if p_.exists() else {}
    return earnings._c.get(sym) or {}

def pe_history(sym, years=5):
    """Tägliches KGV der letzten Jahre: Schlusskurs ÷ Gewinn je Aktie der letzten vier Quartale (verfügbar 45 Tage nach Quartalsende)."""
    q = [x for x in quarters(sym) if x.get("eps") and x.get("net_margin") is not None and x.get("revenue")]
    if len(q) < 4 + 4 * years: return None
    # Aktiensplits: ältere Quartale melden EPS vor dem Split. Implizite Aktienzahl = Nettogewinn ÷ EPS; springt sie um ganzzahlige Faktoren, wird das EPS angepasst.
    impl = [x["net_margin"] * x["revenue"] / x["eps"] for x in q]
    ref = impl[-1]
    eps = [x["eps"] / (round(ref / n) if n > 0 and ref / n > 1.8 else 1) for x, n in zip(q, impl)]
    ttm = pd.DataFrame({"avail": [pd.Timestamp(x["end"]) + pd.Timedelta(days=45) for x in q], "eps": eps})
    ttm["ttm"] = ttm.eps.rolling(4).sum(); ttm = ttm.dropna()
    px = prices_long(sym)[["date", "close"]].copy(); px["date"] = pd.to_datetime(px.date)
    px = px[px.date >= px.date.max() - pd.DateOffset(years=years)]
    if px.empty or ttm.avail.min() > px.date.min(): return None
    px["date"] = px.date.astype("datetime64[ns]"); ttm["avail"] = ttm.avail.astype("datetime64[ns]")
    m = pd.merge_asof(px.sort_values("date"), ttm.sort_values("avail")[["avail", "ttm"]], left_on="date", right_on="avail")
    m = m[m.ttm > 0]
    return (m.close / m.ttm) if len(m) > 200 else None

def fwd_eps(c, sym):
    """Konsens-Gewinn je Aktie: laufendes Geschäftsjahr, nächstes Geschäftsjahr und die nächsten 12 Monate (zeitgewichtet aus beiden)."""
    ys = [y for y in cons(sym).get("years", []) if y.get("eps")]
    if not ys: return None
    fy_end_m = pd.Timestamp(c["annual"][-1]["fy_end"]).month if c["annual"] else 12
    asof = pd.Timestamp(c["asof"]); e0 = pd.Timestamp(year=ys[0]["fy"], month=fy_end_m, day=1) + pd.offsets.MonthEnd(0)
    w = min(1, max(0, (e0 - asof).days / 365))
    ntm = ys[0]["eps"] * w + ys[1]["eps"] * (1 - w) if len(ys) > 1 else None
    return dict(fy0=ys[0], fy1=ys[1] if len(ys) > 1 else None, ntm=ntm, w=w)

def fpe12(c, sym):
    fe = fwd_eps(c, sym)
    return c["price"] / fe["ntm"] if fe and fe["ntm"] and fe["ntm"] > 0 else None

def kgv_block(c, sym, peh, cur_pe):
    """KGV-Einordnung in Worten mit Abstand zum 5-Jahres-Median, dazu Forward-KGV (12 Monate und Geschäftsjahre)."""
    p = c["price"]; fe = fwd_eps(c, sym); items = []
    if peh is not None:
        med = float(peh.median()); dlt = cur_pe / med - 1
        items.append(("chart", f'Das KGV von <b>{fmult(cur_pe)}</b> liegt {pill(dlt)} {"über" if dlt >= 0 else "unter"} dem Median der letzten fünf Jahre ({fmult(med)}). '
                               f'Spanne in diesem Zeitraum: {fmult(peh.min())} bis {fmult(peh.max())}.'
                               + ii("KGV je Handelstag = Schlusskurs ÷ Gewinn je Aktie der letzten vier Quartale laut SEC, jeweils ab 45 Tage nach Quartalsende. Tage mit negativem Gewinn sind nicht enthalten.")))
    if fe and fe["ntm"]:
        f12 = p / fe["ntm"]
        txt = (f'Forward-KGV (nächste 12 Monate): <b>{fmult(f12)}</b>, auf Basis des Konsens-Gewinns je Aktie von {fnum(fe["ntm"])} {c["currency"]}. '
               f'Geschäftsjahr {fe["fy0"]["fy"]}: {fmult(p / fe["fy0"]["eps"])}' + (f', {fe["fy1"]["fy"]}: {fmult(p / fe["fy1"]["eps"])}.' if fe["fy1"] else "."))
        if peh is not None:
            txt += f' Gegenüber dem KGV-Median der letzten fünf Jahre: {pill(f12 / float(peh.median()) - 1)}.'
        txt += ii(f'Forward-KGV = Schlusskurs ÷ erwarteter Gewinn je Aktie. 12 Monate: Konsens des laufenden und des nächsten Geschäftsjahres, zeitgewichtet '
                  f'({fnum(fe["w"] * 100, 0)} % / {fnum((1 - fe["w"]) * 100, 0)} %). Der Konsens ist häufig bereinigt, das KGV der Historie beruht auf GAAP-Gewinnen; '
                  'ein Verlauf des Forward-KGV liegt nicht vor (nur ein aktueller Konsens-Snapshot), daher der Vergleich mit dem Median des normalen KGV.')
        items.append(("target", txt))
    if items: agx.box(items)

def t_valuation(c, sym):
    """Bewertung: Hero (Wertspanne der gültigen Modelle vs. Kurs), Reverse-DCF, Chart nur gültiger Modelle, Annahmen kompakt, Details aufklappbar."""
    cur = c["currency"]; p = c["price"]; ok, na = common.models_of(c); s = c["scenarios"]; b = s["basis"]
    ok = sorted(ok, key=lambda m: m["value"])
    vals = [m["value"] for m in ok]
    h2("Bewertung", None, info=f"Fairer Wert je Aktie aus den Bewertungsmodellen, die für {c['name'].split(' (')[0]} einen Wert liefern · {cur} · Schlusskurs {fdate(c['asof'])}")
    if not ok:
        st.markdown('<p class="muted">Für diese Aktie liefert kein Modell einen Wert (k. A.).</p>', unsafe_allow_html=True); return
    med = c["models_median"] or float(pd.Series(vals).median())
    q1, q3 = (float(pd.Series(vals).quantile(x)) for x in (.25, .75))
    lo, hi = min(vals + [p]), max(vals + [p]); pad = (hi - lo) * .04; lo, hi = max(0, lo - pad), hi + pad
    pos = lambda v: f"{(v - lo) / (hi - lo) * 100:.2f}%"
    gap = med / p - 1
    st.markdown(f'''<div class="vhero"><div class="top">
      <div><div class="l">Median der Modelle{ii("Mittlerer Wert aller Bewertungsmodelle, die für diese Aktie einen fairen Wert je Aktie liefern. Jedes Modell rechnet mit 9 % Kapitalkosten.")}</div><div class="big">{fprice(med, cur)}</div></div>
      <div><div class="l">Schlusskurs</div><div class="mid">{fprice(p, cur)}</div></div>
      <div><div class="l">Median ggü. Kurs</div><div class="mid">{fpct(gap, 1, True)}</div></div>
      <div><div class="l">Mittlere Hälfte der Modelle{ii("Spanne vom 25. bis zum 75. Perzentil der Modellwerte. Im Balken: hellblau niedrigster bis höchster Modellwert, dunkelblau mittlere Hälfte, Strich Schlusskurs.")}</div><div class="mid">{fnum(q1, 0)} – {fnum(q3, 0)}</div></div></div>
      <div class="rbar"><div class="track"></div>
        <div class="span" style="left:{pos(min(vals))};width:calc({pos(max(vals))} - {pos(min(vals))})"></div>
        <div class="iqr" style="left:{pos(q1)};width:calc({pos(q3)} - {pos(q1)})"></div>
        <div class="mk" style="left:{pos(p)}">Kurs {fnum(p, 0)}<i></i></div>
        <div class="lab" style="left:{pos(min(vals))}">{fnum(min(vals), 0)} {cur}</div><div class="lab" style="left:{pos(med)}">Median {fnum(med, 0)}</div><div class="lab" style="left:{pos(max(vals))}">{fnum(max(vals), 0)} {cur}</div>
      </div></div>''', unsafe_allow_html=True)
    if c.get("implied_g") is not None:
        st.markdown(f'<div class="info" style="margin-top:12px"><b>Reverse-DCF:</b> Der Schlusskurs von {fprice(p, cur)} impliziert ein Wachstum des Free Cashflows von '
                    f'<b>{fpct(c["implied_g"], 1)} p. a.</b> über fünf Jahre (Kapitalkosten 9 %). Zum Vergleich: Konsens-Umsatzwachstum im laufenden Jahr '
                    f'{fpct((cons(sym).get("years") or [{}])[0].get("rev_growth"), 1)}.</div>', unsafe_allow_html=True)
    peh = pe_history(sym); cur_pe = pe(c)
    if cur_pe:
        kgv_block(c, sym, peh, cur_pe)
    if peh is not None:
        with agx.acc_ctx("kgvhist", "KGV-Verlauf 5 Jahre", "KGV je Handelstag, hellblau die mittlere Hälfte der Tage."):
            pv = prices_long(sym)[["date"]].copy(); pv["date"] = pd.to_datetime(pv.date)
            d_ = pv[pv.date >= pv.date.max() - pd.DateOffset(years=5)].date.iloc[-len(peh):].tolist()
            f = go.Figure()
            f.add_hrect(y0=float(peh.quantile(.25)), y1=float(peh.quantile(.75)), fillcolor="#eaf2fa", line_width=0, layer="below")
            f.add_trace(go.Scatter(x=d_, y=peh.tolist(), mode="lines", line=dict(color=BLUE, width=1.8), hovertemplate=agx.single("%{x|%d.%m.%Y}", "KGV", ",.1f", "×")))
            f.add_hline(y=float(peh.median()), line=dict(color=INK, width=1, dash="dash"))
            f.add_annotation(x=1, xref="paper", y=float(peh.median()), xanchor="right", yanchor="bottom", showarrow=False, text=f"Median {fmult(peh.median())}", font=dict(size=12, color=INK))
            cap = float(peh.quantile(.98)) * 1.1
            f.update_layout(**fig_base(320, yaxis=dict(gridcolor="#eef2f6", range=[0, cap], ticksuffix="×"), xaxis=dict(showgrid=False)))
            pchart(f, width="stretch", config=PLOT_CFG)
    h2("Fairer Wert je Modell", None,
       info=f"{len(ok)} Modelle mit Wert für diese Aktie, sortiert nach Höhe · gestrichelt: Schlusskurs. Discounted-Cashflow-Modelle zinsen künftige Free Cashflows ab; Multiple-Modelle übertragen Bewertungsrelationen (KGV, EV/EBITDA) von Vergleichsfirmen oder der eigenen Historie. Annahmen je Modell im aufklappbaren Detail unten.")
    f = go.Figure()
    names = [m["model"] for m in ok]
    f.add_trace(go.Bar(y=names, x=vals, orientation="h", marker_color=BLUE, width=.55,
                       text=[f"{fnum(v)}  ({fpct(v / p - 1, 1, True)})" for v in vals], textposition="outside", cliponaxis=False,
                       hovertemplate=agx.single("%{y}", "Fairer Wert", ",.2f", cur, "x"),
                       textfont=dict(size=13, color=INK)))
    f.add_vline(x=p, line=dict(color=INK, width=1.5, dash="dash"))
    f.add_annotation(x=p, y=1, yref="paper", yanchor="bottom", showarrow=False, text=f"<b>Kurs {fnum(p)}</b>", font=dict(size=12, color=INK))
    f.update_layout(**fig_base(90 + 46 * len(ok), xaxis=dict(range=[0, max(vals) * 1.28], gridcolor="#eef2f6", tickformat=",.0f"),
                               yaxis=dict(categoryorder="array", categoryarray=names, tickfont=dict(size=13.5, color=INK), automargin=True)))
    f.update_layout(margin=dict(l=4, r=4, t=30, b=4))
    pchart(f, width="stretch", config=PLOT_CFG)
    n_na = len([n for n, _ in na if n != "Reverse-DCF"])
    h2("Wichtigste Annahmen", None,
       info="Basis-Szenario und Modellrahmen; alle Modelle rechnen mit denselben Kapitalkosten. Die Werte stammen aus dem Basis-Szenario: Umsatzwachstum läuft von Jahr 1 linear auf Jahr 5 aus; Kapitalkosten (Diskontsatz) sind für alle Modelle fix 9 %.")
    an = c["annual"][-6:]; y0 = (cons(sym).get("years") or [{}])[0]; k = c["keystats"]
    h_g = (an[-1]["revenue"] / an[0]["revenue"]) ** (1 / (len(an) - 1)) - 1 if len(an) >= 2 and an[0].get("revenue") else None
    h_m = [r_["net_margin"] for r_ in an[-5:] if r_.get("net_margin") is not None]
    sh = an[-1].get("diluted_shares") if an else None
    c_m = y0["eps"] * sh / y0["rev"] if y0.get("eps") and y0.get("rev") and sh else None
    rows = [("Umsatzwachstum p. a.", f'{fpct(b["g_start"], 1)} → {fpct(b["g_end"], 1)}', "Jahr 1 bis 5", fpct(h_g, 1) if h_g is not None else None, f"Ø der letzten {len(an) - 1} Jahre",
             fpct(y0.get("rev_growth"), 1) if y0.get("rev_growth") is not None else None, f'Geschäftsjahr {y0.get("fy", "")}'),
            ("Nettomarge", fpct(b["margin"], 1), "Zielwert Jahr 5", fpct(sum(h_m) / len(h_m), 1) if h_m else None, f"Ø der letzten {len(h_m)} Jahre",
             fpct(c_m, 1) if c_m else None, f'Geschäftsjahr {y0.get("fy", "")}, Näherung'),
            ("Exit-KGV", fmult(b["exit_pe"]), "am Ende von Jahr 5", fmult(peh.median()) if peh is not None else (fmult(k.get("pe_hist_median")) if k.get("pe_hist_median") else None), "Median 5 Jahre",
             ka(k.get("pe_fwd"), fmult) if k.get("pe_fwd") else None, "Forward-KGV heute"),
            ("Kapitalkosten", "9,0 %", "fix für alle Modelle", None, "", None, "")]
    cell = lambda v, sub: f'<b>{v}</b><span class="muted" style="display:block;font-size:12px">{sub}</span>' if v else '<span class="muted">–</span>'
    st.markdown('<table class="tbl atbl"><thead><tr><th>Annahme</th><th class="r">Modell (Basis)</th><th class="r">Eigene Historie</th><th class="r">Analystenkonsens</th></tr></thead><tbody>'
                + "".join(f'<tr><td>{n}</td><td class="r">{cell(v, vs)}</td><td class="r">{cell(h, hs)}</td><td class="r">{cell(cn, cs_)}</td></tr>' for n, v, vs, h, hs, cn, cs_ in rows)
                + '</tbody></table>', unsafe_allow_html=True)
    with st.expander("Details je Modell: Wert und Annahmen"):
        st.markdown(table([{"Modell": f"<b>{m['model']}</b>", "Fairer Wert": fnum(m["value"]), "ggü. Kurs": fpct(m["value"] / p - 1, 1, True),
                            "Annahmen": plain(m["assumptions"])} for m in sorted(ok, key=lambda m: common.MODEL_ORDER.index(m["model"]))],
                          ["Modell", "Fairer Wert", "ggü. Kurs", "Annahmen"], align={"Fairer Wert": "r", "ggü. Kurs": "r"}), unsafe_allow_html=True)

# ---------------------------------------------------------------- Szenarien
def eps_path(c, sym, key):
    """Gewinn je Aktie je Modelljahr: Umsatzpfad × Margenpfad ÷ Aktienanzahl (Rückkaufquote), auf den Jahr-5-Wert des Szenarios abgestimmt."""
    an = c["annual"]; v = c["scenarios"][key]; P = scen_path(c, sym, key); sh0 = an[-1].get("diluted_shares"); y0 = int(an[-1]["fy_end"][:4])
    if not sh0: return [], []
    raw = [P[y][0] * 1e9 * P[y][1] / 100 / (sh0 * (1 - (v.get("sh_yield") or 0)) ** (y - y0)) for y in sorted(P)]
    fac = v["eps"] / raw[-1] if raw and raw[-1] else 1
    eps = [x * (1 + (fac - 1) * (i + 1) / len(raw)) for i, x in enumerate(raw)]
    return [y0] + sorted(P), [an[-1].get("eps_diluted")] + eps

def eps_paths(c, sym):
    """Gewinn je Aktie je Szenario als Pfad bis Jahr 5 mit beschrifteten Endwerten; Exit-KGV kompakt als Pill-Tabelle daneben."""
    s = c["scenarios"]; cur = c["currency"]; a = (c["analyst"] or {}).get("scenarios") or {}; p = c["price"]
    agx.sec("Gewinn je Aktie und Exit-KGV je Szenario",
            "Gewinn je Aktie je Jahr = Umsatz × Nettomarge ÷ Aktienanzahl (abnehmend mit der Rückkaufquote des Szenarios), auf den Jahr-5-Wert des Szenarios abgestimmt. "
            "Graue Punkte: Analystenkonsens für die nächsten Geschäftsjahre (häufig bereinigt). Exit-KGV = KGV, mit dem der Gewinn in Jahr 5 bewertet wird.")
    l, r = st.columns([1.7, 1], gap="medium", vertical_alignment="top")
    cols = {"konservativ": "#9cc0e2", "basis": agx.BLUE, "positiv": "#1f4e79"}
    with l:
        f = go.Figure(); ends = []
        for k in ("konservativ", "basis", "positiv"):
            X, Y = eps_path(c, sym, k)
            if not X: continue
            pos = {"positiv": "top left", "basis": "middle left", "konservativ": "bottom left"}[k]
            f.add_trace(go.Scatter(x=[str(x) for x in X], y=Y, mode="lines+markers+text", name=k.capitalize(), line=dict(color=cols[k], width=2.6 if k == "basis" else 2),
                                   marker=dict(size=6), text=[""] * (len(Y) - 1) + [f"<b>{k.capitalize()}</b> {fnum(Y[-1])}  "], textposition=pos,
                                   textfont=dict(size=12, color=cols[k]), hovertemplate=agx.tpl(k.capitalize(), ",.2f", cur)))
            ends.append((str(X[-1]), Y[-1], k))
        ys_ = [y for y in cons(sym).get("years", []) if y.get("eps") and str(y["fy"]) in {e_[0] for e_ in ends} | {str(x) for x in eps_path(c, sym, "basis")[0]}]
        if ys_:
            f.add_trace(go.Scatter(x=[str(y["fy"]) for y in ys_], y=[y["eps"] for y in ys_], mode="markers", name="Konsens", marker=dict(size=9, color="#98a2b3", symbol="diamond"),
                                   hovertemplate=agx.tpl("Konsens", ",.2f", cur)))
        allv = [v for tr in f.data for v in tr.y if v is not None]
        f.update_layout(**agx.layout(400, title=dict(text=f"Gewinn je Aktie je Geschäftsjahr ({cur})", x=.5, font=dict(size=13, color=INK)),
                                     xaxis=dict(type="category", showgrid=False, range=[-0.3, len(eps_path(c, sym, "basis")[0]) - 0.7]), yaxis=dict(gridcolor="#eef2f6", tickformat=",.0f", range=[0, max(allv) * 1.12])))
        f.update_layout(margin=dict(l=4, r=10, t=34, b=4))
        pchart(agx.unified(f, "Geschäftsjahr %{x}"), width="stretch", config=PLOT_CFG)
    with r:
        peh = pe_history(sym); cur_pe = pe(c)
        rows = [(k.capitalize(), fmult(s[k]["exit_pe"]) if s[k].get("exit_pe") else "–", pill(s[k]["exit_pe"] / cur_pe - 1) if cur_pe and s[k].get("exit_pe") else "", None) for k in ("konservativ", "basis", "positiv")]
        rows += [("KGV heute", fmult(cur_pe), "", "Schlusskurs ÷ Gewinn je Aktie der letzten 12 Monate."),
                 ("Median 5 Jahre", fmult(peh.median()) if peh is not None else "k. A.", "", "Median des täglichen KGV der letzten fünf Jahre.")]
        if a.get("basis"): rows.append(("Analysten", fmult(a["basis"]["exit_pe"]), "", "Exit-KGV im Analysten-Szenario (Konsens Durchschnitt)."))
        st.markdown('<div style="height:34px"></div>' + agx.pill_table("Exit-KGV in Jahr 5 " + agx.ii("Pill bei den Szenarien: Abstand des Exit-KGV zum KGV heute."), rows, tags=["Modell"] * 3 + [None] * (len(rows) - 3)), unsafe_allow_html=True)

def t_scen(c, sym):
    if c.get("scen_src") != "v4":
        import fairvalue as _fv0
        _r = (_fv0.all_()["stocks"].get(sym) or {})
        agx.sec("Eigene Szenarien über fünf Jahre", "Szenarien aus derselben Bewertung wie im Reiter Bewertung.")
        _why = ("Kapazitätsaufbau: Statt Kurs-Szenarien zeigt der Reiter Bewertung die vom Kurs eingepreiste Rendite auf neue Kapazität."
                if _r.get("display_mode") == "implied_return" else "Für diese Aktie liegen keine vollständigen Finanzdaten für eigene Szenarien vor.")
        st.markdown(f'<span class="pill neu">Szenarien nicht verfügbar</span>{ii(_why)}', unsafe_allow_html=True); return
    import fairvalue as _fv
    if _fv.unreliable(sym):
        st.markdown(f'<span class="pill neu">Bewertung nicht belastbar</span>{ii("; ".join(_fv.unreliable(sym)) + ". Die Szenarien unten dienen nur der Nachvollziehbarkeit.")}', unsafe_allow_html=True)
    s = c["scenarios"]; cur = c["currency"]; a = c["analyst"].get("scenarios") or {}; p = c["price"]
    agx.sec("Eigene Szenarien über fünf Jahre", "Aus der Bewertung (dieselben drei Szenarien wie im Reiter Bewertung): fairer Wert heute = Szenariowert; "
            "Kurs in 5 Jahren = fairer Wert × (1 + Eigenkapitalkosten)⁵; Rendite p. a. vom heutigen Kurs. Wachstum und Marge aus dem DCF-Pfad (Jahr 1 und 5), Marge nach Steuern auf das operative Ergebnis (NOPAT).")
    html = ""
    for n, col in (("konservativ", "#9cc0e2"), ("basis", agx.BLUE), ("positiv", "#1f4e79")):
        v = s[n]
        html += (f'<div class="kc" style="border-top:3px solid {col}"><div class="h3">{n.capitalize()}</div>'
                 f'<div style="font-size:26px;font-weight:700;color:#1d2939">{fpct(v["cagr"])} <span style="font-size:13px;font-weight:500;color:#5d6b7e">p. a.</span></div>'
                 f'<div class="row"><span>Kurs in 5 Jahren</span><b>{fprice(v["price"], cur)}</b></div>'
                 f'<div class="row"><span>Fairer Wert heute</span><b>{fprice(v["fv_today"], cur)} {pill(v["fv_today"] / p - 1)}</b></div>'
                 f'<div class="row"><span>Umsatzwachstum Jahr 1 → 5</span><b>{fpct(v["g_start"])} → {fpct(v["g_end"])}</b></div>'
                 f'<div class="row"><span>Marge nach Steuern (NOPAT) Jahr 5</span><b>{fpct(v["margin"])}</b></div></div>')
    st.markdown(f'<div class="kcards">{html}</div>', unsafe_allow_html=True)
    d, ys = forecast_block(c, sym, toggle=False)
    eps_paths(c, sym)
    if c.get("val_criteria"):
        def _b():
            st.markdown(table([{"Kennzahl": plain(q["name"]),
                                "Wert": (fpct(q["value"]) if q["fmt"] == "pct" else (f'Perzentil {fnum(q["value"], 1)}' if q["fmt"] == "pctl" else fnum(q["value"]))) if q["value"] is not None else "–",
                                "Referenzbereich": plain(q["range"]), "Hinweis": plain(q["note"])} for q in c["val_criteria"]],
                              ["Kennzahl", "Wert", "Referenzbereich", "Hinweis"], align={"Wert": "r"}), unsafe_allow_html=True)
        agx.acc("sc_val", "Bewertungskennzahlen im Detail", f'{len(c["val_criteria"])} Kennzahlen mit Referenzbereich.', body=_b)

# ---------------------------------------------------------------- Finanzdaten
def fybars(xs, vals, title, fmt, col=None, h=340, unit="", est=None, lag=1, name="Wert", d=2):
    col = col or agx.BLUE
    nact = len(xs)
    if est:
        xs = list(xs) + [f"{y}e" for y, _ in est]; vals = list(vals) + [v for _, v in est]
    gr = [None] * lag + [(vals[i] / vals[i - lag] - 1) if vals[i - lag] and vals[i - lag] > 0 and vals[i] is not None else None for i in range(lag, len(vals))]
    f = go.Figure(go.Bar(x=xs, y=vals, marker_color=[col] * nact + ["#a9c4e6"] * (len(xs) - nact), customdata=[fpct(g, 1, True) if g is not None else "–" for g in gr],
                         text=[fmt(v) if v is not None else "" for v in vals], textposition="outside", cliponaxis=False, textfont=dict(size=11.5, color=INK),
                         hovertemplate=f"<b>%{{x}}</b><br>{name}: %{{y:,.{d}f}} {unit}<br>Veränderung: %{{customdata}}<extra></extra>"))
    vv = [v for v in vals if v is not None] or [0]
    f.update_layout(**agx.layout(h, bargap=.35, xaxis=dict(type="category"), yaxis=dict(gridcolor="#eef2f6", range=[min(0, min(vv) * 1.3), max(vv) * 1.2], tickformat=",.0f")))
    f.update_layout(margin=dict(l=4, r=4, t=14, b=4))
    pchart(f, width="stretch", config=PLOT_CFG)

def quarters(sym):
    import json
    from lib import D as DATA
    if not hasattr(quarters, "_c"):
        p_ = DATA / "quarters.json"; quarters._c = json.loads(p_.read_text()) if p_.exists() else {}
    return quarters._c.get(sym, [])

def t_data(c, sym):
    cur = c["currency"]; an = c["annual"]
    if not an:
        st.markdown('<p class="muted">Jahresabschlüsse: k. A.</p>', unsafe_allow_html=True); return
    xs = [r["fy_end"][:4] for r in an]
    col = lambda k: [r.get(k) for r in an]
    qs = quarters(sym)[-12:]
    hl, hr = st.columns([3, 1], vertical_alignment="bottom")
    with hr:
        if qs: per = period_toggle(sym)
        else:
            per = "Jährlich"; st.markdown('<span class="pill neu">nur Jahreszahlen</span>', unsafe_allow_html=True)
    quarter = per == "Quartal" and bool(qs)
    with hl:
        agx.sec("Finanzdaten", f"Letzte {len(qs)} Quartale laut SEC-Quartalsberichten (10-Q; viertes Quartal aus dem 10-K abgeleitet). Wo ein Bericht nur aufgelaufene Werte enthält, ist das Quartal als Differenz berechnet. Beträge in {cur}."
                if quarter else f"Geschäftsjahre {xs[0]}–{xs[-1]} laut SEC-Jahresabschluss (10-K bzw. 20-F/40-F, XBRL)." + ("" if qs else " Keine aktuellen Quartalsberichte bei der SEC (Auslandsemittenten berichten jährlich oder halbjährlich), daher nur Jahreszahlen.") + f" Beträge in {cur}. Hellblaue Balken mit „e“: Konsens-Schätzung der Analysten.")
    if quarter:
        X = [q["label"] for q in qs]
        S = {k: [q[k2] for q in qs] for k, k2 in (("revenue", "revenue"), ("eps_diluted", "eps"), ("fcf", "fcf"), ("gross_margin", "gross_margin"),
                                                  ("op_margin", "op_margin"), ("net_margin", "net_margin"), ("fcf_margin", "fcf_margin"))}
        lag, cmp_txt, lab_end = 4, "ggü. Vorjahresquartal", X[-1]
    else:
        X = xs; S = {k: col(k) for k in ("revenue", "eps_diluted", "fcf", "gross_margin", "op_margin", "net_margin", "fcf_margin", "roic", "buybacks", "diluted_shares")}
        lag, cmp_txt, lab_end = 1, "ggü. Vorjahr", xs[-1]
    def card(lab, k, fmt):
        v = S.get(k) or []
        if not v or v[-1] is None: return kpi(f"{lab} {lab_end}", "k. A.", "")
        l, p_ = v[-1], (v[-1 - lag] if len(v) > lag else None)
        if fmt is fpct: delta = f'<span style="color:#5d6b7e;font-weight:600">{"↑" if l >= p_ else "↓"} {fnum(abs(l - p_) * 100, 1)} Pp.</span>' if p_ is not None else ""
        else: delta = arrow((l / p_ - 1) if p_ and p_ > 0 else None)
        return kpi(f"{lab} {lab_end}", fmt(l), f"{delta} {cmp_txt}", spark(v, 84, 28))
    big = lambda v: fbig(v, "")
    st.markdown('<div class="kpis c3">' + card("Umsatz", "revenue", big) + card("Gewinn je Aktie", "eps_diluted", fnum) + card("Free Cashflow", "fcf", big) + "</div>", unsafe_allow_html=True)
    yrs = [] if quarter else [y for y in cons(sym).get("years", []) if str(y["fy"]) > xs[-1]]
    nz = lambda v: [x / 1e9 if x is not None else None for x in v]
    per_txt = "Quartal" if quarter else "Geschäftsjahr"
    def gsent(vals, lab, unit, d=1):
        v = [x for x in vals if x is not None]
        if len(v) <= lag: return ""
        g = v[-1] / v[-1 - lag] - 1 if v[-1 - lag] and v[-1 - lag] > 0 else None
        cagr = (v[-1] / v[0]) ** (1 / ((len(v) - 1) / (4 if quarter else 1))) - 1 if v[0] and v[0] > 0 and v[-1] > 0 else None
        return (f'{lab} im {per_txt} {X[-1]}: {fnum(v[-1], d)} {unit}{(" " + pill(g) + " " + cmp_txt) if g is not None else ""}.'
                + (f' Durchschnittliches Wachstum über den gezeigten Zeitraum: {pill(cagr)} pro Jahr.' if cagr is not None else ""))
    def ptab(title, vals, unit, d=1):
        rows = []
        for i in range(len(X)):
            v = vals[i]; g = vals[i] / vals[i - lag] - 1 if i >= lag and vals[i - lag] and vals[i - lag] > 0 and v is not None else None
            rows.append((X[i], f"{fnum(v, d)} {unit}" if v is not None else "k. A.", pill(g) if g is not None else "", None))
        return agx.pill_table(title, rows[-8:])
    rv = nz(S["revenue"])
    agx.acc("fd_rev", "Umsatz & -wachstum", gsent(rv, "Umsatz", f"Mrd. {cur}"), "",
            expanded=True, body=lambda: fybars(X, rv, "", lambda v: fnum(v, 1), unit=f"Mrd. {cur}", est=[(y["fy"], y["rev"] / 1e9) for y in yrs if y.get("rev")], lag=lag, name="Umsatz", d=1))
    agx.acc("fd_eps", "Gewinn je Aktie & -wachstum", gsent(S["eps_diluted"], "Gewinn je Aktie (verwässert)", cur, 2), "",
            body=lambda: fybars(X, S["eps_diluted"], "", lambda v: fnum(v, 2), col="#1f4e79", unit=cur, est=[(y["fy"], y["eps"]) for y in yrs if y.get("eps")], lag=lag, name="Gewinn je Aktie", d=2))
    fv = nz(S["fcf"])
    def _fcf():
        f = go.Figure()
        f.add_trace(go.Bar(x=X, y=fv, name="Free Cashflow", marker_color=agx.BLUE, hovertemplate=agx.tpl("Free Cashflow", ",.2f", f"Mrd. {cur}")))
        if not quarter:
            f.add_trace(go.Bar(x=X, y=nz(col("fcf_after_sbc")), name="nach Aktienvergütung", marker_color="#a9c4e6", hovertemplate=agx.tpl("nach Aktienvergütung", ",.2f", f"Mrd. {cur}")))
        f.update_layout(**agx.layout(340, barmode="group", bargap=.35, showlegend=not quarter, legend=dict(orientation="h", y=1.1, x=0), xaxis=dict(type="category"), yaxis=dict(gridcolor="#eef2f6", tickformat=",.0f")))
        pchart(agx.unified(f), width="stretch", config=PLOT_CFG)
    agx.acc("fd_fcf", "Free Cashflow", gsent(fv, "Free Cashflow", f"Mrd. {cur}"), "", body=_fcf)
    def _m():
        f = go.Figure()
        for k, nm, cl in (("gross_margin", "Bruttomarge", "#9cc0e2"), ("op_margin", "Operative Marge", agx.BLUE), ("net_margin", "Nettomarge", "#1f4e79"),
                          ("fcf_margin", "FCF-Marge", "#e8892c"), ("roic", "ROIC", GREEN)):
            if k not in S: continue
            v = [x * 100 if x is not None else None for x in S[k]]
            f.add_trace(go.Scatter(x=X, y=v, name=nm, mode="lines+markers", line=dict(color=cl, width=2.2), marker=dict(size=6), hovertemplate=agx.tpl(nm, ",.1f", "%")))
        f.update_layout(**agx.layout(380, showlegend=True, legend=dict(orientation="h", y=-0.14, x=0), xaxis=dict(type="category"),
                                     yaxis=dict(gridcolor="#eef2f6", ticksuffix=" %", range=[min([0] + [x * 100 for k in S if k.endswith("margin") for x in S[k] if x is not None]) - 5, 100])))
        pchart(agx.unified(f), width="stretch", config=PLOT_CFG)
    lm = lambda k: (S[k][-1] * 100 if S.get(k) and S[k][-1] is not None else None)
    mrows = [(n, f"{fnum(lm(k), 1)} %" if lm(k) is not None else "k. A.", "", INFO.get(n)) for n, k in (("Bruttomarge", "gross_margin"), ("Operative Marge", "op_margin"), ("Nettomarge", "net_margin"), ("FCF-Marge", "fcf_margin"))]
    agx.acc("fd_m", "Margen" + ("" if quarter else " & Kapitalrendite"), f"Margen in Prozent des Umsatzes im {per_txt} {X[-1]}.", agx.pill_table("Margen " + X[-1], mrows), body=_m)
    if not quarter:
        k = c["keystats"]
        def _kap():
            f = go.Figure()
            for k_, nm, cl in (("buybacks", "Aktienrückkäufe", agx.BLUE), ("dividends_paid", "Dividenden", "#1f4e79"), ("sbc", "Aktienvergütung", "#c9d3df")):
                f.add_trace(go.Bar(x=xs, y=[abs(v or 0) / 1e9 for v in col(k_)], name=nm, marker_color=cl, hovertemplate=agx.tpl(nm, ",.1f", f"Mrd. {cur}")))
            f.update_layout(**agx.layout(320, barmode="group", bargap=.3, showlegend=True, legend=dict(orientation="h", y=1.1, x=0), xaxis=dict(type="category"), yaxis=dict(gridcolor="#eef2f6")))
            pchart(agx.unified(f), width="stretch", config=PLOT_CFG)
        fc = [v for v in col("fcf")[-5:] if v is not None]
        krows = [("Nettoverschuldung", fbig(k.get("net_debt"), cur) if k.get("net_debt") is not None else "k. A.", "", "Finanzschulden minus Barmittel; negativ = Nettoliquidität."),
                 ("Nettoverschuldung ÷ FCF", fmult(k.get("net_debt_to_fcf")) if k.get("net_debt_to_fcf") is not None else "k. A.", "", "Jahre Free Cashflow zur Tilgung der Nettoschulden."),
                 ("Aktienanzahl p. a. (3 J.)", fpct(k.get("shares_cagr3"), 1, True), "", "Veränderung der verwässerten Aktienanzahl pro Jahr über drei Jahre."),
                 ("Aktienvergütung ÷ Umsatz", fpct(k.get("sbc_to_revenue"), 1), "", None),
                 ("Jahre mit negativem FCF (5)", fnum(sum(v < 0 for v in fc), 0), "", None)]
        agx.acc("fd_kap", "Bilanz & Mittelverwendung", f"Aktienrückkäufe {xs[-1]}: {fbig(abs(an[-1].get('buybacks') or 0), cur)}; Dividenden: {fbig(abs(an[-1].get('dividends_paid') or 0), cur)}.",
                agx.pill_table("Bilanz und Kapital", krows), body=_kap)
        def _tab():
            spec = [("Umsatz", "revenue", "big"), ("Umsatzwachstum", "rev_growth", "chg"), ("Bruttomarge", "gross_margin", "pct"),
                    ("Operative Marge", "op_margin", "pct"), ("Nettomarge", "net_margin", "pct"), ("Gewinn je Aktie (verwässert)", "eps_diluted", "px"),
                    ("Free Cashflow", "fcf", "big"), ("FCF-Marge", "fcf_margin", "pct"), ("Aktienvergütung", "sbc", "big"),
                    ("FCF nach Aktienvergütung", "fcf_after_sbc", "big"), ("Aktienrückkäufe", "buybacks", "big"), ("Dividenden", "dividends_paid", "big"),
                    ("Aktien (verwässert, Mio.)", "diluted_shares", "mio"), ("ROIC", "roic", "pct"), ("ROIC ohne Goodwill", "roic_ex_gw", "pct")]
            fm = {"big": lambda v: fnum(v / 1e9, 2) if v is not None else "–", "pct": fpct, "chg": arrow, "px": fnum, "mio": lambda v: fnum(v / 1e6, 1) if v else "–"}
            rows = [{"Kennzahl": f"<b>{lab}</b>" + (f" <span class='muted'>Mrd. {cur}</span>" if kind == "big" else ""), **{r_["fy_end"][:4]: fm[kind](r_.get(key)) for r_ in an}} for lab, key, kind in spec]
            st.markdown(table(rows, ["Kennzahl"] + xs, align={x: "r" for x in xs}), unsafe_allow_html=True)
            st.markdown(table([{"Kennzahl": plain(q["name"]), "Wert": (fpct(q["value"]) if q["fmt"] == "pct" else fnum(q["value"])) if q["value"] is not None else "–",
                                "Referenzbereich": plain(q["range"])} for q in c["quality"]["criteria"]], ["Kennzahl", "Wert", "Referenzbereich"], align={"Wert": "r"}), unsafe_allow_html=True)
        def _tabraw():
            _tab(); st.markdown('<div class="h3" style="margin:22px 0 8px">Alle Werte der Analyse</div>', unsafe_allow_html=True); raw_values(c, sym)
        agx.acc("fd_tab", "Tabellen & Rohdaten", f"Jahresabschlüsse ({len(an)} Geschäftsjahre), Qualitätskennzahlen und alle Felder der Analyse als CSV.", body=_tabraw)


SECTION_DE = {"fundamentals": "Fundamentaldaten", "quality": "Qualität", "chart": "Chart", "valuation": "Bewertung", "analyst": "Analysten",
              "valuation_models": "Bewertungsmodelle", "deep": "Detailanalyse", "einstieg": "Einstieg", "tranches": "Limits",
              "consensus_norm": "Konsens (normiert)", "growth_margins": "Wachstum und Margen", "hist_multiples": "Historische Multiples",
              "peers": "Vergleichsfirmen", "price_path": "Kursverlauf", "mcap_tam": "Marktkapitalisierung und Markt",
              "renditequelle": "Renditequelle", "business_model": "Geschäftsmodell", "layer": "Einordnung"}

def raw_values(c, sym):
    df = fields(sym).copy()
    df["Bereich"] = df.feld.str.split(".").str[0].map(lambda x: SECTION_DE.get(x, x))
    df["Feld"] = df.feld.str.split(".", n=1).str[1].fillna("")
    def fmtv(v):
        try: x = float(v)
        except ValueError: return {"True": "ja", "False": "nein"}.get(v, v)
        return fnum(x, 0) if abs(x) >= 1e5 else fnum(x, 4 if abs(x) < 1 else 2)
    a, b, d = st.columns([1.2, 2, 1], vertical_alignment="bottom")
    bereich = a.selectbox("Bereich", ["Alle Bereiche"] + sorted(df.Bereich.unique()), key=f"db_{sym}")
    q = b.text_input("Feld suchen", key=f"dq_{sym}", placeholder="z. B. roic, fcf, pe")
    v = df if bereich == "Alle Bereiche" else df[df.Bereich == bereich]
    if q: v = v[v.Feld.str.contains(q, case=False, regex=False)]
    out = df[["Bereich", "Feld", "wert"]].rename(columns={"wert": "Wert"})
    d.download_button("CSV herunterladen", out.to_csv(index=False, sep=";").encode("utf-8-sig"), file_name=f"{sym}_analyse_{c['asof']}.csv",
                      mime="text/csv", key=f"dl_{sym}", width="stretch")
    st.markdown(table([{"Bereich": r.Bereich, "Feld": f"<code>{r.Feld}</code>", "Wert": fmtv(r.wert)} for r in v.itertuples()],
                      ["Bereich", "Feld", "Wert"], align={"Wert": "r"}, cls="scroll"), unsafe_allow_html=True)

def market_view(key):
    """Einfache Marktansicht für Kacheln wie SPY oder VIX: Verlauf der vorhandenen Schlusskurse, Stand und Veränderung."""
    agx.inject()
    mk = {m["key"]: m for m in load_v3()[0]}; m = mk[key]
    from lib import MKT_FMT
    fmt = MKT_FMT.get(key, lambda v: fnum(v, 2))
    st.markdown(f'<div class="shead"><div class="nm"><span class="mono">{key[:2]}</span>{m["name"]}{agx.ii(m["sub"])}</div>'
                f'<div class="pxrow"><span class="px">{fmt(m["last"])}</span>{pill(m["last"] / m["prev"] - 1, 2, big=True)}</div>'
                f'<div class="sub">Schluss {fdate(m["date"])} · Vortag {fmt(m["prev"])}</div></div>', unsafe_allow_html=True)
    from lib import D as _D; hp = str(_D / f"market_hist_{key}.parquet")
    if os.path.exists(hp):
        h = pd.read_parquet(hp); h["date"] = pd.to_datetime(h.date)
        TF = {"1M": 1, "3M": 3, "6M": 6, "1J": 12, "3J": 36, "5J": 60}
        tf = st.segmented_control("Zeitraum", list(TF), default="1J", key=f"mtf_{key}", label_visibility="collapsed") or "1J"
        v = h[h.date >= h.date.max() - pd.DateOffset(months=TF[tf])]
        ch = v.close.iloc[-1] / v.close.iloc[0] - 1; unit = {"TNX": "%", "GOLD": "USD", "BRENT": "USD", "SPY": "USD", "QQQ": "USD"}.get(key, "")
        dec = 4 if key == "EURUSD" else 2
        f = go.Figure(go.Scatter(x=v.date, y=v.close, mode="lines", line=dict(color=agx.BLUE, width=2), fill="tozeroy", fillcolor="rgba(61,111,182,.08)",
                                 customdata=[[f"{d.day:02d}.{d.month:02d}.{d.year}", fnum(x / v.close.iloc[0] * 100 - 100, 2)] for d, x in zip(v.date, v.close)],
                                 hovertemplate=f"<b>%{{customdata[0]}}</b><br>{m['name']}: %{{y:,.{dec}f}}{(' ' + unit) if unit else ''}<br>seit Beginn: %{{customdata[1]}} %<extra></extra>"))
        lo, hi = v.close.min(), v.close.max(); pad = (hi - lo) * .12 or 1
        agx.sec(f"Verlauf {tf} · {fpct(ch, 2, True)}", f"Tagesschlusskurse vom {fdate(v.date.iloc[0])} bis {fdate(v.date.iloc[-1])}, Quelle wie die Marktleiste (yfinance über den Datenbestand des Projekts).")
        f.update_layout(**agx.layout(420, hovermode="x", yaxis=dict(gridcolor="#eef2f6", range=[lo - pad, hi + pad], tickformat=f",.{min(dec, 2)}f", side="right"),
                                     xaxis=dict(showgrid=False, tickformat="%d.%m." if TF[tf] <= 6 else "%m/%Y", hoverformat=" ")))
        pchart(pad_right(f, .04), width="stretch", config=PLOT_CFG, key=f"mchart_{key}_{tf}")
    footer2(META)

def page():
    mq = st.query_params.get("m")
    if mq and mq in {m["key"] for m in load_v3()[0]}:
        market_view(mq); return
    sym = common.current()
    if sym in CASES: detail(sym)
    else: overview()
