import hashlib, hmac, os, time
from urllib.parse import urlparse
import streamlit as st
import streamlit.components.v1 as components
from lib import CSS

st.set_page_config(page_title="Swing-System · Aktienanalyse und Swing-Tool", layout="wide", initial_sidebar_state="collapsed")
st.markdown(CSS, unsafe_allow_html=True)

import analysis, swing, about, common, home, investment, ecal

# Navigation wird immer registriert (auch vor dem Login), damit Unterseiten-URLs nie "Page not found" zeigen.
P = {"analyse": st.Page(analysis.page, title="Aktienanalyse", url_path="aktienanalyse"),
     "swing": st.Page(swing.page, title="Swing-Tool", url_path="swing-tool"),
     "invest": st.Page(investment.page, title="Investment", url_path="investment"),
     "earn": st.Page(ecal.page, title="Zahlentermine", url_path="zahlentermine"),
     "about": st.Page(about.about, title="Über das Projekt", url_path="projekt"),
     "valid": st.Page(about.validation, title="Validierung", url_path="validierung")}
def _home():  # "/" = Startseite; alte Deep-Links "/?t=…&tab=…" öffnen weiterhin direkt die Aktienanalyse
    if st.query_params.get("t") in common.CASES: analysis.page()
    else: home.home()
ALIAS = st.Page(_home, title="Start", url_path="start", default=True)
common.PAGES.update(P)

# Unbekannte URL: nicht Streamlits englischen Dialog zeigen, sondern auf Deutsch zur Startseite umleiten.
_path = urlparse(st.context.url or "").path.strip("/")
if _path and _path not in {p.url_path for p in P.values()} | {"start"}:
    q = f"?t={st.query_params['t']}" if st.query_params.get("t") in common.CASES else ""
    st.markdown('<div style="height:10vh"></div><div class="eyebrow">Swing-System</div>', unsafe_allow_html=True)
    st.title("Seite nicht gefunden")
    st.markdown(f'<p class="lead">Diese Adresse gibt es nicht. Sie werden zur Startseite weitergeleitet. '
                f'<a href="/{q}" target="_self">Zur Startseite</a></p>', unsafe_allow_html=True)
    components.html(f"<script>setTimeout(()=>{{const d=window.parent.document,a=d.createElement('a');a.href='/{q}';a.target='_self';d.body.appendChild(a);a.click();}},2500)</script>", height=0)
    st.stop()

pg = st.navigation(list(P.values()) + [ALIAS], position="hidden")

# Anmeldung bleibt bei Neuladen erhalten: Cookie mit Ablaufzeit + HMAC (Schlüssel = DEMO_PASSWORD), kein Passwort im Cookie oder in der URL.
COOKIE, TTL = "swing_demo_auth", 12 * 3600
def _sig(pw, exp): return hmac.new(pw.encode(), f"swing-demo|{exp}".encode(), hashlib.sha256).hexdigest()
def _token(pw):
    exp = int(time.time()) + TTL
    return f"{exp}.{_sig(pw, exp)}"
def _valid(pw, tok):
    try:
        exp, sig = tok.split(".", 1)
        return int(exp) > time.time() and hmac.compare_digest(sig, _sig(pw, int(exp)))
    except (AttributeError, ValueError):
        return False

def gate():
    pw = os.environ.get("DEMO_PASSWORD")
    if not pw or st.session_state.get("auth"): return True
    if _valid(pw, st.context.cookies.get(COOKIE)):
        st.session_state.auth = True; return True
    _, mid, _ = st.columns([1, 1.1, 1])
    with mid:
        st.markdown('<div style="height:14vh"></div><div class="logo" style="justify-content:center;font-size:24px;margin:0 0 6px"><i aria-hidden="true">S</i>Swing System</div>'
                    '<p class="lead" style="text-align:center;margin:0 auto 14px">Bitte Passwort eingeben.</p>', unsafe_allow_html=True)
        with st.form("login", border=True):
            v = st.text_input("Passwort", type="password")
            if st.form_submit_button("Anmelden", type="primary", width="stretch"):
                if hmac.compare_digest(v.encode(), pw.encode()):
                    st.session_state.auth = True; st.session_state.set_cookie = _token(pw); st.rerun()
                else:
                    st.error("Falsches Passwort.")
    return False

if not gate():
    st.stop()

_tok = st.session_state.pop("set_cookie", None)

import live

# Kopfbereich: Marktleiste + Navigationsleiste (Logo links, Produkt-Navigation, Aktiensuche rechts, Projektseiten zweitrangig)
live.strip()
cur = common.current()
_q = {"t": cur} if cur else None
_here = next((k for k, v in P.items() if v._script_hash == pg._script_hash), "analyse" if cur else "home")  # Startseite zählt als Aktienanalyse   # Alias zählt als Aktienanalyse
def _pick():
    v = st.session_state.get("nav_search")
    common.set_ticker(v)
    if _here in ("about", "valid", "home", "earn"): st.session_state.goto_analyse = True
with st.container(key="topnav", horizontal=True, vertical_alignment="center", gap="small"):
    st.markdown('<a class="logo" href="/" target="_self" title="Zur Startseite"><i aria-hidden="true">S</i>Swing System</a>', unsafe_allow_html=True)
    for k, lab in (("analyse", "Aktienanalyse"), ("swing", "Swing-Tool"), ("invest", "Investment"), ("earn", "Zahlentermine")):
        with st.container(key=f"nav_{'on' if _here == k else 'off'}_{k}", width="content"):
            st.page_link(P[k], label=lab, query_params=_q)
    st.space("stretch")
    st.session_state["nav_search"] = cur
    with st.container(width=210, key="hidesearch_off"):  # Startseite hat die große Suche
        st.selectbox("Aktie suchen", common.SYMS, key="nav_search", on_change=_pick, placeholder="Aktie suchen",
                     label_visibility="collapsed", format_func=lambda s: f"{common.CASES[s]['name']} ({s})")
    with st.container(key=f"nav_sec_{'on' if _here in ('about', 'valid') else 'off'}", width="content"):
        st.page_link(P["about"], label="Über das Projekt", query_params=_q)
if st.session_state.pop("goto_analyse", False):
    common.go("analyse")
if _tok:
    _sec = "; Secure" if (st.context.url or "").startswith("https") else ""
    components.html(f"<script>window.parent.document.cookie = '{COOKIE}={_tok}; Max-Age={TTL}; Path=/; SameSite=Strict{_sec}';</script>", height=0)

pg.run()
