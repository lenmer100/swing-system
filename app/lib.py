import json, re
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
D = ROOT / __import__("os").environ.get("DATA_DIR", "data")   # DATA_DIR=data_full zum Testen des Vollimports

@st.cache_data
def _clean_names(cases):
    for c in cases.values():   # "Coca-Cola Company (The)" -> "The Coca-Cola Company"
        n = c.get("name") or ""
        if n.endswith(" (The)"): c["name"] = "The " + n[:-6]
    return cases

def load():
    return (json.loads((D / "meta.json").read_text()), _clean_names(json.loads((D / "cases.json").read_text())),
            json.loads((D / "validation.json").read_text()))

@st.cache_data
def prices(sym):
    df = pd.read_parquet(D / f"px_{sym.replace('.', '_')}.parquet")
    df["date"] = pd.to_datetime(df["date"])
    return df

@st.cache_data
def fields(sym):
    df = pd.read_parquet(D / "case_fields.parquet")
    df = df[df.symbol == sym].drop(columns="symbol")
    from common import CASES
    import v4_overlay
    return v4_overlay.fields_filter(df, sym, CASES.get(sym, {}))

# ---------------------------------------------------------------- Formatierung (de-DE, ein Helfer je Art)
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"

def _de(x, d):
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def _ok(x):
    return x is not None and x == x

def fnum(x, d=2):
    """Zahl: 1.044,12"""
    return _de(x, d) if _ok(x) else "–"

def fprice(x, cur="USD", d=2):
    """Kurs/Preis: 709,33 USD"""
    return f"{_de(x, d)} {cur}" if _ok(x) else "–"

def fpct(x, d=1, sign=False):
    """Prozent aus Anteil: 0.134 -> 13,4 % (sign=True -> +13,4 %)"""
    if not _ok(x): return "–"
    v = x * 100
    s = _de(abs(v), d)
    return (("+" if v > 0 else "−" if v < 0 else "±") + s if sign else ("−" + s if v < 0 else s)) + " %"

def fpp(x, d=2, sign=True):
    """Prozentpunkte"""
    if not _ok(x): return "–"
    return ("+" if x > 0 else "−" if x < 0 else "") + _de(abs(x), d) + " Pp."

def fmult(x, d=1):
    """Multiple: 21,3×"""
    return f"{_de(x, d)}×" if _ok(x) else "–"

def fbig(x, cur="USD"):
    """Große Beträge: 1,82 Bio. USD / 228,25 Mrd. USD / 512,30 Mio. USD"""
    if not _ok(x): return "–"
    a = abs(x); sg = "−" if x < 0 else ""
    for lim, unit in ((1e12, "Bio."), (1e9, "Mrd."), (1e6, "Mio.")):
        if a >= lim: return f"{sg}{_de(a / lim, 2)} {unit} {cur}".strip()
    return f"{sg}{_de(a, 0)} {cur}".strip()

def fpctl(x):
    """Perzentil 0–100: 96,9"""
    return _de(x, 1) if _ok(x) else "–"

def fdate(s):
    """2026-10-21 -> 21.10.2026"""
    if not s: return "–"
    return pd.Timestamp(s).strftime("%d.%m.%Y")

# Kompatibilität mit älterem Code
def de(x, d=2): return fnum(x, d)
def pct(x, d=1, sign=True): return fpct(x, d, sign)

_NUM = re.compile(r"(?<![\w.])(-?)(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?(?=\s?%|\b)")
def de_text(t):
    """Zahlen im Fließtext auf deutsches Format bringen (1,341.83 -> 1.341,83; 20.0% -> 20,0 %)."""
    if not t: return t or ""
    def rep(m):
        sign, whole, frac = m.group(1), m.group(2).replace(",", "."), m.group(3)
        if len(whole) == 4 and not frac and whole.startswith(("19", "20")): return m.group(0)   # Jahreszahl
        return (("−" if sign else "") + whole + ("," + frac if frac else ""))
    t = re.sub(r"(\d)%", r"\1 %", t)
    return _NUM.sub(rep, t)

# ---------------------------------------------------------------- Interne Begriffe -> Klartext
TYPE_DE = {"CapexMega": "Tech-Konzern mit hohen Investitionen", "Plattform": "Plattform", "Halbleiter": "Halbleiter",
           "Software": "Software", "REIT": "Immobilien (REIT)", "Versicherung": "Versicherung", "Bank": "Bank",
           "KonsumZyklisch": "Konsum (zyklisch)", "Konsum": "Konsum", "Industrie": "Industrie"}
SECTOR_DE = {"Communication Services": "Kommunikation", "Consumer Discretionary": "Zyklischer Konsum",
             "Information Technology": "Informationstechnologie", "Financials": "Finanzen", "Real Estate": "Immobilien",
             "Health Care": "Gesundheit", "Industrials": "Industrie", "Consumer Staples": "Basiskonsum",
             "Utilities": "Versorger", "Energy": "Energie", "Materials": "Grundstoffe"}
_RULES = [
    (r"Kaufzone bei ([\d.]+) \(([-\d.]+ %), Basis-Retest\)", r"Einstiegszone ab \1 (\2 vom Kurs, Rücktest der Ausbruchsbasis)"),
    (r"Kaufzone bei ([\d.]+)", r"Einstiegszone ab \1"),
    (r"Warten: Zahlen in (\d+) Handelstagen \(([\d-]+)\)", r"Warten: Quartalszahlen in \1 Handelstagen (\2)"),
    (r"⚠ Zahlen in \d+ Handelstagen \([\d-]+\)", ""),
    (r"OCF enthält Zuflüsse aus Kunden-/Kartengeldern \(Funds payable to customers ([\d.]+) Mrd; Amounts payable due to credit and debit card transactions ([\d.]+) Mrd, letztes GJ\) → FCF kein Eigentümer-Cashflow; OCF ohne diese ≈ ([\d.]+) Mrd statt ([\d.]+) Mrd \([^)]*\)",
     r"Operativer Cashflow enthält Kundengelder (\1 Mrd. Kundeneinlagen, \2 Mrd. Kartenverbindlichkeiten): bereinigt ≈ \3 Mrd. statt \4 Mrd."),
    (r"FCF \(normalisiert, nach SBC\)", "Free Cashflow (normalisiert, nach Aktienvergütung)"),
    (r"Konsens-Umsatz FY2/FY1", "Konsens-Umsatzwachstum nächstes ggü. laufendem Geschäftsjahr"),
    (r"; r ([\d.]+%)", r"; Kapitalkosten \1"), (r", r ([\d.]+%)", r", Kapitalkosten \1"), (r"r\+2 Pp\.", "Kapitalkosten + 2 Pp."),
    (r"Konsens-NTM-EPS", "Konsens-Gewinn je Aktie (nächste 12 Monate)"), (r"NTM-EPS", "Konsens-Gewinn je Aktie (nächste 12 Monate)"),
    (r"Peer-Fwd-KGV", "Forward-KGV der Vergleichsfirmen"), (r"Peer-Median", "Median der Vergleichsfirmen"), (r"\(n=(\d+)\)", r"(\1 Firmen)"),
    (r"unser EPS", "eigener Gewinn je Aktie"), (r"eigenes Median-KGV", "eigenes historisches Median-KGV"),
    (r"½ DCF ([\d,.]+) \+ ½ Relativ-Ø ([\d,.]+)", r"½ DCF-Wert \1 + ½ Durchschnitt der Relativbewertungen \2"),
    (r"Ø\(Hist-KGV × EPS, Hist-KUV × Umsatz/Aktie\) × Wachstumsanpassung ([\d.]+) \(\(1\+g1\)/\(1\+CAGR3\)\)",
     r"Ø aus (historisches KGV × Gewinn je Aktie) und (historisches KUV × Umsatz je Aktie) × Wachstumsanpassung \1 (erwartetes ggü. 3-Jahres-Wachstum)"),
    (r"fairer KGV = Wachstum ([\d.]+) \+ Div\.-Rendite ([\d.]+) = ([\d.]+) × EPS ([\d.]+)", r"faires KGV = Wachstum \1 + Dividendenrendite \2 = \3, × Gewinn je Aktie \4"),
    (r"nicht geeignet \(nur Value/Asset-heavy \(KBV < 3, Fin, Zykliker\)\)", "nicht anwendbar (nur für Substanzwerte: KBV < 3, Finanzwerte, Zykliker)"),
    (r"nicht geeignet \(kein Dividenden-/Versorger-/REIT-Titel \(Rendite < 2,5 %\)\)", "nicht anwendbar (kein Dividendenwert, Rendite < 2,5 %)"),
    (r"nicht geeignet \(keine Dividende\)", "nicht anwendbar (keine Dividende)"),
    (r"nicht geeignet \(nur Wachstumswerte \(g ≥ 10 %\), keine Zykliker/Finanzwerte\)", "nicht anwendbar (nur Wachstumswerte mit ≥ 10 % Wachstum, keine Zykliker/Finanzwerte)"),
    (r"nicht geeignet \(DCF oder Relativwert fehlt\)", "nicht anwendbar (DCF- oder Relativwert fehlt)"),
    (r"verborgen/fehlt oder kein Peer-KGV", "nicht vergleichbar oder kein KGV der Vergleichsfirmen"),
    (r"⚠ ([\d.]+)× Kurs außerhalb 0,2–5× – Eingaben prüfen", r"Hinweis: Wert = \1× Kurs, außerhalb der Plausibilitätsspanne 0,2–5× (nicht im Median)"),
    (r"√\(22,5 × EPS ([\d.]+) × Buchwert/Aktie ([\d.]+)\)", r"√(22,5 × Gewinn je Aktie \1 × Buchwert je Aktie \2)"),
    (r"EPS ([\d.]+) × \(8,5 \+ 2×15\) × 4,4 / Y ([\d.]+) \(Y = 10J-UST \+ 1 Pp\. als AAA-Proxy\)",
     r"Gewinn je Aktie \1 × (8,5 + 2 × 15) × 4,4 / Anleihezins \2 (10-jährige US-Staatsanleihe + 1 Pp.)"),
    (r"EBITDA ([\d.]+) Mrd ×", r"EBITDA \1 Mrd. ×"),
    (r"Basis-Retest", "Rücktest der Ausbruchsbasis"), (r"Support-Zone \(v3\)", "Unterstützungszone"),
    (r"Trend-Pullback SMA(\d+)", r"Rücksetzer an die \1-Tage-Linie"),
    (r"kein Stage 2: Abwärtsstruktur trotz steigender 30W", "keine Aufwärtsphase: tiefere Hochs und Tiefs trotz steigender 30-Wochen-Linie"),
    (r"kein Stage 2: Kurs unter 30W", "keine Aufwärtsphase: Kurs unter der 30-Wochen-Linie"),
    (r"kein Stage 2: 30W-Steigung Zone gelb \(z [^)]*\) – nicht grün", "keine klare Aufwärtsphase: 30-Wochen-Linie steigt nur schwach"),
    (r"Stage 2 \(30W steigt, keine Abwärtsstruktur\)", "Aufwärtsphase: 30-Wochen-Linie steigt, keine Abwärtsstruktur"),
    (r"FCF_norm-Marge \(OCF − Erhaltungs-Capex − SBC\)", "Normalisierte Free-Cashflow-Marge (op. Cashflow − Erhaltungsinvestitionen − Aktienvergütung)"),
    (r"ROIC \(FCF_norm-Basis, ex GW\)", "Kapitalrendite (ROIC, auf Basis normalisierter Free Cashflow, ohne Goodwill)"),
    (r"ROIC ex GW Zyklusmittel \(7 J\.\)", "Kapitalrendite (ROIC ohne Goodwill, Ø über 7 Jahre)"),
    (r"ROIC ex GW", "Kapitalrendite (ROIC ohne Goodwill)"),
    (r"Nettoschulden÷FCF_norm", "Nettoschulden / normalisierter FCF"), (r"ND/FCF_norm", "Nettoschulden/FCF"),
    (r"FCF_norm", "normalisierter FCF"),
    (r"Bereinigter Nettogewinn TTM > 0", "Bereinigter Nettogewinn (12 Monate) positiv"),
    (r"Netto-Aktienzahl 3J-CAGR", "Veränderung der Aktienzahl p. a. (3 Jahre)"),
    (r"SBC/Umsatz", "Aktienvergütung / Umsatz"),
    (r"Bereinigung GAAP→bereinigt", "Anteil der Gewinnbereinigungen (GAAP → bereinigt)"),
    (r"Accruals \(NI−OCF\)/Bilanzsumme", "Bilanzielle Abgrenzungen (Gewinn − op. Cashflow) / Bilanzsumme"),
    (r"These-Risiko \(qualitativ/manuell\)", "Geschäftsrisiko (qualitativ geprüft)"),
    (r"≥ p80 Referenz", "≥ 80. Perzentil der Vergleichsgruppe"),
    (r"Composite p(\d+) im Typ \(Universum\)", r"Qualitäts-Gesamtscore Perzentil \1 (Vergleich: alle Aktien)"),
    (r"Composite p(\d+) im Typ \(([^)]+)\)", r"Qualitäts-Gesamtscore Perzentil \1 (Vergleich: \2)"),
    (r"Composite p(\d+)", r"Qualitätsscore Perzentil \1"),
    (r"Impl\. Wachstum als Base-Rate-Perzentil rot", "das im Kurs eingepreiste Wachstum haben historisch nur wenige Firmen geschafft"),
    (r"Basis-CAGR 5 J\. rot", "Basis-Rendite über 5 Jahre zu niedrig"),
    (r"Konservativ \(p25\) CAGR 5 J\. rot", "konservative Rendite über 5 Jahre zu niedrig"),
    (r"Trendbestätigung fehlt \(Kurs < 30W\)", "Trendbestätigung fehlt (Kurs unter der 30-Wochen-Linie)"),
    (r"Gate: Basis ([\d.]+ %) > 18 % \(Wertfalle/Datenfehler prüfen\)", r"Prüfhinweis: Basis-Rendite \1 ist ungewöhnlich hoch (Wertfalle/Datenfehler ausschließen)"),
    (r"Basis-Retest", "erneuter Test der Ausbruchsbasis"),
    (r"Ausbauphase \(Capex-Spitze\): FCF-Basis gedrückt \(Capex ([\d.]+)× D&A; FCF ([\d.]+ %) vs\. Kontrolle ([\d.]+ %) Umsatz\)",
     r"Investitionsphase: Free Cashflow vorübergehend gedrückt (Investitionen \1× Abschreibungen; FCF-Marge \2 statt \3)"),
    (r"Marktampel gelb → ½ Größe", "Gesamtmarkt neutral (gelb) → halbe Positionsgröße"),
    (r"Sektor (.+?) schwach \(Rang [\d.]+\) → ½ Größe", r"Sektor \1 relativ schwach → halbe Positionsgröße"),
    (r"Basis ([\d.]+ %)", r"Basis-Rendite \1"),
    (r"Basis-CAGR 5 J\.", "Basis-Rendite p. a. (5 Jahre)"),
    (r"Konservativ \(p25\) CAGR 5 J\.", "Konservative Rendite p. a. (5 Jahre)"),
    (r"Impl\. Wachstum als Base-Rate-Perzentil", "Eingepreistes Wachstum: wie selten historisch erreicht (Perzentil)"),
    (r"Renditequelle \(Multiple-Anteil / Gewinn je Aktie p\. a\.\)", "Renditequelle: Anteil aus Bewertungsänderung vs. Gewinnwachstum"),
    (r"impl\. Umsatz-CAGR", "eingepreistes Umsatzwachstum p. a."),
    (r"Konsens \(PIT-Snapshot\), GJ-Basis", "Analystenkonsens (Stichtags-Snapshot), Basis Geschäftsjahr"),
    (r"Gewinn/Aktie ([+\-\d.]+ %) p\. a\.", r"Gewinn je Aktie \1 p. a."),
    (r"\(Spanne 0–7\)", ""),
    (r"\bTTM\b", "12 Monate"), (r"\bSBC\b", "Aktienvergütung"), (r"\bOCF\b", "operativer Cashflow"),
    (r"Spanne ([\d.]+)…([\d.]+) Mrd", r"Spanne \1–\2 Mrd"),
    (r"g1 ([\d.]+%) 5 J\., Fade 15 J\. → ([\d.]+%) \(ROIC > r\+2 Pp\. in (\d+)% von 7 J\.\)",
     r"Wachstum Phase 1 \1 für 5 Jahre, danach 15 Jahre Angleichung → \2 (ROIC lag in \3 % der letzten 7 Jahre über Kapitalkosten + 2 Pp.)"),
    (r"g1 ≈", "Wachstum Phase 1 ≈"), (r"\bg1\b", "Wachstum Phase 1"),
    (r"J\. 6–10 → ", "Jahre 6–10 → "), (r"(\d) J\.", r"\1 Jahre"), (r"(\d) Mrd(?!\.)", r"\1 Mrd."),
    (r"Basis-CAGR 5 Jahre rot", "Basis-Rendite über 5 Jahre zu niedrig"),
    (r"Konservativ \(p25\) CAGR 5 Jahre rot", "konservative Rendite über 5 Jahre zu niedrig"),
    (r"Fade 15 Jahre → ", "danach 15 Jahre Angleichung auf "),
    (r"\(ROIC > Kapitalkosten \+ 2 Pp\. in (\d+)% von 7 Jahre\)", r"(ROIC in \1 % der letzten 7 Jahre über Kapitalkosten + 2 Pp.)"),
    (r"% 5 Jahre,", "% für 5 Jahre,"), (r"% 5 Jahre;", "% für 5 Jahre;"), (r"\) 5 Jahre,", ") für 5 Jahre,"),
    (r"Qualitäts-Gesamtscore Perzentil (\d+) \(Vergleich: ([^)]+)\)\)", r"Qualitätsscore Perzentil \1 im Vergleich \2)"),
]
_RULES = [(re.compile(a), b) for a, b in _RULES]

def plain(t):
    if not t: return t or ""
    for rx, rep in _RULES: t = rx.sub(rep, t)
    t = re.sub(r"\s*·\s*$", "", re.sub(r"(\s*·\s*)+", " · ", t)).replace("⚠", "").strip(" ·")
    t = de_text(re.sub(r"\s{2,}", " ", t))
    return re.sub(r"\b(\d{4})-(\d{2})-(\d{2})\b", r"\3.\2.\1", t)

def dedupe(t):
    seen, out = [], []
    for part in (t or "").split(" · "):
        key = part.replace("⚠", "").strip()
        if key and not any(key in x or x in key for x in seen):
            seen.append(key); out.append(part)
    return " · ".join(out)

def type_de(t): return TYPE_DE.get(t, t)
def sector_de(s): return SECTOR_DE.get(s, s)

CAT_STYLE = [("Kaufbereit", "#ecfdf3", "#067647"), ("nahe Kaufzone", "#ecfdf3", "#067647"), ("Warten", "#fffaeb", "#b54708"),
             ("Halten", "#eff4ff", "#1849a9"), ("zu teuer", "#fef3f2", "#b42318"), ("Qualität nein", "#fef3f2", "#b42318")]
def cat_style(cat):
    for k, bg, fg in CAT_STYLE:
        if cat.startswith(k): return bg, fg
    return "#f2f4f7", "#475467"

CAT_DE = {"nahe Kaufzone": "nahe Einstiegszone", "Qualität nein": "Qualität nicht erfüllt"}
def badge(cat):
    bg, fg = cat_style(cat)
    for k, v in CAT_DE.items(): cat = cat.replace(k, v)
    cat = cat[:1].upper() + cat[1:]
    return f'<span class="badge" style="background:{bg};color:{fg};border-color:{fg}33">{cat}</span>'

AMPEL_COL = {"grün": "#12b76a", "gelb": "#f79009", "rot": "#f04438", "pass": "#12b76a", "fail": "#f04438", "info": "#98a2b3"}
def dot(state):
    return f'<span class="dot" style="background:{AMPEL_COL.get(state, "#d0d5dd")}"></span>'

def table(rows, cols, align=None, cls=""):
    """Statische, nicht editierbare HTML-Tabelle. align: dict col->'r'."""
    align = align or {}
    th = "".join(f'<th class="{"r" if align.get(c) == "r" else ""}">{c}</th>' for c in cols)
    tr = "".join("<tr>" + "".join(f'<td class="{"r" if align.get(c) == "r" else ""}">{r.get(c, "")}</td>' for c in cols) + "</tr>" for r in rows)
    return f'<div class="tblwrap {cls}"><table class="tbl"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'

def stat(label, value, sub=None, tone=None):
    col = {"pos": "#067647", "neg": "#b42318"}.get(tone, "#101828")
    return (f'<div class="stat"><div class="l">{label}</div><div class="v" style="color:{col}">{value}</div>'
            + (f'<div class="s">{sub}</div>' if sub else "") + "</div>")

def strip(items):
    st.markdown(f'<div class="strip" style="grid-template-columns:repeat({len(items)},minmax(0,1fr))">' + "".join(stat(*i) for i in items) + "</div>", unsafe_allow_html=True)

def section(title, sub=None):
    st.markdown(f'<div class="sec"><h3>{title}</h3>' + (f'<p>{sub}</p>' if sub else "") + "</div>", unsafe_allow_html=True)

def card(html, cls=""):
    st.markdown(f'<div class="card {cls}">{html}</div>', unsafe_allow_html=True)

EXCHANGE = {"META": "NASDAQ", "MELI": "NASDAQ", "GOOGL": "NASDAQ", "AMZN": "NASDAQ", "NVDA": "NASDAQ"}

# Hover-Werte ja, aber nichts zieh- oder zoombar: kein Drag, keine Achsen-Griffe, kein Doppelklick-Zoom, feste Achsen, keine Werkzeugleiste
PLOT_CFG = {"staticPlot": False, "displayModeBar": False, "scrollZoom": False, "doubleClick": False, "showAxisDragHandles": False, "showTips": False, "responsive": True}
def plot_layout(**kw):
    base = dict(plot_bgcolor="#ffffff", paper_bgcolor="#ffffff", font=dict(family=FONT, size=13, color="#344054"),
                margin=dict(l=8, r=8, t=36, b=8), dragmode=False, hovermode="closest", separators=",.",
                hoverlabel=dict(bgcolor="#ffffff", bordercolor="#d0d7e2", font=dict(family=FONT, size=13, color="#1d2939")))
    base.update(kw)
    for ax in ("xaxis", "yaxis", "xaxis2", "yaxis2"):   # nur vorhandene Achsen ergänzen, damit Aufrufer weiter eigene Achsen-Argumente übergeben können
        if ax in base: base[ax] = {"fixedrange": True, **(base[ax] or {})}
    return base

CSS = """<style>
:root{--ink:#1d2939;--ink2:#344054;--muted:#5d6b7e;--line:#e3e8ef;--line2:#d0d7e2;--blue:#337ab7;--blue2:#2a6496;--card:#f4f8fb;
      --pos:#1e7b45;--posbg:#e3f4ea;--neg:#c0322b;--negbg:#fbe9e7;--bg:#ffffff}
html, body, [class*="css"], .stApp, .stMarkdown, button, input, select, textarea, [data-baseweb]{font-family:FONTSTACK !important}
[data-testid="stIconMaterial"], span[class*="material-symbols"]{font-family:"Material Symbols Rounded" !important}
.stApp{background:#fff;-webkit-user-select:none;user-select:none}
header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"], #MainMenu, footer{display:none !important}
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stSidebarCollapseButton"]{display:none !important}
.block-container{max-width:1200px;padding:0 24px 3rem !important}
[data-testid="stMainBlockContainer"]{padding-top:0 !important}
[data-testid="stVerticalBlock"]{gap:.75rem}
h1,h2,h3{font-family:FONTSTACK !important;color:var(--ink);letter-spacing:-.01em}
p, li, .stMarkdown{font-size:15px;color:var(--ink2);line-height:1.6}
img, svg, canvas, a{-webkit-user-drag:none;user-drag:none}
[data-testid="stHeaderActionElements"], h1 a, h2 a, h3 a{display:none !important}
a{color:var(--blue)}
/* Marktleiste */
.mstrip{display:flex;justify-content:space-between;gap:0;overflow:hidden;border-bottom:1px solid var(--line);background:#fafbfd;margin:0 -24px;padding:0 24px;white-space:nowrap}
.mstrip .it{display:flex;align-items:center;gap:5px;padding:7px 8px 7px 0;margin-right:8px;border-right:1px solid var(--line);font-size:12px;color:var(--ink2);font-variant-numeric:tabular-nums}
.mstrip .it:last-child{border-right:none} .mstrip a.it{text-decoration:none;color:var(--ink2);cursor:pointer} .mstrip a.it:hover b{color:#337ab7;text-decoration:underline}
.mstrip .it b{font-weight:600;color:var(--ink)} .mstrip .pill{font-size:11.5px;padding:1px 6px} .mstrip .it .n{color:var(--muted);font-weight:500}
.mstrip .asof{margin-left:auto;font-size:12px;color:var(--muted);align-self:center}
/* Kopfzeile */
.st-key-topnav{border-bottom:1px solid var(--line);margin:0 -24px;padding:10px 24px !important;background:#fff}
.st-key-topnav [data-testid="stPageLink"] a{padding:6px 12px;border-radius:6px;background:transparent}
.st-key-topnav [data-testid="stPageLink"] a:hover{background:#f2f5f9}
.st-key-topnav [data-testid="stPageLink"] p{font-size:15px;font-weight:500;color:var(--ink2) !important}
.st-key-topnav [class*="st-key-nav_on"] [data-testid="stPageLink"] p{color:var(--blue) !important;font-weight:600}
.st-key-topnav [class*="st-key-nav_sec"] [data-testid="stPageLink"] p{font-size:14px;color:var(--muted) !important}
.st-key-topnav .st-key-nav_sec_on [data-testid="stPageLink"] p{color:var(--blue) !important;font-weight:600}
.logo{display:flex;align-items:center;gap:9px;font-size:19px;font-weight:700;color:var(--ink);white-space:nowrap;margin-right:18px}
.logo i{display:inline-flex;width:28px;height:28px;border-radius:7px;background:var(--blue);color:#fff;font-style:normal;font-size:14px;align-items:center;justify-content:center;font-weight:700}
.logo span{color:var(--ink)}
.st-key-topnav [data-testid="stSelectbox"] [data-baseweb="select"] > div{min-height:36px;border-radius:6px;border-color:var(--line2);background:#fff;font-size:14px}
/* Aktienkopf */
.shead{padding:18px 0 4px}
.shead .nm{display:flex;align-items:center;gap:12px;font-size:26px;font-weight:700;color:var(--ink);line-height:1.2}
.mono{display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:8px;background:var(--card);border:1px solid var(--line);color:var(--blue);font-size:13px;font-weight:700}
.shead .pxrow{display:flex;align-items:center;gap:14px;margin-top:12px}
.shead .px{font-size:34px;font-weight:700;color:var(--ink);font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.shead .px small{font-size:20px;font-weight:600;margin-left:4px}
.shead .sub{font-size:12.5px;color:var(--muted);margin-top:4px}
.pill{display:inline-flex;align-items:center;gap:4px;border-radius:5px;padding:2px 8px;font-weight:600;font-size:13px;font-variant-numeric:tabular-nums;white-space:nowrap}
.pill.pos{background:var(--posbg);color:var(--pos)} .pill.neg{background:var(--negbg);color:var(--neg)} .pill.neu{background:#eef2f6;color:var(--ink2)}
.pill.big{font-size:17px;padding:4px 10px}
.mgrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:4px 36px;margin:16px 0 6px;font-size:13.5px}
.mgrid div{display:grid;grid-template-columns:110px 1fr;color:var(--ink2)} .mgrid span{color:var(--muted)} .mgrid b{font-weight:500;color:var(--blue)}
.r52{display:block;position:relative;height:4px;background:#e3e8ef;border-radius:2px;margin:5px 0 2px;width:150px}.r52 i{position:absolute;top:-3px;width:3px;height:10px;background:#337ab7;border-radius:1px}
.perf2{display:inline-flex;gap:14px;margin-left:18px;font-size:12.5px;color:var(--muted);white-space:nowrap;font-variant-numeric:tabular-nums}
.perf2 b{font-weight:600;margin-left:3px} .perf2 b.up{color:var(--pos)} .perf2 b.dn{color:var(--neg)}
.inote{display:flex;justify-content:flex-end;align-items:center;gap:2px;margin:-2px 0 4px;font-size:12px;color:var(--muted)} .inote .il{margin-left:2px}
.inote .ii .tip{left:auto;right:-6px;transform:none}
.perf{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.ibox{background:#f4f8fb;border-radius:10px;padding:16px 22px;margin:6px 0}
.ibox .ib-r{display:flex;gap:16px;align-items:flex-start;padding:7px 0;font-size:14px;line-height:1.6;color:#344054} .ibox svg{flex:0 0 18px;margin-top:3px}
.ibox .pill{font-size:12px;padding:1px 7px;margin:0 2px}
.perf .p{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:5px 10px;font-size:12.5px;color:var(--muted);font-variant-numeric:tabular-nums}
.perf .p b{margin-left:6px}
/* Tab-Leiste */
.st-key-tabs{border-bottom:1px solid var(--line);margin-top:6px}
.st-key-tabs [data-testid="stButtonGroup"] [role="radiogroup"]{gap:18px !important;flex-wrap:nowrap}
.st-key-tabs [data-testid="stButtonGroup"] [role="radiogroup"] button{margin:0 !important}
.st-key-tabs button{background:transparent !important;border:none !important;border-bottom:2px solid transparent !important;border-radius:0 !important;padding:10px 12px !important;min-height:0 !important;box-shadow:none !important}
.st-key-tabs button p{font-size:14.5px !important;font-weight:600 !important;color:var(--ink) !important}
.st-key-tabs button[aria-checked="true"]{border-bottom-color:var(--blue) !important}
.st-key-tabs button[aria-checked="true"] p{color:var(--blue) !important}
.st-key-tabs button:hover p{color:var(--blue) !important}
/* Abschnitte, Karten */
.h2{font-size:20px;font-weight:700;color:var(--ink);margin:26px 0 4px;line-height:1.3}
.h2sub{font-size:13.5px;color:var(--muted);margin:0 0 10px}
.h3{font-size:15.5px;font-weight:700;color:var(--ink);margin:0 0 10px}
.card{background:#fff;border:1px solid var(--line);border-radius:8px;padding:16px 18px}
.card.soft{background:var(--card)}
.info{background:var(--card);border-radius:8px;padding:16px 20px;font-size:14.5px;color:var(--ink2);line-height:1.65}
.info ul{margin:.4rem 0 0;padding-left:1.1rem}.info li{font-size:14.5px;margin:2px 0}
.rt{display:grid;grid-template-columns:92px 1fr 52px;align-items:center;gap:10px;font-size:14px;margin:6px 0;color:var(--ink2)}
.rt .bar{height:12px;background:#e6eaf0;border-radius:6px;overflow:hidden}.rt .bar i{display:block;height:100%;border-radius:6px}
.rt b{text-align:right;font-variant-numeric:tabular-nums}
.kt{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums}
.kt, .kt tr, .kt td{border:none !important;background:transparent !important}
.kt td{padding:10px 2px;border-bottom:1px solid var(--line) !important;color:var(--ink2)} .kt tr:last-child td{border-bottom:none}
.kt td.r{text-align:right;font-weight:600;color:var(--ink)}
.kcards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.kc{background:var(--card);border-radius:8px;padding:14px 18px}
.kc .h3{margin-bottom:4px}
.kc .row{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #e1e8f0;font-size:14px;color:var(--ink2)}
.kc .row:last-child{border-bottom:none} .kc .row b{color:var(--ink);font-weight:600;font-variant-numeric:tabular-nums;white-space:nowrap;margin-left:10px}
.fig{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.fc{background:#fff;border:1px solid var(--line);border-radius:8px;padding:12px 14px}
.fc .l{font-size:12.5px;color:var(--muted)} .fc .v{font-size:19px;font-weight:700;color:var(--ink);margin-top:2px;font-variant-numeric:tabular-nums;white-space:nowrap}
.fc .s{font-size:12px;color:var(--muted);margin-top:2px;display:flex;justify-content:space-between;align-items:flex-end}
.ev{display:flex;gap:14px;align-items:center;padding:10px 0;border-bottom:1px solid var(--line)} .ev:last-child{border-bottom:none}
.ev .d{width:52px;height:52px;border-radius:8px;background:var(--card);border:1px solid var(--line);display:flex;flex-direction:column;align-items:center;justify-content:center;line-height:1.05}
.ev .d b{font-size:19px;color:var(--ink)} .ev .d span{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.ev .t{font-size:14.5px;color:var(--ink);font-weight:600} .ev .t span{display:block;font-weight:400;font-size:13px;color:var(--muted)}
/* Tabellen (aktien.guide-artig) */
.tblwrap{background:#fff;border:1px solid var(--line);border-radius:8px;overflow:auto}
.tblwrap.scroll{max-height:520px}
.tbl{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums}
.tbl th{position:sticky;top:0;background:#f7f9fc;color:var(--muted);font-weight:600;font-size:12.5px;text-align:left;padding:9px 12px;border-bottom:1px solid var(--line);white-space:nowrap}
.tbl td{padding:9px 12px;border-bottom:1px solid #edf1f5;color:var(--ink2);vertical-align:top}
.tbl tr:last-child td{border-bottom:none}
.tbl .r{text-align:right;white-space:nowrap}
.tbl td b{color:var(--ink)} .tbl td:first-child{white-space:nowrap}
.up{color:var(--pos);font-weight:600}.dn{color:var(--neg);font-weight:600}
[data-testid="stExpander"] details{border:1px solid var(--line) !important;border-radius:8px !important;background:#fff}
[data-testid="stExpander"] summary p{font-size:14.5px !important;font-weight:600 !important;color:var(--ink) !important}
/* Badges / Swing */
.badge{display:inline-block;font-size:12.5px;font-weight:600;padding:3px 9px;border-radius:5px;white-space:nowrap;vertical-align:middle}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:8px;vertical-align:middle}
.strip{display:grid;background:var(--card);border-radius:8px;margin:10px 0 4px}
.stat{padding:12px 16px;border-right:1px solid #e1e8f0}.stat:last-child{border-right:none}
.stat .l{font-size:12.5px;color:var(--muted)} .stat .v{font-size:18px;font-weight:700;margin-top:2px;font-variant-numeric:tabular-nums;white-space:nowrap}
.stat .s{font-size:12px;color:var(--muted);margin-top:1px}
.tcard .row{display:flex;justify-content:space-between;padding:8px 0;border-top:1px solid #e1e8f0;font-size:14px;color:var(--ink2)}
.tcard .row b{color:var(--ink);font-variant-numeric:tabular-nums;white-space:nowrap;margin-left:8px}
.tcard .tk{font-size:18px;font-weight:700;color:var(--ink)} .tcard .nm{font-size:13px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tcard .top{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px}
.muted{color:var(--muted);font-size:13.5px}
.tbl, .tbl tr, .tbl td, .tbl th{border-left:none !important;border-right:none !important}
.note{color:var(--muted);font-size:13px !important;margin-top:8px;line-height:1.55}
.ka{border-bottom:1px dotted #667085;cursor:help;color:var(--muted)}
.eyebrow{font-size:12px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--blue)}
.lead{font-size:15.5px;color:var(--ink2);max-width:860px;line-height:1.65;margin:.3rem 0 .8rem}
h1.ptitle{font-size:28px;font-weight:700;color:var(--ink);margin:18px 0 4px;padding:0;line-height:1.25}
.pipe{display:flex;gap:10px;align-items:stretch;margin:6px 0 4px}
.pipe .s{flex:1;background:var(--card);border-top:3px solid var(--blue);border-radius:8px;padding:12px}
.pipe .s b{display:block;color:var(--ink);font-size:14.5px}.pipe .s span{font-size:13px;color:var(--muted)}
.pipe .a{align-self:center;color:#98a2b3}
.sec{margin:24px 0 8px}.sec h3{font-size:18px !important;font-weight:700 !important;margin:0 !important;padding:0 !important}.sec p{margin:2px 0 0;font-size:13.5px;color:var(--muted)}
.kv{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));background:var(--card);border-radius:8px}
.kv div{padding:10px 14px;border-bottom:1px solid #e1e8f0}.kv span{display:block;font-size:12.5px;color:var(--muted)}.kv b{font-size:15px;color:var(--ink);font-weight:600}
.foot{display:flex;justify-content:space-between;gap:24px;color:var(--muted);font-size:12.5px;border-top:1px solid var(--line);margin-top:2.5rem;padding-top:14px;line-height:1.6}
.foot a{color:var(--ink2)}
/* Buttons / Widgets */
.stButton button{border-radius:6px;font-weight:600;border-color:var(--line2);min-height:36px}
.stButton button p, .stDownloadButton button p{font-size:14px !important;font-weight:600}
.stButton button[kind="primary"]{background:var(--blue);border-color:var(--blue)}
.stButton button[kind="primary"]:hover{background:var(--blue2);border-color:var(--blue2)}
.stButton button[kind="primary"] p, [data-testid="stFormSubmitButton"] button p{color:#fff !important}
[data-testid="stFormSubmitButton"] button{background:var(--blue);border-color:var(--blue)}
[data-testid="stButtonGroup"] button p{font-size:13.5px !important}
[data-testid="stButtonGroup"] button[aria-checked="true"]{background:#eaf2fa;border-color:#9cc0e2;color:var(--blue)}
[data-testid="stButtonGroup"] button[aria-checked="true"] p{color:var(--blue2) !important}
iframe{border:none}
@media (max-width:640px){.st-key-topnav{flex-wrap:wrap !important;row-gap:4px !important;margin:0 -16px !important;padding:8px 12px !important}
.st-key-topnav > div:first-child{width:100%}
.st-key-topnav [data-testid="stPageLink"] a{padding:4px 6px}.st-key-topnav [data-testid="stPageLink"] p{font-size:14px !important}
.st-key-topnav [class*="st-key-hidesearch"]{width:100% !important;order:9}.st-key-topnav [class*="st-key-nav_sec"]{display:none}}
@media (max-width:640px){.mgrid{grid-template-columns:1fr;gap:2px 0}.mgrid div{grid-template-columns:120px minmax(0,1fr);word-break:normal;overflow-wrap:anywhere}
.perf2{display:flex;flex-wrap:wrap;gap:4px 12px;margin-left:0;white-space:normal}
.st-key-tabs [data-testid="stButtonGroup"]{overflow-x:auto;-webkit-overflow-scrolling:touch}.st-key-tabs [data-testid="stButtonGroup"] [role="radiogroup"]{gap:4px !important;width:max-content}
.st-key-tabs button p{white-space:nowrap !important;overflow:visible !important;text-overflow:clip !important}
.pstrip,.sw-kpis,.steps,.csteps{grid-template-columns:1fr 1fr !important}.pstrip>div{border-right:none;border-bottom:1px solid var(--line)}
.tbl{display:block;overflow-x:auto}.agperf{flex-wrap:wrap !important;white-space:normal !important;row-gap:4px}
.pstrip .s,.pstrip .v,.sw-k .v{white-space:normal !important}.pstrip>div,.sw-k{min-width:0;overflow-wrap:anywhere}}
@media (max-width:1320px){.mgrid{gap:4px 20px}.mgrid div{grid-template-columns:96px 1fr}.fig{grid-template-columns:repeat(2,minmax(0,1fr))}.stat{padding:10px 12px}.stat .v{font-size:16px}}
</style>""".replace("FONTSTACK", FONT)

KA_NOTE = "k. A. = keine Angabe: Der Analystenkonsens rechnet mit einer anderen Gewinnbasis (GAAP statt bereinigt) als dieses System; der Wert wird deshalb bewusst ausgeblendet."
def ka(v, fmt):
    return fmt(v) if v is not None else f'<span class="ka" title="{KA_NOTE}">k. A.¹</span>'

def page_head(eyebrow, title=None, lead=None):
    """Einheitlicher Seitenkopf für alle Seiten: Rubrik, Titel, Einleitung."""
    st.markdown(f'<div class="eyebrow">{eyebrow}</div>' + (f'<h1 class="ptitle">{title}</h1>' if title else "")
                + (f'<p class="lead">{lead}</p>' if lead else ""), unsafe_allow_html=True)

def footer(meta):
    st.markdown(f'<div class="foot">Keine Anlageberatung. Das System gibt keine Orders. '
                f'Datenstand: Schlusskurse {fdate(meta["asof"])}. Quellen: SEC EDGAR (XBRL), Kurs- und Konsensdaten über öffentliche Schnittstellen. '
                f'Charts: <a href="https://www.tradingview.com/" target="_blank">TradingView</a> Lightweight Charts™ (Apache-2.0), Plotly.</div>',
                unsafe_allow_html=True)

def quote_header(c, px):
    last, prev = px.close.iloc[-1], px.close.iloc[-2]
    ch = last - prev; chp = ch / prev
    col = "#067647" if ch >= 0 else "#b42318"
    sg = "+" if ch >= 0 else "−"
    y = px.tail(252); lo52, hi52 = y.low.min(), y.high.max()
    pos = (last - lo52) / (hi52 - lo52) * 100 if hi52 > lo52 else 50
    def perf(n):
        if len(px) <= n: return "–"
        r = last / px.close.iloc[-1 - n] - 1
        return f'<b style="color:{"#067647" if r >= 0 else "#b42318"}">{fpct(r, 1, True)}</b>'
    st.markdown(f'<div class="qhead"><div><div class="tk">{EXCHANGE.get(c["symbol"], "")}: {c["symbol"]}</div>'
                f'<div class="nm">{c["name"]} &nbsp;{badge(c["category"])}</div>'
                f'<div class="meta">{sector_de(c["sector"])} · {INDUSTRY_DE.get(c["industry"], c["industry"])} · {type_de(c["type"])}</div>'
                f'<div class="perf"><span>1 Woche {perf(5)}</span><span>1 Monat {perf(21)}</span><span>3 Monate {perf(63)}</span><span>1 Jahr {perf(252)}</span></div></div>'
                f'<div class="qright"><div class="px">{fnum(c["price"])}<small>{c["currency"]}</small></div>'
                f'<div class="chg" style="color:{col}">{sg}{fnum(abs(ch))} ({fpct(chp, 2, True)}) Vortag</div>'
                f'<div class="asof">Schlusskurs {fdate(c["asof"])}</div>'
                f'<div class="r52"><div class="lab"><span>52 Wochen: {fnum(lo52)}</span><span>{fnum(hi52)}</span></div>'
                f'<div class="bar"><i style="left:{pos:.1f}%"></i></div></div></div></div>', unsafe_allow_html=True)

def kpi(col, value, label):
    col.markdown(f'<div class="card">{stat(label, value)}</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- v3: Bausteine im aktien.guide-Stil
POS, NEG, BLUE_AG = "#1e7b45", "#c0322b", "#337ab7"

@st.cache_resource   # nur lesen; vermeidet Kopie je Aufruf (Vollpool)
def load_v3():
    return json.loads((D / "market.json").read_text()), json.loads((D / "consensus.json").read_text())

@st.cache_data
def prices_long(sym):
    df = pd.read_parquet(D / f"pxl_{sym}.parquet"); df["date"] = pd.to_datetime(df["date"]); return df

def pill(x, d=2, big=False, txt=None):
    """Veränderungs-Pille: grün/rot mit Pfeil."""
    if not _ok(x): return '<span class="pill neu">k. A.</span>'
    cls = "pos" if x > 0 else "neg" if x < 0 else "neu"
    arr = "↑" if x > 0 else "↓" if x < 0 else ""
    return f'<span class="pill {cls}{" big" if big else ""}">{arr} {txt or fpct(abs(x), d)}</span>'

def arrow(x, d=1):
    """Farbiger Änderungswert für Tabellen."""
    if not _ok(x): return "–"
    return f'<span class="{"up" if x > 0 else "dn" if x < 0 else ""}">{"↑" if x > 0 else "↓" if x < 0 else ""} {fpct(x, d, True)}</span>'

def ii(text):
    """Info-Symbol mit kurzer Erklärung (Hover oder Tastatur-Fokus), ohne Widget."""
    return f'<span class="ii" tabindex="0" aria-label="Erklärung">i<span class="tip">{text}</span></span>'

def h2(title, sub=None, info=None):
    st.markdown(f'<div class="h2">{title}{ii(info) if info else ""}</div>' + (f'<div class="h2sub">{sub}</div>' if sub else ""), unsafe_allow_html=True)

def spark(vals, w=92, h=26, col=None):
    v = [x for x in vals if _ok(x)]
    if len(v) < 2: return ""
    lo, hi = min(v), max(v); rng = (hi - lo) or 1
    col = col or (POS if v[-1] >= v[0] else NEG)
    pts = " ".join(f"{i * w / (len(v) - 1):.1f},{h - 2 - (x - lo) / rng * (h - 4):.1f}" for i, x in enumerate(v))
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}"><polyline points="{pts}" fill="none" stroke="{col}" stroke-width="1.6" stroke-linejoin="round"/></svg>'

MKT_FMT = {"TNX": lambda v: fnum(v, 2) + " %", "EURUSD": lambda v: fnum(v, 4), "VIX": lambda v: fnum(v, 2)}
def market_strip():
    mk, _ = load_v3()
    items = []
    for m in mk:
        if m["last"] is None: continue   # keine Reihe im Datenbestand (DAX): nicht anzeigen statt "k. A."
        ch = m["last"] / m["prev"] - 1
        val = MKT_FMT.get(m["key"], lambda v: fnum(v, 2))(m["last"])
        items.append(f'<a class="it" href="/aktienanalyse?m={m["key"]}" target="_self" title="{m["sub"]} · Schluss {fdate(m["date"])}"><b>{m["name"]}</b><span>{val}</span>{pill(ch, 2)}</a>')
    d = next((m["date"] for m in mk if m.get("date")), None)
    st.markdown(f'<div class="mstrip">{"".join(items)}</div>', unsafe_allow_html=True)

from industry_de import INDUSTRY_DE

def stock_head(c, px, right_html=""):
    """Aktienkopf wie bei Finanzportalen: Name, großer Kurs + Pille, Stichtagszeile, Stammdaten-Raster. Ohne Urteil."""
    _, cons = load_v3(); k = cons.get(c["symbol"], {})
    last, prev = px.close.iloc[-1], px.close.iloc[-2]
    chp = last / prev - 1
    y = px.tail(252); lo52, hi52 = y.low.min(), y.high.max()
    def pv(x):
        return f'<b class="{"up" if x > 0 else "dn" if x < 0 else ""}">{fpct(x, 1, True)}</b>'
    def perf(n):
        return pv(last / px.close.iloc[-1 - n] - 1) if len(px) > n else "k. A."
    ytd = px[px.date.dt.year == px.date.iloc[-1].year].close.iloc[0]
    mono = c["symbol"][:2] if c["symbol"] != "GOOGL" else "GO"
    st.markdown(
        f'<div class="shead"><div style="display:flex;justify-content:space-between;align-items:flex-start;gap:24px"><div>'
        f'<div class="nm"><span class="mono">{mono}</span>{c["name"]}</div>'
        f'<div class="pxrow"><span class="px">{fnum(last)}<small>{c["currency"]}</small></span>{pill(chp, 2, big=True)}'
        f'<span class="perf2"><span>1 W {perf(5)}</span><span>1 M {perf(21)}</span><span>3 M {perf(63)}</span><span>lfd. J. {pv(last / ytd - 1)}</span><span>1 J {perf(252)}</span><span>3 J {perf(756)}</span></span></div>'
        f'<div class="sub">{k.get("exchange", "NASDAQ")}, Schlusskurs {fdate(str(px.date.iloc[-1])[:10])} · Vortag {fnum(prev)} {c["currency"]} · Datenstand point-in-time</div></div>'
        f'<div style="text-align:right">{right_html}</div></div>'
        f'<div class="mgrid"><div><span>Symbol</span>{c["symbol"]}</div><div><span>Index</span><b>{k.get("index") or "k. A."}</b></div>'
        f'<div><span>52 Wochen</span><span style="color:#1d2939">{fnum(lo52)} – {fnum(hi52)}<i class="r52"><i style="left:{(last - lo52) / (hi52 - lo52) * 100 if hi52 > lo52 else 50:.0f}%"></i></i></span></div>'
        f'<div><span>Börse</span>{k.get("exchange", "NASDAQ")}</div><div><span>Sektor</span><b>{sector_de(c["sector"])}</b></div>'
        f'<div><span>Börsenwert</span>{fbig(c["keystats"]["mcap"], c["currency"])}</div>'
        f'<div><span>Währung</span>{c["currency"]}</div><div><span>Industrie</span><b>{INDUSTRY_DE.get(c["industry"], c["industry"])}</b></div>'
        f'<div><span>Nächste Zahlen</span>{fdate(c["next_earnings"])}</div></div>'
        '</div>',
        unsafe_allow_html=True)

ICONS = {"chart": '<path d="M3 17l5-5 4 4 8-8" /><path d="M14 8h6v6" />', "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>',
         "alert": '<circle cx="12" cy="12" r="9"/><path d="M12 7v6M12 16.5v.5"/>', "pen": '<path d="M4 20h4L19 9l-4-4L4 16v4z"/>',
         "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>', "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/>',
         "shield": '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/>'}
def ibox(items):
    """Infokasten wie bei aktien.guide: Symbol links, kurzer Satz mit eingebetteten Pills."""
    row = lambda ic, t: (f'<div class="ib-r"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#337ab7" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{ICONS.get(ic, ICONS["info"])}</svg><div>{t}</div></div>')
    return '<div class="ibox">' + "".join(row(i, t) for i, t in items) + "</div>"

def inote(text, label="Erläuterung"):
    """Erläuterung nur als Info-Symbol (Hover/Fokus), nie als Fließtext unter Charts."""
    return f'<div class="inote"><span class="ii" tabindex="0" aria-label="{label}">i<span class="tip">{text}</span></span><span class="il">{label}</span></div>'

def hover_fix(fig):
    """Einheitliche Tooltips: fette Kopfzeile (Datum/Jahr), eine Zeile je Reihe 'Name: Wert', weißer Kasten mit Rahmen."""
    import re as _re
    for tr in fig.data:
        ht = getattr(tr, "hovertemplate", None)
        if not ht or "<b>" in ht: continue
        m = _re.match(r"^%\{(x|y)(\|[^}]*)?\}(: |<br>|\s·\s)(.*)$", ht, _re.S)
        if m:
            nm = tr.name or ""
            rest = m.group(4)
            ex = _re.search(r"<extra>(.*?)</extra>", rest)
            lab = (ex.group(1) if ex and ex.group(1) else nm)
            rest = _re.sub(r"<extra>.*?</extra>", "", rest)
            tr.hovertemplate = f"<b>%{{{m.group(1)}{m.group(2) or ''}}}</b><br>" + (f"{lab}: " if lab and not rest.startswith(lab) else "") + rest + "<extra></extra>"
        else:
            tr.hovertemplate = ht if ht.endswith("</extra>") else ht + "<extra></extra>"
    fig.update_layout(hoverlabel=dict(bgcolor="#ffffff", bordercolor="#d0d7e2", font=dict(family=FONT, size=13, color="#1d2939"), align="left"))
    return fig

def lock_fig(fig):
    """Kein Chart lässt sich verschieben oder zoomen: feste Achsen, kein Ziehen (Maus, Touch, Pinch)."""
    fig.update_layout(dragmode=False)
    fig.update_xaxes(fixedrange=True); fig.update_yaxes(fixedrange=True)
    return fig

def pad_right(fig, frac=0.07):
    """Rechts Luft nach dem letzten Datum, damit aktueller Kurs und Linien/Beschriftungen sichtbar bleiben."""
    import pandas as _pd
    xs = [x for tr in fig.data if getattr(tr, "x", None) is not None for x in tr.x]
    if not xs: return fig
    x = _pd.to_datetime(_pd.Series(xs)); lo, hi = x.min(), x.max()
    fig.update_xaxes(range=[lo, hi + (hi - lo) * frac]); return fig

LOCK_CFG = {"scrollZoom": False, "displayModeBar": False, "doubleClick": False, "showAxisDragHandles": False, "staticPlot": False}
def pchart(fig, **kw):
    kw["config"] = {**PLOT_CFG, **(kw.get("config") or {}), **LOCK_CFG}
    return st.plotly_chart(lock_fig(hover_fix(fig)), **kw)

def footer2(meta, about_link=True):
    st.markdown(f'<div class="foot"><div>Keine Anlageberatung. Das System gibt keine Orders.<br>'
                f'Datenstand: Schlusskurse {fdate(meta["asof"])}. Quellen: SEC EDGAR (XBRL), Kurs-, Makro- und Konsensdaten über öffentliche Schnittstellen.</div>'
                f'<div style="text-align:right;white-space:nowrap">Charts: <a href="https://www.tradingview.com/" target="_blank">TradingView</a> Lightweight Charts™, Plotly<br>'
                + ('<a href="/projekt" target="_self">Über das Projekt</a>' if about_link else "") + '</div></div>', unsafe_allow_html=True)

CSS = CSS.rsplit("</style>", 1)[0] + """
/* v3.1: Startseite */
.hero{text-align:center;padding:48px 0 22px}
.hero h1{font-size:38px;font-weight:750;letter-spacing:-.02em;color:var(--ink);margin:6px 0 12px;padding:0}
.hero p{font-size:17px;line-height:1.55;color:var(--ink2);max-width:680px;margin:0 auto}
.st-key-homesearch [data-baseweb=select]>div{min-height:52px;font-size:16px;border-radius:10px}
.entry{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:24px 26px 6px}
.entry .et{font-size:22px;font-weight:700;color:var(--ink);margin-bottom:6px}
.entry p{font-size:15px;color:var(--ink2);line-height:1.55;margin:0 0 8px} .entry ul{margin:0 0 4px 18px;padding:0;font-size:14px;color:var(--muted)}
[class*=st-key-entry_] [data-testid=stPageLink] a{font-weight:600;color:var(--blue)}
.tile{border:1px solid var(--line);border-radius:10px;padding:14px 16px 8px;background:#fff}
.tile .tk{font-size:17px;font-weight:700;color:var(--ink)} .tile .nm{font-size:13px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tile .pv{font-size:20px;font-weight:700;color:var(--ink);margin:10px 0 4px;font-variant-numeric:tabular-nums;white-space:nowrap} .tile .pv span{font-size:13px;font-weight:500}
.tile .sp svg{width:100%;height:44px;margin-top:8px}
.recruit{margin-top:44px;font-size:14px;color:var(--muted);border-top:1px solid var(--line);padding-top:16px}
a.logo{text-decoration:none!important}
/* v3.1: großzügige Kennzahlen */
.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin:4px 0 8px} .kpis.c3{grid-template-columns:repeat(3,minmax(0,1fr))}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px 20px}
.kpi .l{font-size:13px;color:var(--muted);font-weight:500} .kpi .v{font-size:28px;font-weight:700;color:var(--ink);margin:6px 0 4px;letter-spacing:-.01em;font-variant-numeric:tabular-nums;white-space:nowrap}
.kpi .v small{font-size:14px;font-weight:500;color:var(--muted)} .kpi .s{font-size:13px;color:var(--muted);display:flex;justify-content:space-between;align-items:flex-end;gap:8px}
.sec{font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:30px 0 10px}
/* v3.1: Bewertung Hero */
.vhero{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:24px 28px 20px;margin:6px 0 10px}
.vhero .top{display:flex;gap:48px;align-items:flex-end;flex-wrap:wrap}
.vhero .l{font-size:13px;color:var(--muted)} .vhero .big{font-size:40px;font-weight:750;color:var(--ink);letter-spacing:-.02em;font-variant-numeric:tabular-nums;white-space:nowrap}
.vhero .mid{font-size:22px;font-weight:650;color:var(--ink);font-variant-numeric:tabular-nums;white-space:nowrap}
.rbar{position:relative;height:64px;margin:26px 8px 0}
.rbar .track{position:absolute;top:26px;left:0;right:0;height:6px;background:#e3e9f0;border-radius:3px}
.rbar .span{position:absolute;top:22px;height:14px;background:#9cc0e2;border-radius:7px}
.rbar .iqr{position:absolute;top:22px;height:14px;background:#337ab7;border-radius:7px}
.rbar .mk{position:absolute;top:0;transform:translateX(-50%);font-size:12px;color:var(--ink);white-space:nowrap;text-align:center}
.rbar .mk i{display:block;width:2px;height:34px;margin:3px auto 0;background:var(--ink)}
.rbar .lab{position:absolute;top:44px;transform:translateX(-50%);font-size:12px;color:var(--muted);white-space:nowrap}
.assume{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));border:1px solid var(--line);border-radius:10px;overflow:hidden}
.assume>div{padding:16px 18px;border-right:1px solid var(--line)} .assume>div:last-child{border-right:none}
.assume .l{font-size:12.5px;color:var(--muted)} .assume .v{font-size:20px;font-weight:700;color:var(--ink);margin:4px 0 2px;white-space:nowrap} .assume .s{font-size:12px;color:var(--muted)}
</style>"""

CSS = CSS.rsplit("</style>", 1)[0] + """
.ii{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;border-radius:50%;border:1px solid #98a2b3;color:#5d6b7e;
 font-size:11px;font-weight:700;font-style:normal;margin-left:7px;cursor:help;position:relative;vertical-align:middle;line-height:1;letter-spacing:0;text-transform:none}
.ii .tip{display:none;position:absolute;left:50%;top:22px;transform:translateX(-50%);width:300px;background:#fff;border:1px solid #d0d7e2;border-radius:8px;
 box-shadow:0 6px 20px rgba(16,24,40,.12);padding:10px 12px;font-size:13px;font-weight:400;line-height:1.5;color:#344054;z-index:50;text-align:left;white-space:normal}
.ii:hover .tip,.ii:focus .tip{display:block}
.kpi,.vhero,.assume>div{overflow:visible}
</style>"""

CSS = CSS.rsplit("</style>", 1)[0] + """
[class*=st-key-entry_],[class*=st-key-tile_]{background:#fff;border:1px solid var(--line);border-radius:12px;gap:0!important;padding-bottom:12px}
[class*=st-key-entry_]{background:var(--card);padding-bottom:18px}
.entry,.tile{border:none!important;background:transparent!important}
[class*=st-key-entry_] [data-testid=stPageLink],[class*=st-key-tile_] [data-testid=stPageLink]{padding:0 16px}
[class*=st-key-entry_] [data-testid=stPageLink]{padding:0 26px}
[class*=st-key-tile_]:hover,[class*=st-key-entry_]:hover{border-color:#9cc0e2}
</style>"""

CSS = CSS.rsplit("</style>", 1)[0] + """
.atbl td{padding:12px 14px;font-size:14.5px;vertical-align:top} .atbl td b{font-size:17px;color:var(--ink)} .atbl th{font-size:12.5px}
</style>"""

CSS = CSS.rsplit("</style>", 1)[0] + """
.mcards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.mc{border:1px solid var(--line);border-radius:10px;padding:12px 14px;background:#fff}
.mc .n{font-size:13px;color:var(--muted);font-weight:600} .mc .v{font-size:19px;font-weight:700;color:var(--ink);margin:4px 0;font-variant-numeric:tabular-nums}
.mc .sp svg{width:100%;height:30px;margin-top:6px}
[class*=st-key-entry_] .entry{padding-bottom:14px}
[class*=st-key-entry_] [data-testid=stPageLink] a{display:inline-flex;border:1px solid #337ab7;border-radius:8px;height:36px;padding:0 16px;align-items:center;margin-top:4px;background:#fff}
[class*=st-key-entry_] [data-testid=stPageLink] a:hover{background:#eaf2fa}
.tile .sp{margin-bottom:12px}
.st-key-hidesearch_on{display:none}
</style>"""
