"""Reiter Bewertung (Engine v3): ein fairer Wert mit Spanne und Kaufzone, Modell nach Geschäftstyp, Reverse-DCF,
Forward-KGV, Sensitivitäten, transparenter DCF-Rechner in Akkordeons."""
import json
from pathlib import Path
import plotly.graph_objects as go
import streamlit as st
from lib import fnum, fprice, fpct, fmult, fbig, fdate, h2, ii, pill, table, pchart, PLOT_CFG, plot_layout, FONT
import ag_style as agx
import fairvalue

BLUE, BLUE_L, INK, GREEN, RED = "#337ab7", "#9cc0e2", "#1d2939", "#2e9e5b", "#d64541"
LOCK = dict(fixedrange=True)


def hero(r, cur):
    p, rg = r["price"], r["range"]
    lo_v, base, hi_v = rg["pessimistic"], rg["base"], rg["optimistic"]
    lo, hi = min(lo_v, p), max(hi_v, p); pad = (hi - lo) * .05; lo, hi = max(0, lo - pad), hi + pad
    pos = lambda v: f"{(v - lo) / (hi - lo) * 100:.2f}%"
    w = r["weights"]["dcf"]; m = (r.get("classification") or {}).get("model")
    if m == "fcff":
        info_fv = (f"Fairer Wert = {fpct(w, 0)} Discounted-Cashflow (DCF)" + (f" + {fpct(1 - w, 0)} begründetes Forward-KGV" if w < 1 else ", ohne KGV-Anteil")
                   + " im Basisszenario. Gewichtung nach Wachstumsphase; alle Regeln fest und unten offengelegt.")
    else:
        info_fv = fairvalue.MODEL_DE.get(m, "") + ": Wert aus Eigenkapital und dauerhafter Überrendite bzw. FFO, Basisszenario."
    info_rg = ("Pessimistisch: niedrigste Umsatzschätzung der Analysten (ohne Schätzungen: Wachstum −5 Pp.), schwächere Marge aus eigener Historie und Sektor. "
               "Optimistisch: höchste Schätzung, bessere Marge und Kapitaleffizienz. Bei Zyklikern bleibt die Zyklusmarge in allen Szenarien gedeckelt.")
    buy = r.get("buy_zone_below"); mos = (r.get("classification") or {}).get("margin_of_safety")
    info_bz = (f"Kaufzone = fairer Wert minus Sicherheitsmarge {fpct(mos if mos is not None else .5, 0)}. Die Marge steigt mit der Streuung der Analystenschätzungen "
               "(20 % bei geringer, 50 % bei sehr hoher Unsicherheit oder ohne Schätzungen).")
    st.markdown(f'''<div class="vhero"><div class="top">
      <div><div class="l">Fairer Wert{ii(info_fv)}</div><div class="big">{fprice(base, cur)}</div></div>
      <div><div class="l">Schlusskurs {fdate(r["asof"])}</div><div class="mid">{fprice(p, cur)}</div></div>
      <div><div class="l">Fairer Wert ggü. Kurs</div><div class="mid">{fpct(base / p - 1, 1, True)}</div></div>
      <div><div class="l">Kaufen unter{ii(info_bz)}</div><div class="mid">{fnum(buy, 0) if buy else "k. A."}</div></div>
      <div><div class="l">Spanne pessimistisch – optimistisch{ii(info_rg)}</div><div class="mid">{fnum(lo_v, 0)} – {fnum(hi_v, 0)}</div></div></div>
      <div class="rbar"><div class="track"></div>
        <div class="span" style="left:{pos(lo_v)};width:calc({pos(hi_v)} - {pos(lo_v)})"></div>
        <div class="iqr" style="left:calc({pos(base)} - 3px);width:6px"></div>
        <div class="mk" style="left:{pos(p)}">Kurs {fnum(p, 0)}<i></i></div>
        {f'<div class="lab" style="left:{pos(lo_v)}">Pessimistisch {fnum(lo_v, 0)}</div>' if abs(lo_v / base - 1) > .06 else ''}<div class="lab" style="left:{pos(base)}">{"Basis = pessimistisch" if abs(lo_v / base - 1) <= .06 else "Basis"} {fnum(base, 0)}</div><div class="lab" style="left:{pos(hi_v)}">Optimistisch {fnum(hi_v, 0)}</div>
      </div></div>''', unsafe_allow_html=True)


def summary_box(r, cur):
    """Kennzahlen kompakt: nur Labels und Zahlen, Erklärung im (i)."""
    rv, f = r.get("reverse_dcf") or {}, r["scenarios"]["base"].get("forward_pe") or {}
    h = f.get("vs_history") or _pe_hist(r["ticker"])
    items = []
    if rv.get("implied_rev_cagr_5y") is not None:
        items.append(("target", f'<b>Reverse-DCF</b> · eingepreistes Wachstum p. a. <b>{fpct(rv["implied_rev_cagr_5y"], 1)}</b> · Basisszenario {fpct(rv["base_rev_cagr_5y"], 1)} · '
                      f'Differenz {fpct(rv["implied_rev_cagr_5y"] - rv["base_rev_cagr_5y"], 1, True).replace(" %", " Pp.")}'
                      + (f' · Zielmarge eingepreist {fpct(rv["implied_margin_target"], 1)} statt {fpct(rv["base_margin_target"], 1)}' if rv.get("implied_margin_target") is not None else "")
                      + ii("Gesucht ist das Umsatzwachstum über fünf Jahre (bzw. die operative Zielmarge), bei dem der DCF genau den Schlusskurs ergibt. Basisszenario aus dem Konsens; alle anderen Annahmen wie im Basisszenario.")))
    if f.get("forward_pe"):
        txt = (f'<b>Forward-KGV</b> {fmult(f["forward_pe"])} · begründet <b>{fmult(f["justified"]["justified_pe"])}</b> · fairer Preis {fprice(f["fair_price"], cur, 0)}')
        if h.get("median"):
            txt += f' · KGV {fmult(h["current_trailing"])} ggü. 5-Jahres-Median {fmult(h["median"])} {pill(h["current_vs_median"], 1)}'
        txt += ii(f'Forward-KGV = Kurs ÷ Konsens-Gewinn je Aktie der nächsten 12 Monate ({fnum(f["ntm"]["ntm_eps"])} {cur}, zeitgewichtet aus laufendem und nächstem Geschäftsjahr). '
                  "Begründetes KGV aus Wachstum, Eigenkapitalrendite und Eigenkapitalkosten (Ausschüttung = 1 − Wachstum ÷ Eigenkapitalrendite).")
        items.append(("info", txt))
    if items:
        agx.box(items)


def heat(vals, xs, ys, xt, yt, price, cur, key, hx, hy):
    z = [[v / price - 1 if v is not None else None for v in row] for row in vals]
    txt = [[fnum(v, 0) if v is not None else "–" for v in row] for row in vals]
    cd = [[[hy(y), hx(x), fprice(v, cur, 0), fpct(v / price - 1, 1, True)] for x, v in zip(xs, row)] for y, row in zip(ys, vals)]
    f = go.Figure(go.Heatmap(z=z, x=[hx(x) for x in xs], y=[hy(y) for y in ys], text=txt, texttemplate="%{text}", textfont=dict(size=12),
                             customdata=cd, colorscale=[[0, "#f6d5d3"], [.5, "#ffffff"], [1, "#cfe8d9"]], zmid=0, showscale=False, xgap=2, ygap=2,
                             hovertemplate=f"<b>{yt}: %{{customdata[0]}} · {xt}: %{{customdata[1]}}</b><br>Fairer Wert DCF: %{{customdata[2]}}<br>ggü. Kurs: %{{customdata[3]}}<extra></extra>"))
    f.update_layout(**plot_layout(height=290, margin=dict(l=8, r=8, t=8, b=8),
                                  xaxis=dict(title=dict(text=xt, font=dict(size=12)), side="bottom", type="category", **LOCK),
                                  yaxis=dict(title=dict(text=yt, font=dict(size=12)), autorange="reversed", type="category", **LOCK)))
    pchart(f, width="stretch", config=PLOT_CFG, key=key)


def sensitivities(r, sym, cur):
    s = r["sensitivity"]; p = r["price"]
    a, b = s["wacc_x_terminal_g"], s["margin_x_growth"]
    l, rr = st.columns(2, gap="large")
    with l:
        h2("Kapitalkosten × Endwachstum", None, info="DCF-Wert je Aktie, wenn Kapitalkosten (WACC) und ewiges Wachstum abweichen. Endwachstum ist auf den risikofreien Zins gedeckelt. Grün über, rot unter dem Kurs.")
        heat(a["values"], [a["base_g"] + d for d in a["cols_g_delta"]], [a["base_wacc"] + d for d in a["rows_wacc_delta"]],
             "Endwachstum", "WACC", p, cur, f"hm1_{sym}", lambda x: fpct(min(x, r["cost_of_capital"]["rf"]), 1), lambda y: fpct(y, 1))
    with rr:
        h2("Zielmarge × Wachstum", None, info="DCF-Wert je Aktie bei anderer operativer Zielmarge und anderem Umsatzwachstum in Jahr 1–2 (danach gleicher Übergang). Grün über, rot unter dem Kurs.")
        heat(b["values"], b["cols_growth_delta"], [b["base_margin"] + d for d in b["rows_margin_delta"]],
             "Wachstum J1–2 (Abweichung)", "Zielmarge", p, cur, f"hm2_{sym}", lambda x: fpct(x, 1, True).replace(" %", " Pp."), lambda y: fpct(y, 1))


def dcf_table(r, cur):
    yrs = r["scenarios"]["base"]["model_detail"]["years"]
    rows = [{"Jahr": f'J{y["year"]}', "Umsatz": fbig(y["revenue"], ""), "Wachstum": fpct(y["growth"], 1), "Op. Marge": fpct(y["margin"], 1),
             "Steuer": fpct(y["tax"], 1), "NOPAT": fbig(y["nopat"], ""), "Reinvestition": fbig(y["reinvestment"], ""), "FCFF": fbig(y["fcff"], ""),
             "WACC": fpct(y["wacc"], 1), "Barwert": fbig(y["pv"], "")} for y in yrs]
    st.markdown(table(rows, list(rows[0]), align={k: "r" for k in list(rows[0])[1:]}), unsafe_allow_html=True)


def kv(rows):
    return table([{"Größe": a, "Wert": b, "Herleitung": c} for a, b, c in rows], ["Größe", "Wert", "Herleitung"], align={"Wert": "r"})


def _bt():
    from lib import D as _D; p = _D / "valuation_v3_backtest.json"
    return json.loads(p.read_text())["results"] if p.exists() else None


def _pe_hist(sym):
    """5-Jahres-KGV (GAAP, split-bereinigt) für Vergleich mit heute; {} wenn keine Historie."""
    try:
        import analysis
        peh = analysis.pe_history(sym)
    except Exception:
        return {}
    if peh is None or not len(peh):
        return {}
    med, cur = float(peh.median()), float(peh.iloc[-1])
    return dict(median=med, current_trailing=cur, current_vs_median=cur / med - 1, p25=float(peh.quantile(.25)), p75=float(peh.quantile(.75)))


def _arch_extra(sym, a):
    """Zusatz für das (i): Rüstung (LM-Regel), Konglomerat (SOTP-Segmente), Modellhinweise der Engine v5."""
    r = fairvalue.all_()["stocks"].get(sym) or {}; cl = r.get("classification") or {}; out = ""
    if a.get("key") == "defence" or (a.get("features") or {}).get("defence"):
        out += " Rüstung: Basis = pessimistisches GAAP-Szenario, kein Branchen-KGV."
    so = r.get("sotp") or {}
    if so.get("applied"):
        seg = "; ".join(f'{x["segment"].replace("ReportableSegment", "").replace("Segment", "")} {fbig(x["ev"], "")}' for x in so.get("segments", []))
        out += f" Konglomerat: Summe der Teile ({seg}; Zentralkosten {fbig(so.get('central_costs'), '')}) = {fnum(so.get('per_share'), 0)} je Aktie."
    notes = [n for n in (cl.get("model_notes") or []) if n]
    if notes:
        out += " Modellhinweise: " + "; ".join(notes) + "."
    return out


def arch_pill(sym):
    a = fairvalue.archetype(sym)
    if not a:
        return ""
    feat = a.get("features") or {}
    fx = lambda k, pct=True: (fpct(feat.get(k), 0) if pct else fnum(feat.get(k), 0)) if feat.get(k) is not None else "k. A."
    txt = (f'Archetyp: {a["name"]}. {a["rationale"]} Ausgelöst durch: {a.get("rule")}. Merkmale (zum Bewertungstag): Investitionen/Umsatz {fx("capex_rev")}, '
           f'Wachstum {fx("growth")}, operative Marge {fx("margin")}, Verwässerung p. a. {fx("dilution_3y")}, Aktienvergütung/Umsatz {fx("sbc_rev")}, FCF-Rendite {fx("fcf_yield")}.'
           + (" Strukturbruch erkannt: Historie vor dem Bruch nicht verwendet." if feat.get("structural_break") else "") + _arch_extra(sym, a))
    return f'<span class="pill pos" style="margin-right:4px">{a["name"]}{ii(txt)}</span>'


def pills_html(sym):
    return arch_pill(sym) + " ".join(f'<span class="pill neu" style="margin-right:4px">{x}</span>' for x in fairvalue.pills(sym))


def render(c, sym):
    r = fairvalue.raw(sym); cur = c["currency"]
    erp_txt = ""
    if r:
        cc0 = r["cost_of_capital"]
        erp_txt = f' Marktrisikoprämie {fpct(cc0["erp"], 2)} und Zins {fpct(cc0["rf"], 2)}: Damodaran, implizite Prämie {fdate(cc0["erp_month"])[3:]}.'
    h2("Bewertung", None, info=f"Methode je Geschäftstyp · {cur} · Schlusskurs {fdate(r['asof']) if r else '–'}. Modell nach Geschäftstyp, Spanne aus drei Szenarien, Kaufzone aus der Unsicherheit." + erp_txt)
    if not r:
        st.markdown(f'<span class="pill neu">Keine Bewertung</span>{ii("Für diese Aktie fehlen SEC-Finanzdaten.")}', unsafe_allow_html=True); return
    st.markdown(f'<div style="margin:-4px 0 8px 0">{pills_html(sym)}</div>', unsafe_allow_html=True)
    bad = fairvalue.unreliable(sym); mode = fairvalue.mode(sym); ok = mode == "value" and not bad
    if mode == "implied_return":
        import inv_views
        ir = fairvalue.implied(sym) or {}
        st.markdown(f'<div class="vhero"><div class="top"><div><div class="l">Vom Kurs implizierte Rendite auf neue Kapazität{ii("Kapazitätsaufbau: Der Wert hängt an der Rendite (ROIC) der noch zu bauenden Anlagen. Statt eines Punktwerts zeigt das System, welche Rendite der heutige Kurs voraussetzt. " + __import__("re").sub(r"<[^>]+>", "", inv_views.implied_txt(sym) or ""))}</div>'
                    f'<div class="big">{fpct(ir["value"], 1) if ir.get("value") is not None else "> 80 %"}</div></div>'
                    f'<div><div class="l">Kapitalkosten (WACC)</div><div class="mid">{fpct(ir.get("wacc"), 1)}</div></div>'
                    f'<div><div class="l">Schlusskurs {fdate(r["asof"])}</div><div class="mid">{fprice(r["price"], cur)}</div></div></div>'
                    '</div>', unsafe_allow_html=True)
    elif not ok:
        st.markdown(f'<div class="vhero"><div class="l"><b>Bewertung nicht belastbar</b>{ii("; ".join(bad) + ". Deshalb kein fairer Wert, keine Spanne, keine Kaufzone, keine Tranchen und kein Stresswert aus der Bewertung. Die Modellrechnung unten bleibt zur Nachvollziehbarkeit sichtbar.")}</div>'
                    f'<div class="mid" style="margin-top:4px">Fairer Wert: –</div></div>', unsafe_allow_html=True)
    else:
        hero(r, cur)                # Block 1
    model = r["classification"]["model"]; cl = r["classification"]
    summary_box(r, cur)             # Block 2
    if r.get("sensitivity") and ok:   # ohne gültige Spanne keine Wert-Matrix (wäre eine riesige Spanne durch die Hintertür)
        sensitivities(r, sym, cur)  # Block 3
    b = r["scenarios"]["base"]; d = b["model_detail"]; cc = r["cost_of_capital"]; fs = r["firm"] or {}
    with agx.acc_ctx("v3_cls", "Einordnung und Regeln",
                     f'{fairvalue.MODEL_DE.get(model, model)}, {fairvalue.MOAT_DE.get(cl["moat"], "")}, Phase {fairvalue.STAGE_DE.get(cl["stage"], "")}.'):
        lw = r.get("long_window") or {}
        a_ = r.get("archetype") or {}
        rows = [("Archetyp", a_.get("name", "k. A."), f'{a_.get("rule", "")}. Zielmarge: {(r.get("margin") or {}).get("reference", "k. A.")}; Beta/Kapitaleffizienz: Vergleichsgruppe {a_.get("peer_group", "k. A.")} (n = {a_.get("peer_n", "k. A.")})'),
                ("Modell", fairvalue.MODEL_DE.get(model, model), "Banken/Versicherungen und Versorger: Übergewinn auf Eigenkapital; REITs: FFO; sonst Cashflow-DCF"),
                ("Burggraben", fairvalue.MOAT_DE.get(cl["moat"], "k. A."), f'{cl.get("moat_basis", "Kapitalrendite")} über Kapitalkosten (Median bis 10 Jahre, {lw.get("roic_n", "k. A.")} Quartale): {fpct(cl.get("excess_roic_long"), 1, True)}; breit ab +10 Pp. und Marge > 20 %'),
                ("Wachstumsphase", fairvalue.STAGE_DE.get(cl["stage"], "k. A."), f'Umsatzwachstum {fpct(cl.get("growth_for_stage"), 1)}: über 30 % Hyperwachstum, über 12 % hoch'),
                ("Gewichtung DCF / KGV", f'{fpct(r["weights"]["dcf"], 0)} / {fpct(r["weights"]["forward_pe"], 0)}', "nach Phase; Reinvestierer (Free Cashflow < 50 % des Gewinns) ohne KGV-Anteil"),
                ("Zykliker", "ja" if cl["cyclical"] else "nein", "Halbleiter, Rohstoffe, Energie u. a.: Marge = Median über bis zu 10 Jahre"),
                ("Unsicherheit", cl.get("uncertainty") or "ohne Schätzungen", f'Spannweite der Gewinnschätzungen {fpct(cl.get("eps_dispersion"), 0)} → Sicherheitsmarge {fpct(cl.get("margin_of_safety") if cl.get("margin_of_safety") is not None else .5, 0)}')]
        if cl.get("defence"):
            rows.append(("Rüstung", "pessimistisch", "Basis = pessimistisches Szenario auf GAAP-Basis"))
        st.markdown(kv(rows), unsafe_allow_html=True)
    if model == "fcff":
        i = d["inputs"]; t = d["terminal"]; mg = r["margin"]
        with agx.acc_ctx("v2_dcf", "DCF-Rechner: Umsatz, Marge, Reinvestition",
                         f'Ausgangspunkt Umsatz {fbig(fs["revenue_ttm"], cur)} ({"Geschäftsjahr, nur Jahreszahlen" if fs.get("only_annual") else "letzte 12 Monate"}), operative Marge {fpct(i["margin0"], 1)} → Ziel {fpct(i["margin_target"], 1)} bis Jahr 5, '
                         f'Kapitaleffizienz {fnum(i["sales_to_capital"], 2)}. DCF-Wert {fprice(b["intrinsic"], cur, 0)}.'):
            dcf_table(r, cur)
            st.markdown(kv([("Zielmarge", fpct(i["margin_target"], 1), f'{mg["own_basis_kind"]} {fpct(mg["own_basis"], 1)}, {fpct(mg["reversion_share"], 0)} der Lücke zum Median {fpct(mg["sector_median"], 1)} der {mg.get("reference", "Vergleichsgruppe")}'),
                            ("Umsatz je investiertem Kapital", fnum(i["sales_to_capital"], 2), "Median über den Zyklus"),
                            ("Aktienvergütung", fbig(fs.get("sbc_ttm"), cur), "im operativen Ergebnis als Kosten enthalten"),
                            ("Nettoverschuldung", fbig(i["net_debt"], cur), f'Schulden {fbig(fs["total_debt"], cur)} − Cash und kurzfristige Wertpapiere {fbig(fs["cash"], cur)}'),
                            ("Aktien (verwässert)", fnum(i["shares"] / 1e6, 0) + " Mio.", f'SEC-Abschluss {fdate(fs["last_quarter_end"])}')]), unsafe_allow_html=True)
        with agx.acc_ctx("v2_wacc", "Kapitalkosten (WACC)",
                         f'WACC {fpct(cc["wacc"], 1)} = Eigenkapitalkosten {fpct(cc["cost_of_equity"], 1)} und Fremdkapitalkosten {fpct(cc["cost_of_debt_after_tax"], 1)} nach Steuern.'):
            st.markdown(kv([("Risikofreier Zins", fpct(cc["rf"], 2), f'10-jährige US-Staatsanleihe laut Damodaran, Monat {fdate(cc["erp_month"])[3:]}'),
                            ("Marktrisikoprämie", fpct(cc["erp"], 2), f'implizite Prämie nach Damodaran im selben Monat ({cc.get("erp_basis")})'),
                            ("Beta", fnum(cc["beta"], 2), f'½ eigenes 5-Jahres-Beta {fnum(cc.get("beta_regression_blume"), 2)} (bereinigt) + ½ Median der Vergleichsgruppe {fnum(cc.get("beta_peer_median") or cc.get("beta_sector_median"), 2)}'),
                            ("Länderrisikoprämie", fpct(cc.get("crp") or 0, 2), f'Damodaran, {cc.get("crp_country") or "k. A."} ({cc.get("crp_basis") or "Sitz"}); auf die Eigenkapitalkosten addiert'),
                            ("Eigenkapitalkosten", fpct(cc["cost_of_equity"], 2), "risikofreier Zins + Beta × Marktrisikoprämie + Länderrisikoprämie"),
                            ("Fremdkapitalkosten vor Steuern", fpct(cc["cost_of_debt_pre_tax"], 2), (f'Zins + Aufschlag {fpct(cc["spread"], 2)} aus der Zinsdeckung' if not cc.get("kd_basis") else f'{cc["kd_basis"]}: Zinsdeckung ≤ 0, Tabelle nicht anwendbar')),
                            ("WACC Jahr 1–5 / ab Jahr 10", f'{fpct(cc["wacc"], 1)} / {fpct(cc["wacc_mature"], 1)}', "Übergang auf ein reifes Unternehmen")]), unsafe_allow_html=True)
        with agx.acc_ctx("v2_tv", "Endwert",
                         f'Der Endwert macht {fpct(d["terminal_share"], 0)} des Unternehmenswerts aus. Ewiges Wachstum {fpct(t["g"], 1)}.'):
            st.markdown(kv([("Ewiges Wachstum", fpct(t["g"], 2), "min(risikofreier Zins, 3,5 %)"),
                            ("Kapitalrendite im Endwert", fpct(t["roic"], 1), f'Kapitalkosten + {fpct(i.get("roic_fade"), 0)} der Überrendite (nach Burggraben)'),
                            ("Reinvestitionsquote", fpct(t["reinvestment_rate"], 1), "Wachstum ÷ Kapitalrendite"),
                            ("Barwert Jahre 1–10", fbig(d["pv_explicit"], cur), ""), ("Barwert Endwert", fbig(d["pv_terminal"], cur), ""),
                            ("Unternehmenswert", fbig(d["ev"], cur), ""), ("Eigenkapitalwert", fbig(d["equity"], cur), "Unternehmenswert − Nettoverschuldung")]), unsafe_allow_html=True)
    else:
        with agx.acc_ctx("v3_fin", "Eigenkapital-Modell",
                         f'Eigenkapitalkosten {fpct(cc["cost_of_equity"], 1)}, Eigenkapital {fbig(fs.get("equity"), cur)}, Eigenkapitalrendite {fpct(fs.get("roe_ttm"), 1)}.'):
            rows = [("Eigenkapitalkosten", fpct(cc["cost_of_equity"], 2), f'Zins {fpct(cc["rf"], 2)} + Beta {fnum(cc["beta"], 2)} × Prämie {fpct(cc["erp"], 2)} (Damodaran)'),
                    ("Eigenkapital", fbig(fs.get("equity"), cur), "SEC-Abschluss"), ("Gewinn 12 Monate", fbig(fs.get("net_income_ttm"), cur), "")]
            if model == "excess_returns":
                rows.append(("Eigenkapitalrendite im Endwert", fpct(d.get("roe_terminal"), 1), "Kapitalkosten + Anteil der Überrendite nach Burggraben"))
            st.markdown(kv(rows + [("Barwert Endwert", fbig(d.get("pv_terminal"), cur), ""), ("Eigenkapitalwert", fbig(d.get("equity"), cur), "")]), unsafe_allow_html=True)
    f = b.get("forward_pe")
    if f:
        h = f.get("vs_history") or _pe_hist(sym); sx = f.get("vs_sector") or {}
        with agx.acc_ctx("v2_fpe", "Forward-KGV im Detail",
                         f'Forward-KGV {fmult(f["forward_pe"])}, begründet {fmult(f["justified"]["justified_pe"])}, fairer Preis {fprice(f["fair_price"], cur, 0)}.'):
            n = f["ntm"]
            st.markdown(kv([("Gewinn je Aktie nächste 12 Monate", fprice(n["ntm_eps"], cur), f'{fpct(n["weight_fy0"], 0)} laufendes + {fpct(1 - n["weight_fy0"], 0)} nächstes Geschäftsjahr' + (" (bereinigt)" if n["normalised_fy0"] else "")),
                            ("Forward-KGV", fmult(f["forward_pe"]), "Kurs ÷ Gewinn je Aktie nächste 12 Monate"),
                            ("KGV 5-Jahres-Median (GAAP)", fmult(h.get("median")), f'mittlere Hälfte {fmult(h.get("p25"))} – {fmult(h.get("p75"))}'),
                            ("Wachstum im Modell", fpct(f["growth_used"], 1), "Konsens, 5 Jahre, dann Übergang"),
                            ("Eigenkapitalrendite / -kosten", f'{fpct(f["roe"], 1)} / {fpct(f["cost_of_equity"], 1)}', "bestimmt die Ausschüttungsquote"),
                            ("Begründetes KGV", fmult(f["justified"]["justified_pe"]), f'reifes KGV {fmult(f["justified"]["gordon_mature_pe"])}'),
                            ("Konsens ggü. GAAP-Gewinn", fpct(f.get("consensus_vs_gaap_ttm"), 1, True), "Abweichung des Konsens-Gewinns vom GAAP-Gewinn der letzten 12 Monate")]), unsafe_allow_html=True)
    _pe_chart(c, sym)
    if not ok:
        return
    with agx.acc_ctx("v2_scen", "Szenarien der Spanne", "Drei Szenarien mit festen Regeln."):
        lab = {"pessimistic": "Pessimistisch", "base": "Basis", "optimistic": "Optimistisch"}
        rows = [{"Szenario": lab[k], "Fairer Wert": fnum(r["scenarios"][k]["fair_value"], 0), "Modellwert": fnum(r["scenarios"][k]["intrinsic"], 0),
                 "KGV-Modell": fnum(r["scenarios"][k]["pe_value"], 0) if r["scenarios"][k]["pe_value"] else "–",
                 "Zielmarge": fpct(r["scenarios"][k].get("margin_target"), 1) if r["scenarios"][k].get("margin_target") is not None else "–"} for k in lab]
        st.markdown(table(rows, list(rows[0]), align={k: "r" for k in list(rows[0])[1:]}), unsafe_allow_html=True)
    bt = _bt()
    if bt:
        tr, v = bt["train"], bt["val"]; t1, v1 = tr["ret_1y_x"], v["ret_1y_x"]; cal = tr["calibration_3y"]["v3"]
        with agx.acc_ctx("v2_val", "Wie verlässlich ist das?",
                         f'Rückblick 2012 bis 2021 über rund {fnum((tr["n"] + v["n"]) / 1000, 0)}.000 Bewertungen: etwas besser als v2, aber nicht besser als die einfache Free-Cashflow-Rendite. Kurse laufen nicht verlässlich zum fairen Wert.'):
            st.markdown(kv([("2012–2019 Rangkorrelation (1 Jahr)", fnum(t1["v3_all"]["ic_mean"], 3), f'v2 {fnum(t1["v2"]["ic_mean"], 3)} · Free-Cashflow-Rendite {fnum(t1["fcf_yield"]["ic_mean"], 3)}'),
                            ("2020–2021 Rangkorrelation (1 Jahr)", fnum(v1["v3_all"]["ic_mean"], 3), f'v2 {fnum(v1["v2"]["ic_mean"], 3)} · Free-Cashflow-Rendite {fnum(v1["fcf_yield"]["ic_mean"], 3)}'),
                            ("Abstand zum fairen Wert nach 3 Jahren", f'kleiner in {fpct(cal["share_gap_shrinks"], 0)}', f'mittlere Abweichung {fpct(cal["median_abs_err_pct"], 0)} (2012–2019)'),
                            ("Einordnung", "kein Vorsprung", "Der Wert macht Erwartungen nachrechenbar, er ist kein Kaufsignal. Ab 2023 versiegelt, nicht ausgewertet.")]), unsafe_allow_html=True)


def _pe_chart(c, sym):
    import pandas as pd
    import analysis
    from lib import prices_long
    peh = analysis.pe_history(sym)
    if peh is None:
        return
    with agx.acc_ctx("kgvhist", "KGV-Verlauf 5 Jahre", f"KGV je Handelstag, Median {fmult(peh.median())}, hellblau die mittlere Hälfte der Tage."):
        pv = prices_long(sym)[["date"]].copy(); pv["date"] = pd.to_datetime(pv.date)
        d_ = pv[pv.date >= pv.date.max() - pd.DateOffset(years=5)].date.iloc[-len(peh):].tolist()
        f = go.Figure()
        f.add_hrect(y0=float(peh.quantile(.25)), y1=float(peh.quantile(.75)), fillcolor="#eaf2fa", line_width=0, layer="below")
        f.add_trace(go.Scatter(x=d_, y=peh.tolist(), mode="lines", line=dict(color=BLUE, width=1.8), hovertemplate=agx.single("%{x|%d.%m.%Y}", "KGV", ",.1f", "×")))
        f.add_hline(y=float(peh.median()), line=dict(color=INK, width=1, dash="dash"))
        f.update_layout(**plot_layout(height=320, margin=dict(l=8, r=40, t=10, b=8), showlegend=False,
                                      yaxis=dict(gridcolor="#eef2f6", range=[0, float(peh.quantile(.98)) * 1.1], ticksuffix="×", **LOCK),
                                      xaxis=dict(showgrid=False, **LOCK)))
        pchart(f, width="stretch", config=PLOT_CFG, key=f"pehist_{sym}")
