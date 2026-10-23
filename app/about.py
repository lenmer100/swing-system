import re
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from lib import pchart, inote, page_head, load, footer2, de, strip, section, table, plot_layout, PLOT_CFG, fnum, fdate

META, CASES, VAL = load()
PLOT = plot_layout()
PLOT.pop("margin"); PLOT.pop("separators")

def head(eyebrow, title, lead=None):
    page_head(eyebrow, title, lead)

CLAB = {"Modell v0 allein": "nur eigenes Modell", "U1 Kursziel-Upside allein": "nur Kursziel-Potenzial",
        "U2 Tie-Breaker (Modell-Quintil, dann Upside)": "Modell zuerst, Kursziel als Entscheider", "U3 Revisionsmomentum 90 T.": "Schätzungsrevisionen 90 Tage",
        "U4 Gate Modell ≥ 8 % + Upside ≥ 0": "Modell ≥ 8 % und Kursziel über Kurs"}

def subhead(title, lead=None):
    st.markdown(f'<div class="h2">{title}</div>' + (f'<p class="lead">{lead}</p>' if lead else ""), unsafe_allow_html=True)

def f(x):
    x = x.replace("−", "-").replace("%", "").replace("+", "").strip()
    try: return float(x)
    except ValueError: return None

def overview():
    subhead("Worum es geht",
         "Eine Python-Pipeline, die für über 1.000 US- und EU-Aktien jeden Tag aus Rohdaten ein nachvollziehbares Urteil rechnet: "
         "<b>Ist das Unternehmen gut? Ist es fair bewertet? Ist jetzt ein guter Einstiegszeitpunkt?</b>")
    strip([("Aktien im Universum", de(META["n_universe"], 0), f'davon {META["n_eur"]} aus Europa'),
           ("Automatisierte Tests", "374", "pytest"), ("Tageslauf", de(META["runtime_min"], 1) + " min", f'{META["workers"]} parallele Prozesse'),
           ("Codeumfang", "≈ 41.000", "Zeilen Python inkl. Tests")])
    a, b = st.columns([1.1, 1], gap="large")
    with a:
        section("Problem")
        st.markdown("Fundamentalanalyse und Charttechnik passieren meist getrennt und von Hand. Portale zeigen fertige Kennzahlen, "
                    "ohne dass man nachrechnen kann, wie sie entstehen. Viele Backtests sind durch Lookahead (Nutzung von Daten, "
                    "die damals noch nicht bekannt waren) zu optimistisch.")
        section("Ansatz")
        st.markdown("- Fundamentaldaten direkt aus **SEC-EDGAR-XBRL**, rekonstruiert zum jeweiligen Wissensstand (point-in-time)\n"
                    "- **Quality-Growth-Bewertung:** Qualität je Branchentyp, drei Bewertungsszenarien und zwölf nachgerechnete Bewertungsmodelle (je nach Aktie sind nicht alle anwendbar, z. B. Dividenden- oder Graham-Modelle)\n"
                    "- **Chart-Timing:** Trendphase über die 30-Wochen-Linie, Unterstützungen und Einstiegszonen, Zahlentermine als Sperre\n"
                    "- **Analystenkonsens** als zusätzliche, geprüfte Info-Säule\n"
                    "- jede Regel liegt in Konfigurationsdateien, jede Zahl lässt sich auf ihre Quelle zurückführen")
    with b:
        section("Tech-Stack")
        st.markdown('<div class="card">'
                    "<b>Sprache & Daten:</b> Python 3.13, pandas, DuckDB + Parquet<br>"
                    "<b>Quellen:</b> SEC EDGAR XBRL, yfinance, FRED, Alpha Vantage, Financial Modeling Prep<br>"
                    "<b>Rechnen:</b> multiprocessing (parallele Analyse je Titel)<br>"
                    "<b>Qualität:</b> pytest, Referenzfälle, Stichproben-Audits<br>"
                    "<b>Darstellung:</b> Streamlit, Plotly, TradingView Lightweight Charts™"
                    "</div>", unsafe_allow_html=True)
        st.write("")
        st.markdown('<div class="card"><b>Rolle:</b> Konzeption, Datenmodell, Bewertungslogik, Backtest-Design und Umsetzung '
                    'als Einzelprojekt im Rahmen meines Studiums (Data and Information Science, TH Köln).</div>', unsafe_allow_html=True)
    footer2(META, about_link=False)

def architecture():
    subhead("Von Rohdaten zum Urteil",
         "Jede Aktie läuft durch dieselben sechs Stufen. Qualität und Bewertung entscheiden, <i>ob</i> eine Aktie interessant ist, "
         "der Chart nur, <i>wann</i>.")
    steps = [("Daten", "EDGAR-Abschlüsse, Kurse, Konsens"), ("Qualität", "ROIC, Free Cashflow, Wachstum, Bilanz"),
             ("Bewertung", "3 Szenarien, 12 Modelle"), ("Analysten-Säule", "Konsens, Kursziele, Revisionen"),
             ("Chart / Einstieg", "30-Wochen-Trend, Zonen, Termine"), ("Urteil", "Kategorie + Begründung")]
    st.markdown('<div class="pipe">' + '<div class="a">›</div>'.join(f'<div class="s"><b>{i+1}. {t}</b><span>{s}</span></div>'
                for i, (t, s) in enumerate(steps)) + "</div>", unsafe_allow_html=True)
    st.write("")
    section("So entsteht ein Urteil")
    c = st.columns(3, gap="medium")
    c[0].markdown('<div class="card"><b>1 · Qualität</b><br><span class="muted">Kennzahlen wie Kapitalrendite, normalisierter Free Cashflow, '
                  'Aktienvergütung und Verschuldung werden mit Ampeln bewertet und innerhalb vergleichbarer Firmen (Branchentyp) zu einem '
                  'Perzentil-Score verdichtet. Unter der Schwelle → „Qualität nicht erfüllt“.</span></div>', unsafe_allow_html=True)
    c[1].markdown('<div class="card"><b>2 · Bewertung</b><br><span class="muted">Fünf-Jahres-Szenarien (konservativ, Basis, positiv) aus Umsatz, '
                  'Marge und Exit-KGV ergeben eine erwartete Rendite p. a. Ist die Basis-Rendite zu niedrig oder das im Kurs eingepreiste '
                  'Wachstum historisch selten → „zu teuer“.</span></div>', unsafe_allow_html=True)
    c[2].markdown('<div class="card"><b>3 · Einstieg</b><br><span class="muted">Nur bei steigender 30-Wochen-Linie und Kurs nahe einer '
                  'Unterstützung oder in der Einstiegszone wird es „Kaufbereit“. Zahlentermine im Haltefenster, ein schwacher Gesamtmarkt oder '
                  'Sektor führen zu „Warten“ oder halber Größe.</span></div>', unsafe_allow_html=True)
    st.write("")
    section(f'Verteilung der Urteile im Gesamtuniversum ({fdate(META["asof"])})')
    CATDE = {"Qualität nein": "Qualität nicht erfüllt", "Halten am ATH (kein Neukauf)": "Halten nahe Allzeithoch (kein Neukauf)",
             "Warten: 30W fällt": "Warten: 30-Wochen-Linie fällt", "Zyklik: normalisiert teuer": "Zykliker: normalisiert teuer",
             "Kaufbereit (Langfrist-Tranche)": "Kaufbereit (langfristige Teilposition)", "PI: Einkommen geeignet": "geeignet für Einkommensstrategie",
             "nahe Kaufzone (<3 %)": "nahe Einstiegszone (unter 3 %)"}
    cats = pd.Series({CATDE.get(k, k): v for k, v in META["categories"].items()}).sort_values()
    fig = go.Figure(go.Bar(x=cats.values, y=cats.index, orientation="h", marker_color="#1849a9", text=cats.values, textposition="outside"))
    fig.update_layout(height=420, margin=dict(l=10, r=40, t=10, b=10), **PLOT, separators=",.", xaxis=dict(gridcolor="#f2f4f7"))
    pchart(fig, width="stretch", config=PLOT_CFG)
    st.markdown(f'<div class="inote"><span class="ii" tabindex="0" aria-label="Erläuterung">i<span class="tip">{de(META["n_analysed"], 0)} analysierte Titel. Die meisten scheitern bewusst an Qualität oder Bewertung: Das System ist streng gebaut.</span></span><span class="il">Erläuterung</span></div>', unsafe_allow_html=True)
    section("Methodische Strenge")
    m = st.columns(3, gap="medium")
    m[0].markdown('<div class="card"><b>Point-in-time</b><ul class="muted"><li>Abschlusszahlen gelten erst ab dem Tag nach der Einreichung bei der SEC</li>'
                  '<li>unbereinigte Kurse + Split-Faktoren für korrekte Multiples</li><li>historische Indexmitglieder gegen Survivorship-Bias</li></ul></div>', unsafe_allow_html=True)
    m[1].markdown('<div class="card"><b>Saubere Zeitaufteilung</b><ul class="muted"><li>Training 2012–2019, Validierung 2020–2022</li>'
                  '<li>2023+ versiegelt: genau ein Test nach dem Einfrieren</li><li>Regel nur übernommen, wenn in Training <b>und</b> Validierung nicht schlechter</li></ul></div>', unsafe_allow_html=True)
    m[2].markdown('<div class="card"><b>Kein Overfitting</b><ul class="muted"><li>Varianten werden vorab benannt, keine Parametersuche</li>'
                  '<li>unklare Daten → „Fundamentaldaten unsicher“ statt geratenem Urteil</li><li>Konsens-Signale bleiben Info, bis genug eigene Historie testbar ist</li></ul></div>', unsafe_allow_html=True)
    footer2(META, about_link=False)

def validation_body():
    subhead("Was die Tests zeigen, und was nicht",
         "Alle Zahlen stammen unverändert aus den Studienberichten des Projekts. IC = Rangkorrelation (Spearman) zwischen Signal und "
         "späterer 12-Monats-Überrendite gegenüber dem S&P 500 (SPY). Training = 2012–2019, Validierung = 2020–2021/22, 2023+ ist versiegelt.")
    ap5 = VAL["ap5"][0]
    df = pd.DataFrame(ap5["rows"], columns=ap5["cols"])
    df["IC"] = df["IC Ø (t)"].map(lambda s: f(s.split("(")[0]))
    df["Q"] = df["Q5−Q1"].map(f)
    df["Anteil"] = df["Anteil FV>Kurs"].map(f)
    names = {"K1": "fix 9 %", "K2": "Zins 10 Jahre + 5 %", "K3": "Zins 10 Jahre + Beta × 5 %"}
    section("1 · DCF-Kapitalkosten: drei vorab benannte Varianten")
    c1, c2 = st.columns(2, gap="large")
    with c1:
        fig = go.Figure()
        for per, col in (("train", "#98a2b3"), ("val", "#1849a9")):
            d = df[df.Periode == per]
            fig.add_trace(go.Bar(name="Training 2012–19" if per == "train" else "Validierung 2020–21", x=[names.get(k, k) for k in d["Konv."]],
                                 y=d.IC, marker_color=col, marker_line=dict(color=col, width=2), text=[fnum(v, 3).replace("-", "−") if v < 0 else "+" + fnum(v, 3) for v in d.IC], textposition="outside"))
        fig.update_layout(barmode="group", height=340, margin=dict(l=10, r=10, t=40, b=10), **PLOT,
                          title=dict(text="Ø IC des DCF-Signals", font=dict(size=14)), legend=dict(orientation="h", y=-0.15),
                          separators=",.", yaxis=dict(gridcolor="#f2f4f7", zeroline=True, zerolinecolor="#98a2b3"))
        pchart(fig, width="stretch", config=PLOT_CFG)
    with c2:
        fig = go.Figure()
        for per, col in (("train", "#98a2b3"), ("val", "#1849a9")):
            d = df[df.Periode == per]
            fig.add_trace(go.Bar(name="Training" if per == "train" else "Validierung", x=[names.get(k, k) for k in d["Konv."]],
                                 y=d.Anteil, marker_color=col, marker_line=dict(color=col, width=2), text=[fnum(v, 0) + " %" for v in d.Anteil], textposition="outside"))
        fig.update_layout(barmode="group", height=340, margin=dict(l=10, r=10, t=40, b=10), **PLOT,
                          title=dict(text="Anteil Aktien „unterbewertet“ (fairer Wert > Kurs)", font=dict(size=14)),
                          legend=dict(orientation="h", y=-0.15), separators=",.", yaxis=dict(gridcolor="#f2f4f7", ticksuffix=" %", range=[0, 85]))
        pchart(fig, width="stretch", config=PLOT_CFG)
    st.markdown("**Ergebnis:** In 2012–19 hatte der DCF praktisch keine Vorhersagekraft (IC ≈ 0), in 2020–21 eine deutliche (IC ≈ 0,13–0,17). "
                "Die Reihenfolge der Aktien ist bei allen Varianten ähnlich. Die marktabhängigen Varianten hätten in der Niedrigzinsphase aber "
                "57–71 % aller Aktien als unterbewertet ausgewiesen. Gewählt wurde deshalb **fix 9 %**, und der DCF bleibt eine Info-Spalte.")
    with st.expander("Originaltabelle aus dem Studienbericht"):
        cn = {"Periode": "Zeitraum", "Konv.": "Variante", "n": "Beobachtungen", "r Median": "Kapitalkosten (Median)", "IC Ø (t)": "IC Durchschnitt (t-Wert)",
              "IC gepoolt": "IC gepoolt", "Q5−Q1": "Bestes − schlechtestes Fünftel", "FV>Kurs − FV≤Kurs": "Unterbewertet − überbewertet",
              "Median FV/Kurs": "Fairer Wert / Kurs (Median)", "Anteil FV>Kurs": "Anteil unterbewertet", "Reverse-DCF-Gap-IC": "IC der Reverse-DCF-Lücke"}
        per = {"train": "Training", "val": "Validierung"}
        rows = [{cn.get(k, k): (per.get(v, names.get(v, v)) if k in ("Periode", "Konv.") else v.replace(".", ",") if any(ch.isdigit() for ch in v) else v)
                 for k, v in zip(ap5["cols"], r)} for r in ap5["rows"]]
        st.markdown(table(rows, [cn.get(k, k) for k in ap5["cols"]]), unsafe_allow_html=True)

    tabs = {t["heading"][:1]: t for t in VAL["v36j"]}
    section("2 · Qualitätsscore: Umgang mit fehlender Aktienvergütung")
    b = tabs["B"]; th = next(t for t in VAL["v36j"] if t["heading"].startswith("Schwelle"))
    c1, c2 = st.columns(2, gap="large")
    lab = {"Z fehlt = 0 (v3.6h)": "fehlt = 0 (alt)", "X ausgelassen (v3.6i live)": "auslassen (live)",
           "N = Median-Perzentil 50": "Median einsetzen", "H Allokationssäule halb gewichtet": "halb gewichten"}
    with c1:
        fig = go.Figure()
        for i, (nm, col) in enumerate((("Training", "#98a2b3"), ("Validierung", "#1849a9"))):
            fig.add_trace(go.Bar(name=nm, x=[lab.get(r[0], r[0]) for r in b["rows"]], y=[f(r[1 + i]) for r in b["rows"]], marker_color=col, marker_line=dict(color=col, width=2),
                                 text=[fnum(f(r[1 + i]), 3) for r in b["rows"]], textposition="outside"))
        fig.update_layout(barmode="group", height=340, margin=dict(l=10, r=10, t=40, b=10), **PLOT, legend=dict(orientation="h", y=-0.2),
                          title=dict(text="IC des Qualitätsscores je Variante", font=dict(size=14)), separators=",.", yaxis=dict(gridcolor="#f2f4f7", range=[0, 0.065]))
        pchart(fig, width="stretch", config=PLOT_CFG)
    with c2:
        fig = go.Figure()
        for i, (nm, col) in enumerate((("Training", "#98a2b3"), ("Validierung", "#1849a9"))):
            fig.add_trace(go.Bar(name=nm, x=[r[0].replace("p", "Perzentil ") for r in th["rows"]], y=[f(r[1 + i]) * 100 for r in th["rows"]], marker_color=col, marker_line=dict(color=col, width=2),
                                 text=[('+' if f(r[1+i]) >= 0 else '−') + fnum(abs(f(r[1+i]) * 100), 2) + ' Pp.' for r in th["rows"]], textposition="outside"))
        fig.update_layout(barmode="group", height=340, margin=dict(l=10, r=10, t=40, b=10), **PLOT, legend=dict(orientation="h", y=-0.2),
                          title=dict(text="Überrendite bestanden − nicht bestanden je Schwelle (Prozentpunkte)", font=dict(size=14)),
                          separators=",.", yaxis=dict(gridcolor="#f2f4f7", ticksuffix=" Pp.", range=[0, 2.6]))
        pchart(fig, width="stretch", config=PLOT_CFG)
    st.markdown("**Ergebnis:** Fehlende Werte auszulassen schlägt „fehlt = 0“ im IC in Training und Validierung. Unter dieser Regel ist die "
                "Schwelle Perzentil 55 in beiden Zeiträumen besser als 60 und wurde übernommen. Die Unterschiede im Training sind klein (≈ 0,1 Pp.).")

    section("3 · Analystensignale: getestet, aber nicht übernommen")
    cc = tabs["C"]
    rows = [r for r in cc["rows"] if f(r[1]) is not None]
    fig = go.Figure()
    for i, (nm, col) in enumerate((("Training", "#98a2b3"), ("Validierung", "#1849a9"))):
        fig.add_trace(go.Bar(name=nm, y=[CLAB.get(r[0], r[0]) for r in rows], x=[f(r[1 + i]) for r in rows], orientation="h", marker_color=col, marker_line=dict(color=col, width=2),
                             text=[fnum(f(r[1 + i]), 3) for r in rows], textposition="outside"))
    fig.update_layout(barmode="group", height=360, margin=dict(l=10, r=40, t=10, b=10), **PLOT, legend=dict(orientation="h", y=-0.12),
                      separators=",.", xaxis=dict(gridcolor="#f2f4f7", zeroline=True, zerolinecolor="#98a2b3", range=[-0.14, 0.22]), yaxis=dict(autorange="reversed"))
    pchart(fig, width="stretch", config=PLOT_CFG)
    st.markdown("**Ergebnis:** Keine Analysten-Variante ist in Training **und** Validierung besser als das eigene Modell. Das Revisionsmomentum "
                "kippt in der Validierung sogar ins Negative. Die Analysten-Säule bleibt deshalb reine Info.")

    section("Grenzen, ehrlich benannt")
    st.markdown('<div class="card"><ul>'
                "<li><b>Überlappende 12-Monats-Fenster:</b> t-Werte sind überzeichnet, die IC-Werte sind die belastbarere Größe.</li>"
                "<li><b>Konsens-Historie fehlt:</b> Eigene Schätzungs-Snapshots gibt es erst seit 04.10.2026. Tests mit Konsens-EPS sind historisch nicht möglich, frühestens ab 2027.</li>"
                "<li><b>Survivorship:</b> Die Kursziel-Historie umfasst nur heutige Titel (453 von 899 Panel-Titeln).</li>"
                "<li><b>Regimeabhängigkeit:</b> Bewertungssignale wirken 2020–22 deutlich stärker als 2012–19.</li>"
                "<li><b>Versiegelter Test 2023+</b> ist noch nicht gelaufen und wird nach dem Einfrieren genau einmal ausgewertet.</li>"
                "</ul></div>", unsafe_allow_html=True)
    footer2(META, about_link=False)

def sources():
    subhead("Woher die Zahlen kommen", "Nur offizielle oder öffentliche Schnittstellen, kein Scraping gegen Nutzungsbedingungen.")
    rows = [("SEC EDGAR (companyfacts, XBRL)", "Jahres-/Quartalsabschlüsse 10-K, 10-Q, 20-F", "point-in-time über das Einreichungsdatum, ~15 Jahre Historie"),
            ("yfinance", "Tageskurse ab 2015, Splits, Zahlentermine, Analystenkonsens, Kursziele", "täglicher Snapshot seit 04.10.2026 als eigenes Archiv"),
            ("Alpha Vantage (Gratis-Schlüssel)", "Schätzungen inkl. Revisionen, Quartals-Konsens", "25 Abrufe pro Tag, Zweitquelle"),
            ("Financial Modeling Prep (Gratis-Schlüssel)", "Kursziel-Konsens, Schätzungen", "Gratisumfang ≈ 70 große US-Titel, Zweitquelle"),
            ("FRED", "Zinsen, Dollar-Index, Ölpreis, Kreditspreads", "Makro-Kontext, ohne Schlüssel"),
            ("Wikipedia", "Indexmitglieder S&P 500 / Nasdaq-100 (mit Datum)", "Universum + historische Mitgliedschaften")]
    st.markdown(table([dict(zip(["Quelle", "Inhalt", "Hinweis"], (f"<b>{r[0]}</b>",) + r[1:])) for r in rows], ["Quelle", "Inhalt", "Hinweis"]), unsafe_allow_html=True)
    section("Datenprüfungen im Tageslauf")
    st.markdown("- Konsens wird vereinheitlicht: gleiches Geschäftsjahr, gleiche Gewinnbasis (GAAP/bereinigt, bei REITs FFO), Währung und Einheit\n"
                "- Werte, die eine Prüfung nicht bestehen (Frische, ≥ 3 Analysten, Streuung, Kursabweichung), werden ausgeblendet statt still ersetzt\n"
                "- Kursprüfung erkennt veraltete oder eingestellte Kursreihen, Zahlentermine kommen deterministisch aus dem eigenen Archiv\n"
                "- Auslandsaktien: ADR-Verhältnis, Abschlusswährung und Wechselkurs zum Stichtag werden geprüft")
    section("Stand dieser Demo")
    st.markdown(f'- Einzelanalysen: korrigierte Stichprobe v3.6k, Schlusskurse {fdate(META["asof"])}\n'
                f'- Universumszahlen: letzter Volllauf vom {fdate(META["asof"])}\n'
                "- Statischer Snapshot, die Demo ruft keine Live-Schnittstellen ab")
    footer2(META, about_link=False)


def about(default=None):
    """Einzige Seite mit Projektbezug: kurz, sachlich, ohne Methodik-Interna."""
    st.markdown('<h1 class="ptitle">Über das Projekt</h1>'
                '<p class="lead" style="max-width:760px">Eigenes Projekt: ein Werkzeug für Aktienanalyse, Swing-Trading und langfristiges Investieren auf Basis öffentlicher Unternehmens-, Kurs- und Konsensdaten.</p>'
                '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:22px 0">'
                + "".join(f'<div style="border:1px solid var(--line);border-radius:10px;padding:16px 18px;background:#fff"><div style="font-weight:700;margin-bottom:4px">{t}</div><div class="muted">{d}</div></div>'
                          for t, d in (("Aktienanalyse", "Kurs, Analysten, Bewertung, Finanzdaten"), ("Swing-Tool", "Setups, Einstiegszone, Stopp, Termine"), ("Investment", "Tranchen, Positionsgröße, Stressszenario")))
                + "</div>", unsafe_allow_html=True)
    footer2(META, about_link=False)

def validation():
    about()
