"""Gemeinsamer Zustand (Ticker, Modellauswahl) und Seitenverweise für beide Produktteile."""
import streamlit as st
from lib import load

META, CASES, VAL = load()
for _c in CASES.values():   # Jahre ohne Umsatz (Lücken im Vollimport) nicht als Datenpunkt zeigen
    _c["annual"] = [r for r in (_c.get("annual") or []) if r.get("revenue")]
import v4_overlay as _v4
_v4.apply(CASES)    # eine Quelle: Bewertung v4 + kursabhängige Felder auf den Snapshot-Kurs + Swing-Regeln v4
SYMS = list(CASES)
PAGES = {}          # wird in app.py befüllt: {"analyse": Page, "swing": Page, ...}
OVERVIEW = "Übersicht"

def current():
    """Die URL (?t=) ist die Quelle der Wahrheit: Neuladen, Zurück/Vor und Links behalten die Aktie."""
    t = st.query_params.get("t")
    st.session_state.ticker = t if t in CASES else None
    return st.session_state.ticker

def set_ticker(t):
    st.session_state.ticker = t if t in CASES else None
    if st.session_state.ticker: st.query_params["t"] = st.session_state.ticker
    elif "t" in st.query_params: del st.query_params["t"]

def ticker_bar(key):
    cur = current()
    st.session_state[key] = cur or OVERVIEW
    def _chg():
        v = st.session_state.get(key)
        set_ticker(None if v in (None, OVERVIEW) else v)
    st.selectbox("Aktie", [OVERVIEW] + SYMS, key=key, on_change=_chg, label_visibility="collapsed",
                 format_func=lambda s: s if s == OVERVIEW else label(s))
    return cur

# ---------------------------------------------------------------- Vollständiger Pool: Schnellwahl, Suche, Filter, "weitere 25"
FEATURED = [s for s in ("META", "MELI", "GOOGL", "AMZN", "NVDA") if s in CASES]
SUFFIX_LAND = {".DE": "Deutschland", ".HK": "Hongkong", ".PA": "Frankreich", ".MC": "Spanien", ".MI": "Italien", ".VI": "Österreich",
               ".AS": "Niederlande", ".L": "Großbritannien", ".SW": "Schweiz", ".CO": "Dänemark", ".ST": "Schweden"}
PAGE_N = 25

def label(s):
    c = CASES.get(s) or {}; return f"{(c.get('name') or s).split(' (')[0]} ({s})"

def land(s):
    return next((v for k, v in SUFFIX_LAND.items() if s.endswith(k)), "USA")

def quick_picks(page):
    """Die fünf Demo-Aktien als direkte Links (Schnellwahl über jeder Pool-Liste)."""
    url = PAGES[page].url_path
    st.markdown('<div class="qpick"><span>Schnellwahl</span>' + "".join(
        f'<a href="/{url}?t={s}" target="_self">{s}</a>' for s in FEATURED) + "</div>", unsafe_allow_html=True)

def pool_filter(rows, key, sym=lambda r: r, extra=None):
    """Suche (Symbol/Name) + Sektor + Land (+ optionaler Seitenfilter) über bereits sortierte Zeilen.
    Gibt (sichtbare Zeilen, Trefferzahl) zurück; danach more(key, n) für "Weitere 25 anzeigen"."""
    from lib import sector_de
    st.markdown("""<style>.qpick{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin:2px 0 10px;font-size:13px}
.qpick span{color:#5d6b7e;margin-right:4px}.qpick a{border:1px solid #d0d7e2;border-radius:999px;padding:3px 12px;color:#1d2939 !important;text-decoration:none;font-weight:600;background:#fff}
.qpick a:hover{border-color:#3d6fb6;color:#3d6fb6 !important}</style>""", unsafe_allow_html=True)
    secs = sorted({sector_de(CASES[sym(r)].get("sector")) for r in rows if CASES[sym(r)].get("sector")})
    lands = sorted({land(sym(r)) for r in rows}, key=lambda x: (x != "USA", x))
    cols = st.columns([2.2, 1.3, 1.1] + ([1.3] if extra else []), gap="small")
    q = cols[0].text_input("Suche", key=f"{key}_q", placeholder="Symbol oder Name", label_visibility="collapsed")
    sec = cols[1].selectbox("Sektor", ["Alle Sektoren"] + secs, key=f"{key}_sec", label_visibility="collapsed")
    ld = cols[2].selectbox("Land", ["Alle Länder"] + lands, key=f"{key}_land", label_visibility="collapsed")
    ex = None
    if extra:
        name, opts, fn = extra
        ex = cols[3].selectbox(name, [f"Alle ({name})"] + opts, key=f"{key}_ex", label_visibility="collapsed")
    sig = (q, sec, ld, ex)
    if st.session_state.get(f"{key}_sig") != sig: st.session_state[f"{key}_sig"] = sig; st.session_state[f"{key}_n"] = PAGE_N
    ql = (q or "").strip().lower()
    out = [r for r in rows
           if (not ql or ql in sym(r).lower() or ql in (CASES[sym(r)].get("name") or "").lower())
           and (sec == "Alle Sektoren" or sector_de(CASES[sym(r)].get("sector")) == sec)
           and (ld == "Alle Länder" or land(sym(r)) == ld)
           and (not extra or ex == f"Alle ({extra[0]})" or extra[2](r, ex))]
    n = st.session_state.get(f"{key}_n", PAGE_N)
    return out[:n], len(out)

def more(key, total):
    n = st.session_state.get(f"{key}_n", PAGE_N)
    if total > n:
        _, m, _ = st.columns([2, 1, 2])
        if m.button(f"Weitere {min(PAGE_N, total - n)} anzeigen", key=f"{key}_more", width="stretch"):
            st.session_state[f"{key}_n"] = n + PAGE_N; st.rerun()

def go(page, ticker=None):
    if ticker is not None: set_ticker(ticker)
    t = st.session_state.get("ticker")
    st.switch_page(PAGES[page], query_params={"t": t} if t else None)

def model_sel(key, options, default, hide=False):
    """Gemeinsame Modellauswahl (Aktienanalyse <-> Swing-Tool)."""
    if "msel" not in st.session_state: st.session_state.msel = list(default)
    st.session_state[key] = [m for m in st.session_state.msel if m in options]
    def _chg(): st.session_state.msel = list(st.session_state.get(key) or [])
    st.pills("Bewertungsmodelle", options, selection_mode="multi", key=key, on_change=_chg, label_visibility="collapsed" if hide else "visible")
    return st.session_state.msel

# Eine Modellliste für alle Ansichten: immer dieselben 12 Modelle in derselben Reihenfolge.
MODEL_ORDER = [m["model"] for m in next(iter(CASES.values()))["models"]]
STATUS_DE = {"n/a": "nicht anwendbar", "unplausibel": "unplausibel (außerhalb 0,2–5× Kurs, nicht im Median)"}

def models_of(c):
    by = {m["model"]: m for m in c["models"]}
    ok = [by[n] for n in MODEL_ORDER if n in by and by[n]["value"] is not None and by[n]["status"] == "ok"]
    na = [(n, "liefert eingepreistes Wachstum statt fairen Wert" if n == "Reverse-DCF" else STATUS_DE.get(by[n]["status"], by[n]["status"]))
          for n in MODEL_ORDER if n in by and by[n] not in ok]
    return ok, na

def models_note(c):
    ok, na = models_of(c)
    if not na: return ""
    return (f'<div class="inote"><span class="ii" tabindex="0" aria-label="Erläuterung">i<span class="tip">{len(ok)} von {len(MODEL_ORDER)} Modellen liefern für {c["symbol"]} einen Wert. Ohne Wert: '
            + "; ".join(f"{n} ({r})" for n, r in na) + '.</span></span><span class="il">Erläuterung</span></div>')
