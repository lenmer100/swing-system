"""Bereich Investment: langfristiges Investieren. Tranchenplan, Positionsgröße im Depot, Stressszenario, Unterbewertungs-Marken, langfristige Unterstützungen.
Nur Daten aus den Snapshot-Dateien (cases.json, quarters.json, Kurs-Parquets); was fehlt, wird weggelassen."""
import json, os
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from lib import pad_right, pchart, ii, prices_long, prices, fnum, fprice, fpct, fdate, table, plot_layout, load_v3, FONT, footer2
import ag_style as agx
import common
import fairvalue
import inv_views
from common import META, CASES
from swing import CSS, pstrip, de_txt, trend_label, sgn, de_in

from lib import D as _D; D = str(_D)
QUARTERS = json.load(open(os.path.join(D, "quarters.json")))
TABS = ["Überblick", "Tranchenplan", "Positionsgröße", "Stressszenario", "Unterstützungen"]
MON = ["Jan", "Feb", "März", "Apr", "Mai", "Juni", "Juli", "Aug", "Sep", "Okt", "Nov", "Dez"]
LAB = {"p": "erfüllt", "w": "mit Vorbehalt", "f": "nicht erfüllt", "o": "offen"}

# ---------------------------------------------------------------- Rechenkern
@st.cache_data
def calc(sym):
    c = CASES[sym]; price = c["price"]; px = prices_long(sym); sc = c["scenarios"]
    v2 = fairvalue.get(sym); vr = fairvalue.raw(sym)
    fv = dict(q1=v2["pess"], med=v2["base"], q3=v2["opt"], lo=v2["pess"], mos=v2["mos"]) if v2 else None
    cons = v2["pess"] if v2 else None
    w = px.set_index("date").close.resample("W-FRI").last(); m = px.set_index("date").resample("ME").agg({"low": "min", "close": "last"})
    w40, w200 = float(w.rolling(40).mean().iloc[-1]), (float(w.rolling(200).mean().iloc[-1]) if len(w) >= 200 else None)
    lows = m.low.tail(72).values; mi = m.tail(72).index
    piv = [(float(lows[i]), mi[i]) for i in range(2, len(lows) - 2) if lows[i] == min(lows[i - 2:i + 3]) and lows[i] < price]
    piv = sorted({round(v, 2): d for v, d in piv}.items(), key=lambda x: -x[0])[:4]
    sup = [dict(name="40-Wochen-Linie", v=w40, src="Ø Wochenschluss 40 Wochen")] if w40 < price else []
    if w200 and w200 < price: sup.append(dict(name="200-Wochen-Linie", v=w200, src="Ø Wochenschluss 200 Wochen"))
    sup += [dict(name=f"Monatstief {MON[d.month - 1]} {d.year}", v=v, src="Tiefpunkt im Monatschart") for v, d in piv]
    sup.sort(key=lambda x: -x["v"])
    ks = c.get("keystats") or {}; eps_ttm = ks.get("eps_ttm")
    kpe = next((((vr["scenarios"][k].get("forward_pe") or {}).get("justified") or {}).get("gordon_mature_pe") for k in ("pessimistic", "base") if vr and ((vr["scenarios"][k].get("forward_pe") or {}).get("justified") or {}).get("gordon_mature_pe")), None)
    if kpe is None and vr and vr.get("terminal_growth") is not None:   # ohne KGV-Block (Reinvestierer): reifes KGV bei ROE = Eigenkapitalkosten = (1+g)/ke
        _ke = vr["cost_of_capital"].get("cost_of_equity_mature") or vr["cost_of_capital"].get("cost_of_equity")
        kpe = (1 + vr["terminal_growth"]) / _ke if _ke and _ke > vr["terminal_growth"] else None
    pe_med = ks.get("pe_hist_median")
    run = px.close.cummax(); dd = px.close / run - 1; i = int(dd.idxmin()); peak_i = int(px.close[:i + 1].idxmax())
    mdd = dict(v=float(dd.min()), peak=px.date[peak_i], trough=px.date[i])
    wc = []
    if eps_ttm and eps_ttm > 0 and kpe: wc.append(("Heutiger Gewinn × reifes KGV", eps_ttm * kpe, f"Gewinn je Aktie der letzten 12 Monate {fnum(eps_ttm)} ohne Wachstum × KGV eines reifen Unternehmens ohne Wachstumsphase {fnum(kpe, 1)}"))
    if cons: wc.append(("Pessimistisches Szenario", cons, "fairer Wert im pessimistischen Szenario der Bewertung (niedrigste Umsatzschätzung, schwächere Marge, hohe Investitionen)"))
    wc.append(("Größter historischer Rückgang", price * (1 + mdd["v"]), f"heutiger Kurs mit dem größten Rückgang seit {px.date.iloc[0].year} ({fpct(mdd['v'], 1)}, {fdate(mdd['peak'])} bis {fdate(mdd['trough'])})"))
    pl = fairvalue.plan(sym)
    if pl:   # v5: Tranchen, Stopp und Stress kommen aus der Engine (valuation/invest_plan.py), nicht aus der UI
        tr = [dict(n=t["n"], v=t["v"], w=t["w"], why=t["why"]) for t in pl["tranches"]]
        wc = [(x["name"], x["v"], x["why"]) for x in pl["stress"] if x.get("v") and x["v"] > 0]
        worst = pl.get("stress_main") or (min(x[1] for x in wc) if wc else None)
        return dict(fv=fv, cons=cons, sup=sup, w40=w40, w200=w200, kpe=kpe, pe_med=pe_med, eps_ttm=eps_ttm, mdd=mdd, wc=wc, worst=worst, tr=tr, stop=pl.get("stop"), stop_why=pl.get("stop_why"), rules=pl.get("rules"))
    if not fv:   # ohne belastbare Bewertung: nur der historische Extremfall (kein Wert aus der Bewertung)
        wc = [x for x in wc if x[0] == "Größter historischer Rückgang"]
        return dict(fv=None, cons=None, sup=sup, w40=w40, w200=w200, kpe=kpe, pe_med=pe_med, eps_ttm=eps_ttm, mdd=mdd, wc=wc, worst=None, tr=[], stop=None, rules=None)
    worst = cons if cons else min(x[1] for x in wc)   # Hauptwert des Stressszenarios: pessimistisches Szenario der Bewertung
    # Tranchen: 1 = im Bewertungsrahmen, 2 = nächste langfristige Unterstützung ≥ 8 % tiefer, 3 = Kaufzone v3 (fairer Wert minus Sicherheitsmarge 20-50 %)
    tr = []
    if fv:
        t1 = min(price, fv["med"]); tr.append(dict(n=1, v=t1, why="aktueller Kurs (unter dem fairen Wert)" if price <= fv["med"] else "fairer Wert (Kurs liegt darüber)"))
        s2 = next((x for x in sup if x["v"] <= t1 * .92), None)
        if s2: tr.append(dict(n=2, v=s2["v"], why=f"langfristige Unterstützung: {s2['name']}"))
        under = fv["mos"]
        last = tr[-1]["v"]
        if under < last * .95: tr.append(dict(n=3, v=under, why=f"Kaufzone: {fpct(1 - under / fv['med'], 0)} unter dem fairen Wert (Sicherheitsmarge nach Unsicherheit)"))
        else:
            s3 = next((x for x in sup if x["v"] <= last * .92), None)
            if s3: tr.append(dict(n=3, v=s3["v"], why=f"langfristige Unterstützung: {s3['name']}"))
    wts = {1: [1.0], 2: [.5, .5], 3: [.4, .3, .3]}.get(len(tr), [])
    for i_, (t, w_) in enumerate(zip(tr, wts), 1): t["w"] = w_; t["n"] = i_
    return dict(fv=fv, cons=cons, sup=sup, w40=w40, w200=w200, kpe=kpe, pe_med=pe_med, eps_ttm=eps_ttm, mdd=mdd, wc=wc, worst=worst, tr=tr, stop=None, rules=None)

# ---------------------------------------------------------------- Bausteine
def steps(items):
    st.markdown('<div class="csteps">' + "".join(f'<div class="cs {t}"><span class="n">Schritt {i + 1}</span><span class="h">{a}</span><span class="v">{b}</span><span class="s">{d}</span><span class="b">{LAB[t]}</span></div>'
                for i, (a, b, d, t) in enumerate(items)) + "</div>", unsafe_allow_html=True)

def h2(t, info=None): st.markdown(f'<div class="h2" style="margin-top:6px">{t}{" " + ii(info) if info else ""}</div>', unsafe_allow_html=True)

def long_chart(sym, R, lines, height=440, years=10):
    c = CASES[sym]; px = prices_long(sym); w = px.set_index("date").close.resample("W-FRI").last().dropna(); w = w[w.index >= w.index.max() - pd.Timedelta(days=365 * years)]
    fig = go.Figure()
    fig.add_scatter(x=w.index, y=w.values, mode="lines", line=dict(color="#1d2939", width=1.6), name="Wochenschluss",
                    customdata=[f"{d.day:02d}.{d.month:02d}.{d.year}" for d in w.index], hovertemplate="<b>%{customdata}</b><br>Wochenschluss %{y:,.2f} " + c["currency"] + "<extra></extra>")
    for y, t, col, dash in lines:
        fig.add_hline(y=y, line=dict(color=col, width=1.3, dash=dash))
        fig.add_annotation(x=0.01, xref="paper", y=y, text=f"{t} {fnum(y, 0)}", showarrow=False, xanchor="left", yanchor="bottom", font=dict(size=12, color=col), bgcolor="rgba(255,255,255,.8)")
    tv = pd.date_range(f"{w.index.min().year + 1}-01-01", w.index.max(), freq="YS")
    fig.update_layout(height=height, separators=",.", margin=dict(l=10, r=10, t=10, b=10), showlegend=False, plot_bgcolor="#fff", paper_bgcolor="#fff", hovermode="x unified", font=dict(family=FONT),
                      yaxis=dict(gridcolor="#f2f4f7", side="right", tickformat=",.0f", rangemode="tozero"), xaxis=dict(showgrid=False, tickvals=list(tv), ticktext=[str(d.year) for d in tv], hoverformat=" "))
    pchart(pad_right(fig), use_container_width=True, key=f"lc_{sym}_{height}_{len(lines)}")

# ---------------------------------------------------------------- Reiter
def t_overview(c, sym, R):
    price = c["price"]; fv = R["fv"]; qok = c["quality"]["ok"]; tl, tok = trend_label(c); b = (c["scenarios"] or {}).get("basis", {}); bad = fairvalue.unreliable(sym)
    if fv:
        vt = "unter der fairen Spanne" if price < fv["q1"] else "über der fairen Spanne" if price > fv["q3"] else "innerhalb der fairen Spanne"
    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
    tr = R["tr"]
    steps([("Qualität", "bestanden" if qok else "nicht bestanden", f"Perzentil {fnum(c['q_pct'], 0)} im Pool", "p" if qok else "f"),
           ("Bewertung", f"Kurs {vt}" if fv else ("nicht belastbar" if bad else "k. A."), f"faire Spanne {fnum(fv['q1'], 0)} – {fnum(fv['q3'], 0)}" if fv else ("; ".join(bad)[:90] if bad else ""),
            ("p" if price <= fv["med"] else "w") if fv else ("f" if bad else "o")),
           ("Langfristtrend", "über der 40-Wochen-Linie" if price > R["w40"] else "unter der 40-Wochen-Linie", f"40-Wochen-Linie {fnum(R['w40'], 0)}", "p" if price > R["w40"] else "w"),
           ("Kaufniveaus", f"{len(tr)} Tranchen geplant" if tr else "k. A.", " · ".join(fnum(t["v"], 0) for t in tr), "p" if tr else "o")])
    cards = [("Fairer Wert", f'{fnum(fv["med"])} <span style="font-size:15px">{c["currency"]}</span>' if fv else "k. A.", f"{sgn(fv['med'] / price - 1)} zum Kurs" if fv else "", None),
             ("Potenzial zum fairen Wert", sgn(fv["med"] / price - 1) if fv else "k. A.", "Basisszenario der Bewertung", None),
             (("Stressszenario", fnum(R["worst"], 0), f"{sgn(R['worst'] / price - 1)} zum Kurs", "neg") if fv else
              ("Stressszenario", "k. A.", "ohne belastbare Bewertung kein Stresswert", None)),
             ("Qualität im Pool", f"Perzentil {fnum(c['q_pct'], 0)}", "von 100", None)]
    pstrip(cards)
    t = (load_v3()[1].get(sym) or {}).get("targets") or {}
    with st.expander("Kursziele der Analysten und fairer Wert"):
        rows = ([{"Quelle": "Analysten: Median", "Wert": fnum(t["median"]), "Zum Kurs": sgn(t["median"] / price - 1)}, {"Quelle": "Analysten: Spanne", "Wert": f'{fnum(t["low"])} – {fnum(t["high"])}', "Zum Kurs": ""}] if t.get("median") else [])
        if fv: rows += [{"Quelle": f"Bewertung: {n}", "Wert": fnum(v), "Zum Kurs": sgn(v / price - 1)} for n, v in (("optimistisch", fv["q3"]), ("fairer Wert", fv["med"]), ("pessimistisch", fv["q1"]))]
        st.markdown(table(rows, ["Quelle", "Wert", "Zum Kurs"], align={"Wert": "r", "Zum Kurs": "r"}), unsafe_allow_html=True)
    with st.expander("Einschätzung des Systems mit Begründung"):
        q = c["quality"]
        st.markdown(f'<div class="sw-panel"><div class="chk"><b>Qualität:</b>&nbsp;{de_txt(q["why"])}</div><div class="chk"><b>Begründung:</b>&nbsp;{de_txt(c["reason"])}</div></div>', unsafe_allow_html=True)

def t_tranches(c, sym, R): return inv_views.tranches(c, sym, R)

def t_size(c, sym, R):
    price = c["price"]; tr = R["tr"]; cur = c["currency"]
    with st.container(key="inv_inputs"):
        c1, c2, c3 = st.columns([1, 1, 2], gap="medium", vertical_alignment="bottom")
        dep = de_in(c1, f"Depotgröße ({cur})", 100000, f"dep_{sym}", 0, 1000, 1e9)
        wt = de_in(c2, "Zielgewicht (%)", 5.0, f"wt_{sym}", 1, 0.5, 50)
    tot = dep * wt / 100
    st.markdown(f'<p class="muted" style="margin:6px 0 10px">Zielposition <b>{fprice(tot, cur, 0)}</b> · {fnum(wt, 1)} % von {fprice(dep, cur, 0)} · {len(tr)} Tranchen</p>', unsafe_allow_html=True)
    if tr:
        rows = [{"Tranche": f"Tranche {t['n']}", "Kurs": fnum(t["v"]), "Anteil": fpct(t["w"], 0), "Betrag": fprice(tot * t["w"], cur, 0), "Stück": fnum(int(tot * t["w"] // t["v"]), 0)} for t in tr]
        st.markdown(table(rows, list(rows[0]), align={k: "r" for k in ("Kurs", "Anteil", "Betrag", "Stück")}), unsafe_allow_html=True)
        n = sum(int(tot * t["w"] // t["v"]) for t in tr); inv = sum(int(tot * t["w"] // t["v"]) * t["v"] for t in tr)
        loss = n * R["worst"] - inv
        pstrip([("Stück bei allen Tranchen", fnum(n, 0), f"investiert {fprice(inv, cur, 0)}", None),
                ("Verlust im Stressszenario", fprice(loss, cur, 0), f"{fpct(loss / dep, 2)} des Depots", "neg"),
                ("Nur Tranche 1", fprice(int(tot * tr[0]["w"] // tr[0]["v"]) * tr[0]["v"], cur, 0), f"{fpct(tr[0]['w'] * wt / 100, 1)} des Depots", None)])

def t_worst(c, sym, R): return inv_views.stress(c, sym, R)

def t_support(c, sym, R): return inv_views.support(c, sym, R)

# ---------------------------------------------------------------- Seiten
def _nolab(s_):
    m = fairvalue.mode(s_)
    return '<span class="muted">Aufbau: implizite Rendite</span>' if m == "implied_return" else '<span class="muted">nicht belastbar</span>' if m == "nicht_belastbar" else "k. A."

def overview():
    st.markdown('<div class="eyebrow">Investment</div><h1 class="ptitle">Langfristig investieren</h1>', unsafe_allow_html=True)
    th = "".join(f'<th class="{"r" if i > 1 else ""}">{n}{" " + ii(t) if t else ""}</th>' for i, (n, t) in enumerate([
        ("Aktie", None), ("Qualität", "Ergebnis der Qualitätsprüfung und Perzentil im Pool."), ("Kurs", None),
        ("Faire Spanne", "Pessimistisches bis optimistisches Szenario der Bewertung."), ("Zum fairen Wert", "Abstand des Kurses zum fairen Wert (Basisszenario)."),
        ("Stressszenario", "Fairer Wert im pessimistischen Szenario der Bewertung. Weitere Rechnungen im Reiter Stressszenario.")]))
    body = ""
    def _rk(s_):   # Rang: Qualität bestanden zuerst, dann größter Abstand unter dem fairen Wert
        v_ = fairvalue.get(s_); p_ = CASES[s_]["price"]
        return (not CASES[s_]["quality"]["ok"], (v_["base"] / p_ - 1) * -1 if v_ and v_.get("base") and p_ else 9)
    _pool = sorted(CASES, key=_rk)
    if len(CASES) > len(common.FEATURED):
        common.quick_picks("invest")
        _pool, _tot = common.pool_filter(_pool, "ib", extra=("Qualität", ["bestanden", "nicht bestanden"], lambda s_, x: CASES[s_]["quality"]["ok"] == (x == "bestanden")))
    else: _tot = len(_pool)
    for s in _pool:
        c = CASES[s]
        try: R = calc(s)
        except Exception: continue
        fv = R["fv"]; a = lambda x, cls="": f'<td class="{cls}"><a class="rl" href="/investment?t={s}" target="_self">{x}</a></td>'
        body += ("<tr>" + a(f'<b>{c["name"]}</b> <span class="muted">{s}</span>') + a(f'<span class="spill {"pos" if c["quality"]["ok"] else "neg"}">{"bestanden" if c["quality"]["ok"] else "nicht bestanden"}</span> <span class="muted">P{fnum(c["q_pct"], 0)}</span>', "r")
                 + a(fnum(c["price"]), "r") + a(f'{fnum(fv["q1"], 0)} – {fnum(fv["q3"], 0)}' if fv else _nolab(s), "r")
                 + a(f'<b class="tone-{"pos" if fv["med"] > c["price"] else "neg"}">{sgn(fv["med"] / c["price"] - 1)}</b>' if fv else "k. A.", "r")
                 + a(f'{fnum(R["worst"], 0)} <span class="muted">{sgn(R["worst"] / c["price"] - 1)}</span>' if R["worst"] else "k. A.", "r") + "</tr>")
    st.markdown(f'<table class="tbl btb"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>', unsafe_allow_html=True)
    if _tot > len(common.FEATURED): st.markdown(f'<div class="bfoot">{len(_pool)} von {fnum(_tot, 0)} Treffern · sortiert: Qualität bestanden zuerst, dann Abstand zum fairen Wert</div>', unsafe_allow_html=True)
    common.more("ib", _tot)
    footer2(META)

def detail(sym):
    c = CASES[sym]; R = calc(sym)
    st.markdown(f'<div class="crumb"><a href="/investment" target="_self">Investment</a><span>›</span><b>{c["name"]}</b></div>', unsafe_allow_html=True)
    agx.inject()
    l, r = st.columns([5, 1.1], vertical_alignment="top")
    with l: agx.head(c, prices(sym))
    with r:
        st.markdown('<div style="height:22px"></div>', unsafe_allow_html=True)
        if st.button("Swing-Tool", key="inv_to_swing", width="stretch", type="primary"): common.go("swing", sym)
    key = f"itab_{sym}"; q = st.query_params.get("tab")
    if q == "Worst Case": q = "Stressszenario"
    if q in TABS: st.session_state[key] = q
    elif key not in st.session_state: st.session_state[key] = TABS[0]
    def _tab():
        v = st.session_state.get(key) or TABS[0]; st.session_state[key] = v; st.query_params["tab"] = v
    with st.container(key="tabs"):
        tab = st.segmented_control("Bereich", TABS, key=key, on_change=_tab, label_visibility="collapsed") or TABS[0]
    dict(zip(TABS, [t_overview, t_tranches, t_size, t_worst, t_support]))[tab](c, sym, R)
    footer2(META)

def page():
    st.markdown(CSS + """<style>.tsteps{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:10px 0 16px}
.ts{border:1px solid var(--line);border-radius:10px;padding:16px 18px;display:flex;flex-direction:column;gap:4px;background:#fff}
.ts .no{width:26px;height:26px;border-radius:50%;background:#337ab7;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px}
.wcards{display:grid;grid-template-columns:1.2fr 1fr 1fr;gap:12px;margin:10px 0 18px}
.wcard{border:1px solid var(--line);border-radius:10px;padding:16px 18px;display:flex;flex-direction:column;gap:4px;background:#fff}
.wcard.main{border:2px solid #c0322b;background:#fffafa} .wcard .l{font-size:13px;color:var(--muted);font-weight:600} .wcard .v{font-size:24px;font-weight:700} .wcard.main .v{font-size:32px;color:#c0322b}
.wcard .v small{font-size:13px;color:var(--muted)} .wcard .d{font-size:13.5px;color:#c0322b;font-weight:600} .wcard .s{font-size:12.5px;color:var(--muted);line-height:1.5;margin-top:4px}
.ts .v{font-size:24px;font-weight:700} .ts .v small{font-size:13px;color:var(--muted)} .ts .s{font-size:12.5px;color:var(--muted)} .ts .w{font-size:13.5px;color:#344054;border-top:1px solid #f2f4f7;padding-top:8px;margin-top:4px}</style>""", unsafe_allow_html=True)
    sym = common.current()
    if sym in CASES: detail(sym)
    else: overview()
