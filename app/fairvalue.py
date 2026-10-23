"""Eine Definition des fairen Werts für alle Bereiche: Bewertungs-Engine v4 nach Archetyp (data/valuation_v4.json).
Nicht belastbare Bewertungen (Leitplanken in engine_v4._guards) -> get() liefert None: keine Kaufzone, keine Tranchen.
Fairer Wert = v3-Basis; faire Spanne = pessimistisch bis optimistisch; Kaufzone = v3 'kaufen unter'
(Sicherheitsmarge aus Analystenstreuung, 20-50 %); Stressszenario = pessimistisch.
Aktien ohne v3-Wert -> get() liefert None, die Bewertungsblöcke werden ausgeblendet."""
import json
from pathlib import Path
import streamlit as st

from lib import D as _D; P = _D / "valuation_v4.json"
MOS_FALLBACK = 0.30
MODEL_DE = {"fcff": "Cashflow-DCF", "excess_returns": "Übergewinn-Modell (Bank/Versicherung)", "affo": "AFFO-Modell (REIT)"}
MOAT_DE = {"wide": "breiter Burggraben", "narrow": "schmaler Burggraben", "none": "kein Burggraben"}
STAGE_DE = {"hyper": "Hyperwachstum", "high": "hohes Wachstum", "mature": "reif"}


@st.cache_resource
def _load(mtime):
    return json.loads(P.read_text())


def all_():
    return _load(P.stat().st_mtime) if P.exists() else {"stocks": {}}


def raw(sym):
    r = all_()["stocks"].get(sym)
    if not r or r.get("status") != "ok" or not r.get("range") or not (r["range"].get("base") or 0) > 0:
        return None
    return r


OUTLIER = "Modellwert weicht stark vom Markt ab, Prüfung offen"
def outlier(r):
    """Anzeige-Leitplanke (nur UI, Modellwert bleibt unverändert): Basis/Kurs > 2,0 oder < 0,4 bzw. opt/pess > 2,2."""
    try:
        rg = r.get("range") or {}; b, px = rg.get("base") or 0, r.get("price") or 0
        if b <= 0 or px <= 0: return False
        q = b / px; sp = (rg.get("optimistic") or 0) / rg["pessimistic"] if (rg.get("pessimistic") or 0) > 0 else None
        return q > 2.0 or q < 0.4 or (sp is not None and sp > 2.2)
    except Exception:
        return False

import re as _re
def _de_reason(x):
    """Gründe kundentauglich: deutsche Dezimalzahlen, keine Kürzel."""
    x = _re.sub(r"(?<=\d)\.(?=\d)", ",", x)
    x = _re.sub(r"(\d),(\d{3})(?= Mio)", r"\1.\2", x)
    x = x.replace("(pess ", "(pessimistisch ").replace(" / opt ", " / optimistisch ")
    return x[:1].upper() + x[1:]

def unreliable(sym):
    return [_de_reason(x) for x in _unreliable(sym)]

def _unreliable(sym):
    """Gründe, warum die Bewertung nicht belastbar ist (leer = belastbar)."""
    r = all_()["stocks"].get(sym)
    if not r or r.get("status") != "ok":
        return [(r or {}).get("status") or "keine Bewertung"]
    if r.get("display_mode", "value") == "value" and r.get("range_valid", True) and outlier(r):
        return [OUTLIER]
    if r.get("display_mode") == "implied_return":
        return ["Kapazitätsaufbau: kein Punktwert, nur die vom Kurs implizierte Rendite auf neue Kapazität"]
    if r.get("display_mode", "value") != "value" or not r.get("range_valid", r.get("reliable")):
        return [x for x in (r.get("unreliable_reasons") or ["nicht belastbar"]) if "Kapazitätsaufbau" not in x] or ["nicht belastbar"]
    return [] if r.get("reliable") else (r.get("unreliable_reasons") or ["nicht belastbar"])


def mode(sym):
    """'value' | 'implied_return' | 'nicht_belastbar' | None (keine Bewertung)."""
    r = all_()["stocks"].get(sym)
    if not r or r.get("status") != "ok":
        return None
    m = r.get("display_mode") or ("value" if r.get("reliable") else "nicht_belastbar")
    return "nicht_belastbar" if m == "value" and (not r.get("range_valid", True) or outlier(r)) else m


def plan(sym):
    """Tranchen/Stopp/Stress aus der Engine (invest_plan); None wenn nicht verfügbar."""
    r = all_()["stocks"].get(sym) or {}
    p = r.get("invest_plan") or {}
    return p if p.get("available") and mode(sym) == "value" else None


def implied(sym):
    return (all_()["stocks"].get(sym) or {}).get("implied_return")


def archetype(sym):
    r = all_()["stocks"].get(sym) or {}
    return r.get("archetype")


def get(sym):
    r = raw(sym)
    if not r or not r.get("reliable", True) or mode(sym) != "value":
        return None
    rg, cl = r["range"], r.get("classification") or {}
    fp = (r["scenarios"]["base"].get("forward_pe") or {}).get("forward_pe")
    rd = r.get("reverse_dcf") or {}
    buy = r.get("buy_zone_below") or rg["base"] * (1 - MOS_FALLBACK)
    return dict(base=rg["base"], pess=rg["pessimistic"], opt=rg["optimistic"], mos=buy, buy=buy,
                price=r["price"], asof=r["asof"], upside=rg["base"] / r["price"] - 1, fpe=fp,
                implied=rd.get("implied_rev_cagr_5y"), base_g=rd.get("base_rev_cagr_5y"),
                model=cl.get("model"), moat=cl.get("moat"), stage=cl.get("stage"), cyclical=cl.get("cyclical"),
                reinvester=cl.get("reinvester"), uncertainty=cl.get("uncertainty"), mos_pct=cl.get("margin_of_safety"),
                weights=r.get("weights"))


def pills(sym):
    g = get(sym)
    if not g:
        r = raw(sym)
        if not r:
            return []
        cl = r.get("classification") or {}
        g = dict(model=cl.get("model"), moat=cl.get("moat"), stage=cl.get("stage"), cyclical=cl.get("cyclical"), reinvester=cl.get("reinvester"), uncertainty=cl.get("uncertainty"))
    p = [MODEL_DE.get(g["model"], g["model"]), MOAT_DE.get(g["moat"], ""), STAGE_DE.get(g["stage"], "")]
    if g["cyclical"]: p.append("Zykliker (Zyklusmarge)")
    if g["reinvester"]: p.append("Reinvestierer (ohne KGV-Block)")
    if g["uncertainty"]: p.append(f"Unsicherheit {g['uncertainty']}")
    cl_ = raw(sym)["classification"] or {}
    if cl_.get("only_annual"): p.append("nur Jahreszahlen")
    if cl_.get("stale"): p.append("Zahlen veraltet")
    return [x for x in p if x]


_E = _D / "earnings_v3.json"


@st.cache_resource
def _eload(mtime):
    return json.loads(_E.read_text())["stocks"]


def beat_rate(sym):
    """(beats, n) on consistent adjusted basis; None if not available or basis mixed (hidden)."""
    if not _E.exists():
        return None
    e = _eload(_E.stat().st_mtime).get(sym)
    if not e or not e.get("show_beat_rate"):
        return None
    return e["beats"], e["n_usable"]


def has_earnings_basis(sym):
    return _E.exists() and sym in _eload(_E.stat().st_mtime)
