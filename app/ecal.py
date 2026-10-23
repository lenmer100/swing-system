"""Zahlentermine: Kalender für den Pool (wichtige Titel oder alle) und Detailansicht je Termin.
Quellen: data/earnings_cal.json (Yahoo Finance: Termin, Uhrzeit, Konsens), data/earnings_v3.json (Beat-Historie, einheitliche EPS-Basis),
data/swing.json (Kursreaktionen), data/quarters.json (letztes Quartal, SEC EDGAR), data/consensus.json (Jahreskonsens). Optionen live für die erwartete Bewegung."""
import datetime as dt, json
import pandas as pd
import streamlit as st
from lib import D, fnum, fpct, fdate, fbig, pill, footer2
import common, live
from common import META, CASES

TIME_SHORT = {"vor Börseneröffnung": "vorbörslich", "nach Börsenschluss": "nachbörslich"}
WD = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
MON = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
IMPORTANT_MCAP = 50e9

@st.cache_data(ttl=3600)
def _cal():
    f = D / "earnings_cal.json"
    return json.loads(f.read_text()) if f.exists() else {"rows": {}, "asof": None}

@st.cache_resource
def _hist():
    return (json.loads((D / "earnings_v3.json").read_text())["stocks"], json.loads((D / "quarters.json").read_text()),
            json.loads((D / "swing.json").read_text())["stocks"])

def _swing_syms():
    try:
        from swing_calc import board_rows
        return {r["sym"] for r in board_rows() if r.get("status") in ("In Einstiegszone", "Nahe Einstiegszone")}
    except Exception:
        return set()

def _mcap(s): return ((CASES.get(s) or {}).get("keystats") or {}).get("mcap") or 0

def events(d0, d1, important=True):
    """Termine im Zeitraum; Yahoo-Kalender, sonst Snapshot-Datum. Sortiert nach Datum, Uhrzeit, Marktwert."""
    cal = _cal()["rows"]; sw = _swing_syms() if important else set(); out = []
    for s, c in CASES.items():
        r = cal.get(s) or ({"symbol": s, "date": c["next_earnings"]} if c.get("next_earnings") else None)
        if not r or not r.get("date"): continue
        if not (d0.isoformat() <= r["date"] <= d1.isoformat()): continue
        if important and not (_mcap(s) >= IMPORTANT_MCAP or s in sw or s in common.FEATURED): continue
        out.append({**r, "mcap": _mcap(s), "swing": s in sw})
    order = {"vor Börseneröffnung": 0, None: 1, "nach Börsenschluss": 2}
    return sorted(out, key=lambda x: (x["date"], order.get(x.get("time"), 1), -x["mcap"]))

def confirmed(r):
    """Termin plausibel: Abstand zum letzten gemeldeten Termin (Yahoo) 50–130 Tage, bei Halbjahresberichtern außerhalb der USA 160–200 Tage.
    Sonst 'unbestätigt' (z. B. kein Vortermin, Lücke im Kalender, Termin zu nah am letzten)."""
    if not r.get("date") or not r.get("last"): return False
    gap = (pd.Timestamp(r["date"]) - pd.Timestamp(r["last"])).days
    return 50 <= gap <= 130 or ("." in r.get("symbol", "") and 160 <= gap <= 200)

@st.cache_data(ttl=86400, show_spinner=False)
def _guidance(s):
    if "." in s: return None
    try:
        import guidance; return guidance.latest(s)
    except Exception:
        return None

def beats(s):
    """Beat-Historie mit einheitlicher Basis. Quote nur, wenn höchstens 25 % der Quartale wegen Basiswechsel ausgeschlossen sind."""
    h = (_hist()[0].get(s) or {}).get("rows") or []
    ok = [r for r in h if not r.get("excluded_one_off") and r.get("eps_est") is not None and r.get("eps_rep") is not None]
    rate = None
    if h and (len(h) - len(ok)) / len(h) <= 0.25 and ok:
        rate = (sum(r["eps_rep"] > r["eps_est"] for r in ok), len(ok))
    return ok, rate

CSS = """<style>
.ec-h1{font-size:28px;font-weight:700;color:var(--ink);margin:26px 0 4px}
.ec-sub{font-size:13px;color:var(--muted);margin-bottom:10px}
.ec-day{font-size:14px;font-weight:700;color:var(--ink);margin:22px 0 8px;display:flex;gap:8px;align-items:baseline}
.ec-day span{font-size:12.5px;color:var(--muted);font-weight:500}
.etb{width:100%;table-layout:fixed;border-collapse:collapse;font-size:13.5px;font-variant-numeric:tabular-nums;border:1px solid var(--line);border-radius:12px;overflow:hidden;border-style:hidden;box-shadow:0 0 0 1px var(--line)}
.etb th{font-size:12px;font-weight:600;color:var(--muted);text-align:left;padding:8px 12px;border-bottom:1px solid var(--line);background:#fafbfd;white-space:nowrap}
.etb td{padding:0;border-bottom:1px solid var(--line);white-space:nowrap} .etb tr:last-child td{border-bottom:none}
.etb td a{display:block;overflow:hidden;text-overflow:ellipsis;padding:10px 12px;color:var(--ink);text-decoration:none} .etb tr:hover td{background:var(--card)}
.etb .r{text-align:right} .etb .mut{color:var(--muted)} .etb .nm{font-weight:600}
.tm{display:inline-block;font-size:12px;font-weight:600;border-radius:999px;padding:2px 9px;background:#eef2f6;color:var(--ink2)}
.tm.pre{background:#e8f1fb;color:#1f5f9e} .tm.post{background:#f1ecfb;color:#5b3fa6}
.ub{display:inline-block;font-size:11.5px;font-weight:600;border-radius:999px;padding:1px 8px;background:#fef0c7;color:#93370d;margin-left:6px}
.gd{border:1px solid var(--line);border-radius:12px;padding:14px 18px} .gd p{margin:0 0 8px;font-size:14px;color:var(--ink)} .gd .src{font-size:12.5px;color:var(--muted)}
.sw{display:inline-block;font-size:11.5px;font-weight:600;border-radius:999px;padding:1px 8px;background:var(--posbg);color:var(--pos);margin-left:6px}
.ed-top{display:flex;justify-content:space-between;align-items:flex-end;margin:22px 0 14px;gap:20px}
.ed-top h1{font-size:28px;font-weight:700;margin:0;padding:0;color:var(--ink)} .ed-top .tk{color:var(--muted);font-weight:500;font-size:20px;margin-left:8px}
.ed-top .when{font-size:15px;color:var(--ink2);margin-top:4px}
.ed-top .lk a{font-size:13px;font-weight:600;text-decoration:none;margin-left:16px}
.kp{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:8px}
.kp div.c{border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.kp .l{font-size:12.5px;color:var(--muted);font-weight:600} .kp .v{font-size:22px;font-weight:700;color:var(--ink);margin:4px 0 2px;font-variant-numeric:tabular-nums}
.kp .s{font-size:12.5px;color:var(--muted);font-variant-numeric:tabular-nums}
.ed-h2{font-size:16px;font-weight:700;color:var(--ink);margin:24px 0 10px}
.ptb{width:100%;border-collapse:collapse;font-size:13.5px;font-variant-numeric:tabular-nums}
.ptb th{font-size:12px;font-weight:600;color:var(--muted);text-align:right;padding:8px 12px;border-bottom:1px solid var(--line);background:#fafbfd}
.ptb th:first-child,.ptb td:first-child{text-align:left} .ptb td{padding:9px 12px;border-bottom:1px solid var(--line);text-align:right}
.ptb tr:last-child td{border-bottom:none} .ptb .up{color:var(--pos);font-weight:600} .ptb .dn{color:var(--neg);font-weight:600}
.bx{border:1px solid var(--line);border-radius:12px;overflow:hidden}
.back a{font-size:13px;font-weight:600;text-decoration:none}
.etw{overflow-x:auto} .bx{overflow-x:auto !important}
@media (max-width:640px){.etb{min-width:720px}.ptb{min-width:600px}.ed-top{flex-direction:column;align-items:flex-start}.ed-top .lk a{margin:0 16px 0 0}.ec-h1,.ed-top h1{font-size:22px}}
</style>"""

def _tm(t):
    if t == "vor Börseneröffnung": return '<span class="tm pre">vorbörslich</span>'
    if t == "nach Börsenschluss": return '<span class="tm post">nachbörslich</span>'
    return '<span class="mut">–</span>'

def _cur(s): return (CASES.get(s) or {}).get("currency") or "USD"

def calendar_view():
    cal = _cal()
    st.markdown(f'<div class="ec-h1">Zahlentermine</div><div class="ec-sub">Yahoo Finance · Stand {fdate((cal.get("asof") or META["asof"])[:10])}</div>', unsafe_allow_html=True)
    today = dt.date.today()
    c1, c2, _ = st.columns([1.4, 1.6, 2])
    with c1:
        imp = st.segmented_control("Auswahl", ["Wichtige", "Alle"], default="Wichtige", key="ec_imp", label_visibility="collapsed") or "Wichtige"
    with c2:
        span = st.segmented_control("Zeitraum", ["Diese Woche", "2 Wochen", "4 Wochen"], default="2 Wochen", key="ec_span", label_visibility="collapsed") or "2 Wochen"
    d1 = today + dt.timedelta(days={"Diese Woche": 6 - today.weekday(), "2 Wochen": 14, "4 Wochen": 28}[span])
    dsel = st.query_params.get("d")
    ev = events(today, d1, important=imp == "Wichtige")
    if dsel: ev = [e for e in ev if e["date"] == dsel] or ev
    if not ev:
        st.markdown('<div class="ec-sub" style="margin-top:30px">Keine Termine im gewählten Zeitraum.</div>', unsafe_allow_html=True)
    th = ("<tr><th style='width:12%'>Zeitpunkt</th><th style='width:36%'>Aktie</th><th class='r' style='width:13%'>EPS-Konsens</th><th class='r' style='width:15%'>Umsatz-Konsens</th>"
          "<th class='r' style='width:10%'>Beat-Quote</th><th class='r' style='width:14%'>Marktwert</th></tr>")
    for d in sorted({e["date"] for e in ev}):
        D_ = pd.Timestamp(d)
        rows = [e for e in ev if e["date"] == d]
        st.markdown(f'<div class="ec-day">{WD[D_.weekday()]}, {D_.day}. {MON[D_.month - 1]}<span>{len(rows)} {"Termin" if len(rows) == 1 else "Termine"}</span></div>', unsafe_allow_html=True)
        body = ""
        for e in rows:
            s = e["symbol"]; c = CASES[s]; cur = _cur(s); _, rate = beats(s)
            a = lambda x, cls="": f'<td class="{cls}"><a href="/zahlentermine?e={s}" target="_self">{x}</a></td>'
            eps = e.get("eps_avg", e.get("eps_est"))
            body += ("<tr>" + a(_tm(e.get("time"))) + a(f'<span class="nm">{c["name"].split(" (")[0]}</span> <span class="mut">({s})</span>' + ('<span class="sw">Swing-Chance</span>' if e.get("swing") else "") + ("" if confirmed(e) else '<span class="ub">unbestätigt</span>'))
                     + a(f'{fnum(eps)} {cur}' if eps is not None else '<span class="mut">–</span>', "r")
                     + a(fbig(e["rev_avg"], cur) if e.get("rev_avg") else '<span class="mut">–</span>', "r")
                     + a(f'{rate[0]} von {rate[1]}' if rate else '<span class="mut">–</span>', "r")
                     + a(fbig(e["mcap"], cur) if e["mcap"] else "–", "r mut") + "</tr>")
        st.markdown(f'<div class="etw"><table class="etb"><thead>{th}</thead><tbody>{body}</tbody></table></div>', unsafe_allow_html=True)

def detail_view(s):
    c = CASES[s]; cur = _cur(s); e = _cal()["rows"].get(s) or {"date": c.get("next_earnings")}
    d = e.get("date")
    when = (f'{WD[pd.Timestamp(d).weekday()]}, {fdate(d)}' + (f' · {e["time"]}' if e.get("time") else "")
            + ("" if confirmed({**e, "symbol": s}) else ' <span class="ub">unbestätigt</span>')) if d else "Termin noch nicht bekannt"
    st.markdown('<div class="back" style="margin-top:18px"><a href="/zahlentermine" target="_self">← Alle Zahlentermine</a></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="ed-top"><div><h1>{c["name"].split(" (")[0]}<span class="tk">{s}</span></h1><div class="when">Quartalszahlen · {when}</div></div>'
                f'<div class="lk"><a href="/aktienanalyse?t={s}" target="_self">Aktienanalyse</a><a href="/swing-tool?t={s}" target="_self">Swing-Tool</a></div></div>', unsafe_allow_html=True)
    ok, rate = beats(s); sw = _hist()[2].get(s) or {}
    reac = {r[0]: r[1] for r in sw.get("reactions") or []}
    rx = [abs(v) for v in reac.values() if v == v][-8:]
    near = d and (pd.Timestamp(d) - pd.Timestamp.today().normalize()).days <= 30   # Optionen nur aussagekräftig für einen nahen Termin
    im = live.implied_move(s, d) if near and "." not in s else None
    eps = e.get("eps_avg", e.get("eps_est"))
    cards = []
    if eps is not None:
        cards.append(("EPS-Konsens", f"{fnum(eps)} {cur}", f'Spanne {fnum(e["eps_low"])} – {fnum(e["eps_high"])}' if e.get("eps_low") is not None else ""))
    if e.get("rev_avg"):
        cards.append(("Umsatz-Konsens", fbig(e["rev_avg"], cur), f'Spanne {fbig(e["rev_low"], "")} – {fbig(e["rev_high"], "")}' if e.get("rev_low") else ""))
    if im: cards.append(("Erwartete Bewegung", "± " + fpct(im["move"], 1), f'Optionen, Verfall {fdate(im["expiry"])}'))
    if rx: cards.append(("Ø Kursreaktion", "± " + fpct(sum(rx) / len(rx), 1), f"Betrag, letzte {len(rx)} Termine"))
    if rate: cards.append(("Beat-Quote", f"{rate[0]} von {rate[1]}", "Gewinn über Konsens"))
    if cards:
        st.markdown('<div class="kp">' + "".join(f'<div class="c"><div class="l">{l}</div><div class="v">{v}</div><div class="s">{x}</div></div>' for l, v, x in cards[:4]) + "</div>", unsafe_allow_html=True)
    q = (_hist()[1].get(s) or [])
    if q:
        L = q[-1]; P = next((x for x in q if x["end"][:4] == str(int(L["end"][:4]) - 1) and x["end"][5:] == L["end"][5:]), None)
        g = lambda k: (L[k] / P[k] - 1) if P and P.get(k) and L.get(k) and P[k] > 0 else None
        items = [("Umsatz", fbig(L.get("revenue"), cur), g("revenue")), ("Gewinn je Aktie", f'{fnum(L.get("eps"))} {cur}', g("eps")),
                 ("Operative Marge", fpct(L.get("op_margin"), 1), None), ("Freier Cashflow", fbig(L.get("fcf"), cur), g("fcf"))]
        st.markdown(f'<div class="ed-h2">Letztes erfasstes Quartal (SEC) · {L["label"]}</div>', unsafe_allow_html=True)
        st.markdown('<div class="kp">' + "".join(f'<div class="c"><div class="l">{l}</div><div class="v">{v}</div><div class="s">'
                    + (f'{pill(x, 1)} zum Vorjahresquartal' if x is not None else "&nbsp;") + "</div></div>" for l, v, x in items) + "</div>", unsafe_allow_html=True)
    g = _guidance(s)
    if g and g.get("sentences"):
        st.markdown('<div class="ed-h2">Letzte Guidance</div>', unsafe_allow_html=True)
        import html as _h
        st.markdown('<div class="gd">' + "".join(f'<p>{_h.escape(x)}{" (in Mio. USD)" if g.get("millions") and "billion" not in x and "per share" not in x else ""}</p>' for x in g["sentences"])
                    + f'<div class="src">Pressemitteilung vom {fdate(g["date"])} · <a href="{g["url"]}" target="_blank">SEC-Filing 8-K</a></div></div>', unsafe_allow_html=True)
    from lib import load_v3
    yrs = (load_v3()[1].get(s) or {}).get("years")
    if yrs:
        st.markdown('<div class="ed-h2">Analystenkonsens Geschäftsjahr</div>', unsafe_allow_html=True)
        b = "".join(f'<tr><td>GJ {y["fy"]}</td><td>{fbig(y.get("rev"), cur)}</td><td>{fpct(y.get("rev_growth"), 1, True)}</td><td>{fnum(y.get("eps"))} {cur}</td>'
                    f'<td>{fpct(y.get("eps_growth"), 1, True)}</td><td>{fnum(y.get("eps_n"), 0)}</td></tr>' for y in yrs)
        st.markdown('<div class="bx"><table class="ptb"><thead><tr><th>Jahr</th><th>Umsatz</th><th>Wachstum</th><th>Gewinn je Aktie</th><th>Wachstum</th><th>Analysten</th></tr></thead>'
                    f'<tbody>{b}</tbody></table></div>', unsafe_allow_html=True)
    if e.get("last") and e.get("last_eps_rep") is not None and e.get("last_eps_est") and not any(r["date"] == e["last"] for r in ok):
        ok = ok + [dict(date=e["last"], eps_est=e["last_eps_est"], eps_rep=e["last_eps_rep"])]   # jüngster Termin aus Yahoo, noch nicht im Snapshot
    if ok:
        st.markdown('<div class="ed-h2">Bisherige Quartalszahlen</div>', unsafe_allow_html=True)
        b = ""
        for r in reversed(ok[-8:]):
            sp = r["eps_rep"] / r["eps_est"] - 1 if r["eps_est"] else None
            rc = reac.get(r["date"])
            b += (f'<tr><td>{fdate(r["date"])}</td><td>{fnum(r["eps_est"])}</td><td>{fnum(r["eps_rep"])}</td>'
                  f'<td class="{"up" if r["eps_rep"] > r["eps_est"] else "dn"}">{"Übertroffen" if r["eps_rep"] > r["eps_est"] else "Verfehlt" if r["eps_rep"] < r["eps_est"] else "Getroffen"}</td>'
                  f'<td>{fpct(sp, 1, True) if sp is not None and r["eps_est"] > 0 else "–"}</td>'
                  f'<td class="{"up" if rc and rc > 0 else "dn" if rc else ""}">{fpct(rc, 1, True) if rc is not None else "–"}</td></tr>')
        st.markdown(f'<div class="bx"><table class="ptb"><thead><tr><th>Termin</th><th>EPS erwartet ({cur})</th><th>EPS gemeldet ({cur})</th><th>Ergebnis</th>'
                    f'<th>Überraschung</th><th>Kursreaktion</th></tr></thead><tbody>{b}</tbody></table></div>', unsafe_allow_html=True)

def page():
    st.markdown(CSS, unsafe_allow_html=True)
    s = st.query_params.get("e")
    if s in CASES: detail_view(s)
    else: calendar_view()
    footer2(META)
