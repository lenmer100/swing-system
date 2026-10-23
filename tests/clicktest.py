"""Klicktest v3: Login-Persistenz, Top-Navigation, Suche, Tabs (?tab=), ?t= überall, reine Analyse (keine Urteile),
Marktleiste, Chancen-Board mit Filter, Kurschart-Schalter, Swing-Chart-Vollbild, NVDA-Chartmarken, unbekannte URL."""
import re
from playwright.sync_api import sync_playwright
import os
BASE = os.environ.get("BASE", "http://127.0.0.1:8501"); DD = "./" + os.environ.get("DATA_DIR", "data"); import json as _jj; FULL = len(_jj.load(open(DD + "/cases.json"))) > 5; PW = __import__("os").environ["DEMO_PASSWORD"]; OUT = os.environ.get("OUT", "./screenshots/v3")
res = []
def ok(name, cond): res.append((name, "pass" if cond else "FAIL"))
from playwright.sync_api import Locator
_click = Locator.click
def _safe(self, *a, **k):
    try: return _click(self, *a, **{"timeout": 8000, **k})
    except Exception as e: res.append(("Klick " + str(self)[:90], "FAIL"))
Locator.click = _safe
_shot = Locator.screenshot
def _safeshot(self, *a, **k):
    try: return _shot(self, *a, **{"timeout": 8000, **k})
    except Exception: res.append(("Screenshot " + str(self)[:90], "FAIL"))
Locator.screenshot = _safeshot
_it = Locator.inner_text
def _safeit(self, *a, **k):
    try: return _it(self, *a, **{"timeout": 8000, **k})
    except Exception: return ""
Locator.inner_text = _safeit
_bb = Locator.bounding_box
def _safebb(self, *a, **k):
    try: return _bb(self, *a, **{"timeout": 8000, **k})
    except Exception: return None
Locator.bounding_box = _safebb
def main(pg): return pg.locator("[data-testid=stMain]").inner_text()
def wait(pg, ms=3000): pg.wait_for_timeout(ms)
def btn(pg, lab, scope="[data-testid=stMain]"): pg.locator(scope + " button", has_text=re.compile("^" + re.escape(lab) + "$")).first.click(); wait(pg)
BANNED = ["Kaufbereit", "Warten", "Zu teuer", "zu teuer", "Urteil", "Einstiegszone", "Stopp", "Positionsgröße", "Marktampel"]
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(viewport={"width": 1440, "height": 1000}); pg = ctx.new_page()
    pg.goto(BASE, wait_until="networkidle"); wait(pg, 2500)
    pg.screenshot(path=f"{OUT}/00_login.png")
    ff = pg.evaluate("() => { const e = document.querySelector('[data-testid=stIconMaterial]'); return e ? getComputedStyle(e).fontFamily : 'none'; }")
    ok("Login: kein 'Page not found', Icons als Symbolschrift", "Page not found" not in pg.locator("body").inner_text() and ("Material" in ff or ff == "none"))
    pg.fill('input[type="password"]', PW); pg.keyboard.press("Enter"); wait(pg, 4500)
    ok("Login: keine Exception", pg.locator('[data-testid="stException"]').count() == 0 and pg.locator(".st-key-topnav").count() == 1)
    try: pg.get_by_text("Zahlentermine der nächsten Tage").wait_for(timeout=90000)
    except Exception: pass
    ok("Marktleiste: 8 Werte live, kein k. A.", pg.locator(".mstrip .it").count() == 8 and "k. A." not in pg.locator(".mstrip").inner_text())
    _strip = pg.locator(".mstrip").inner_text(); _vix = pg.locator(".st-key-mrow_VIX").inner_text()
    ok("Marktleiste = Live-Liste (VIX gleich)", "Live" in _strip and _vix.split("\n")[1].strip() in _strip if "\n" in _vix else False)
    ok("Keine Seitenleiste sichtbar", not pg.locator('[data-testid="stSidebar"]').is_visible() if pg.locator('[data-testid="stSidebar"]').count() else True)
    ok("Startseite: Markt heute, 11 Marktwerte, Chancen, Bewegungen, Zahlentermine", all(x in main(pg) for x in ["Markt heute", "Chancen aus dem Swing-Pool", "Größte Bewegungen", "Zahlentermine der nächsten Tage"])
       and pg.locator("[class*=st-key-mrow_]").count() == 11)
    pg.locator(".mv a").first.click(); wait(pg, 5000)
    ok("Bewegung öffnet Aktienanalyse ?t=", "aktienanalyse" in pg.url and "t=" in pg.url)
    pg.locator("a.logo").click(); wait(pg, 6000)
    ok("Logo führt zur Startseite, weiter angemeldet", "Markt heute" in main(pg) and pg.locator('input[type="password"]').count() == 0)
    pg.locator(".wk a").first.click(); wait(pg, 6000)
    ok("Zahlentermin auf Startseite öffnet Detail", "zahlentermine?e=" in pg.url and "Quartalszahlen" in main(pg))
    pg.locator("a.logo").click(); wait(pg, 6000)
    pg.goto(BASE + "/aktienanalyse", wait_until="networkidle"); wait(pg, 3500)
    ok("Analyse-Start ohne Urteile", not any(w in main(pg) for w in BANNED))
    pg.locator(".st-key-topnav [data-testid=stSelectbox]").click(); wait(pg, 800)
    pg.get_by_role("option", name=re.compile("Meta Platforms")).click(); wait(pg, 3500)
    ok("Suche in der Kopfzeile öffnet META (?t=META)", "t=META" in pg.url and "Meta Platforms" in main(pg))
    for tab, marker in (("Analysten", "Einstufungen"), ("Bewertung", "Spanne pessimistisch"), ("Szenarien", "Konservativ"), ("Finanzdaten", "Umsatz"), ("Übersicht", "Kennzahlen")):
        pg.locator(".st-key-tabs button", has_text=re.compile("^" + tab + "$")).click(); wait(pg, 3500)
        txt = main(pg)
        ok(f"Tab {tab}: Inhalt + URL ?tab=, ?t= bleibt", marker in txt and f"tab={tab}".replace("Ü", "%C3%9C") in pg.url.replace("Ü", "%C3%9C") and "t=META" in pg.url)
        bad = [w for w in BANNED if w in txt]
        ok(f"Tab {tab}: keine Urteile/Einstiegsdaten {bad if bad else ''}", not bad)
    # Aktienanalyse-Details (Akkordeons, Quartal/Jährlich, KGV-Historie, Finanzdaten) prüft scripts/clicktest_analyse.py
    pg.locator(".st-key-tabs button", has_text=re.compile("^Bewertung$")).click(); wait(pg, 3500)
    pl = pg.locator(".js-plotly-plot").first
    ok("Plotly: Hover aktiv, aber nicht ziehbar (dragmode aus, keine Werkzeugleiste)",
       pg.evaluate("() => { const g = document.querySelector('.js-plotly-plot'); return !!g && g._fullLayout.dragmode === false && !document.querySelector('.modebar-container .modebar-btn') && g._fullLayout.hovermode !== false; }"))
    pg.goto(BASE + "/?t=META&tab=Analysten", wait_until="networkidle"); wait(pg, 4500)
    ok("Neuladen: angemeldet, Tab Analysten bleibt", pg.locator('input[type="password"]').count() == 0 and "Einstufungen" in main(pg))
    pg.goto(BASE + "/?t=META", wait_until="networkidle"); wait(pg, 4500)
    fr = pg.frame_locator("iframe").first
    ok("Kurschart Übersicht: keine Einblendungen", fr.locator("#labs").count() == 0 and fr.locator("#rg button").count() == 6)
    fr.locator("#ty button", has_text="Kerzen").click(); wait(pg, 600); fr.locator("#rg button", has_text="5J").click(); wait(pg, 600)
    ok("Kurschart: Kerzen + 5J aktiv", "on" in (fr.locator("#ty button", has_text="Kerzen").get_attribute("class") or "") and "on" in (fr.locator("#rg button", has_text="5J").get_attribute("class") or ""))
    btn(pg, "Swing-Tool"); ok("'Im Swing-Tool öffnen' behält ?t=META", "swing-tool" in pg.url and "t=META" in pg.url)
    pg.reload(wait_until="networkidle"); wait(pg, 4500)
    ok("Neuladen Swing-Tool: angemeldet, META", pg.locator('input[type="password"]').count() == 0 and "Meta Platforms" in main(pg))
    btn(pg, "Aktienanalyse"); ok("'Aktienanalyse' behält ?t=META", "swing-tool" not in pg.url and "t=META" in pg.url)
    pg.go_back(); wait(pg, 3500); ok("Zurück: Swing-Tool mit ?t=META", "swing-tool" in pg.url and "t=META" in pg.url and "Meta Platforms" in main(pg))
    pg.go_forward(); wait(pg, 3500); ok("Vor: Aktienanalyse mit ?t=META", "swing-tool" not in pg.url and "t=META" in pg.url)
    for lab, part in (("Swing-Tool", "swing-tool"), ("Über das Projekt", "projekt"), ("Aktienanalyse", "aktienanalyse")):
        pg.locator(".st-key-topnav").get_by_role("link", name=lab, exact=True).click(); wait(pg)
        ok(f"Kopfzeile '{lab}' behält ?t=META", part in pg.url and "t=META" in pg.url)
    # Chancen-Board
    pg.goto(BASE + "/swing-tool", wait_until="networkidle"); wait(pg, 4500)
    n0 = pg.locator(".tbl").first.locator("tbody tr").count(); ok("Chancen-Board: 5 Kandidaten (Vollpool: 25 je Seite)", n0 == (25 if FULL else 5))
    TB = lambda lab: pg.locator(".st-key-tabs button", has_text=re.compile("^" + re.escape(lab)))
    ths = pg.locator(".btb thead th"); ok(f"Board: höchstens 7 Spalten, jede (außer Aktie) mit Info-i ({ths.count()})", ths.count() <= 7 and pg.locator(".btb thead th .ii").count() >= ths.count() - 1)
    labs = [t.strip() for t in pg.locator(".st-key-tabs button").all_inner_texts()]
    cnts = [int(re.search(r"\((\d+)\)", t_).group(1)) for t_ in labs if re.search(r"\((\d+)\)", t_)]
    ok(f"Board-Listen: keine leere und keine Dublette von 'Alle' {labs}", all(0 < n_ for n_ in cnts) and all(n_ < cnts[0] for n_ in cnts[1:]))
    for t_ in labs[1:]:
        pg.locator(".st-key-tabs button", has_text=t_).first.click(); wait(pg, 2500)
        n_ = int(re.search(r"\((\d+)\)", t_).group(1)); ok(f"Board-Liste '{t_}' zeigt {n_} Zeilen, ?liste=", pg.locator(".btb tbody tr").count() == (min(n_, 25) if FULL else n_) and "liste=" in pg.url)
    TB("Alle").click(); wait(pg, 3000)
    bt = main(pg); ok("Board: keine Fließtext-Erläuterung, kein 'öffnen', keine Bewertungsurteile", "Erläuterung der Spalten" not in bt and "öffnen" not in bt and "Zu teuer" not in bt and "Kaufbereit" not in bt)
    ok("Board: Marktlage kompakt in einer Zeile", pg.locator(".mline").count() == 1 and pg.locator(".mline").bounding_box()["height"] < 60)
    st_ = [x.strip() for x in pg.locator(".btb tbody tr td:nth-child(4)").all_inner_texts()]
    order = ["In Einstiegszone", "Nahe Einstiegszone", "Warten auf Rücksetzer", "Zahlen abwarten", "Trend nicht bestätigt", "Stopp unterschritten"]
    ok(f"Board: sortiert nach Status {st_}", [order.index(x) for x in st_] == sorted(order.index(x) for x in st_))
    for e in pg.locator("[data-testid=stExpander] summary").all(): e.click(); wait(pg, 1500)
    wait(pg, 2000); bt2 = pg.locator("[data-testid=stMain]").inner_html()
    ok("Board-Ausklapper: Zahlentermine, Rotationsdiagramm, Korrelation", all(x in bt2 for x in ("Stand Abendlauf", "Relative Stärke", "Korrelation der Tagesrenditen")) and pg.locator('[data-testid="stException"]').count() == 0)
    if FULL: pg.locator(".st-key-sb_q input").fill("MELI"); pg.keyboard.press("Enter"); wait(pg, 4000)
    pg.locator(".btb tbody tr", has_text="Mercado Libre").locator("td").nth(5).click(); wait(pg, 5000)
    ok("Board: Klick irgendwo in die Zeile öffnet die Aktie (MELI)", "t=MELI" in pg.url and "Mercado Libre" in main(pg))
    # Vollbild
    pg.goto(BASE + "/swing-tool?t=META&tab=Chart+und+Setup", wait_until="networkidle"); wait(pg, 5000)
    ifr = pg.locator("iframe").first; fr = pg.frame_locator("iframe").first
    fr.locator("#fs").click(); wait(pg, 1200)
    bb = ifr.bounding_box(); pg.screenshot(path=f"{OUT}/1440_swing_vollbild.png")
    ok("Vollbild: Chart füllt Fenster", bb and bb["width"] >= 1430 and bb["height"] >= 990)
    fr.locator("body").press("Escape"); wait(pg, 800); bb2 = ifr.bounding_box()
    ok("Vollbild: Esc schließt", bb2 and bb2["width"] < 1300)
    # v5.2: Zeitraumwechsel ohne Drift (20 Runden) + D1-Detailchart
    import hashlib as _hl
    pg.goto(BASE + "/swing-tool?t=NVDA&tab=Chart+und+Setup", wait_until="networkidle"); wait(pg, 6000)
    frm = [f for f in pg.frames if f.locator("#rg").count()][0]; ks = [x.inner_text() for x in frm.locator("#rg button").all()]
    ok("Swing-Chart: Zeitraum D1 Detail vorhanden", "D1 Detail" in ks)
    _first, _bad = {}, 0
    for _i in range(20):
        for _k in ks:
            frm.locator("#rg button", has_text=_k).first.click(); pg.mouse.move(5, 5); pg.wait_for_timeout(250 if _i else 900)
            _v = (frm.evaluate("document.body.dataset.view"), _hl.md5(frm.locator("#c").screenshot()).hexdigest())
            if _k not in _first: _first[_k] = _v
            elif _first[_k] != _v: _bad += 1
    ok(f"Swing-Chart: 20 Runden x {len(ks)} Zeiträume, Achsen und Bild identisch (Abweichungen {_bad})", _bad == 0 and all(_first[k][0] for k in ks))
    frm.locator("#rg button", has_text="D1 Detail").click(); pg.wait_for_timeout(700)
    _dv = __import__("json").loads(frm.evaluate("document.body.dataset.view")); _pl = _jj.load(open(DD + "/swing_plans.json"))["NVDA"]
    ok("D1 Detail: Tageskerzen 12 Monate, Stopp und Knock-out im festen Bereich", _dv[1] >= 200 and _dv[2] <= _pl["ko"] and "Tageskerzen, 12 Monate" in frm.locator("#lg").inner_text())
    pg.locator("iframe").first.screenshot(path=f"{OUT}/1440_swing_NVDA_D1.png")
    # NVDA-Chart
    pg.goto(BASE + "/swing-tool?t=NVDA&tab=Chart+und+Setup", wait_until="networkidle"); wait(pg, 4500)
    el = pg.locator("iframe").first; el.scroll_into_view_if_needed(); wait(pg, 1500); el.screenshot(path=f"{OUT}/1440_swing_NVDA_chart.png")
    txt = main(pg)
    _stp = f'{_jj.load(open(DD + "/swing_plans.json"))["NVDA"]["stop"]:.2f}'.replace(".", ",")
    ok(f"NVDA: Planleiste mit Stopp {_stp} und Ziel", _stp in txt and "Ziel" in txt)
    # Swing-Reiter: Inhalt, ?tab=, Urteil erst im letzten Reiter
    pg.goto(BASE + "/swing-tool?t=META", wait_until="networkidle"); wait(pg, 5000)
    ok("Swing META: erster Reiter 'Überblick' swing-bezogen (Trend/Setup/Zone/Timing), ohne Langfristiges", all(x in main(pg).upper() for x in ("SETUP", "EINSTIEGSZONE", "TIMING")) and "Tranche 1" not in main(pg) and "Fairer Wert" not in main(pg) and "Stressszenario" not in main(pg).split("Langfristige Sicht")[0])
    for tab, marker in (("Einstiegsplan", "Tranchen"), ("Hebel und Kosten", "Szenarien je Hebel"), ("Technik", "Relative Stärke zum S&P 500"),
                        ("Zahlen", "Kursreaktion am Tag nach den Zahlen"), ("Chart und Setup", "Chance/Risiko"), ("Überblick", "Einstiegszone")):
        pg.locator(".st-key-tabs button", has_text=re.compile("^" + tab + "$")).click(); wait(pg, 3500)
        ok(f"Swing-Reiter {tab}: Inhalt, ?tab=, ?t=META", marker.upper() in main(pg).upper() and "tab=" in pg.url and "t=META" in pg.url and pg.locator('[data-testid="stException"]').count() == 0)
    pg.goto(BASE + "/swing-tool?t=META&tab=Hebel+und+Kosten", wait_until="networkidle"); wait(pg, 5000)
    ok("Deep-Link ?tab=Hebel und Kosten", "Szenarien je Hebel" in main(pg))
    kv = lambda lab: pg.locator("table.tbl tbody tr", has_text="Turbo 3×").first.locator("td").nth(4).inner_text() or "0"
    n1 = int(kv("Stückzahl").replace(".", ""))
    f = pg.get_by_label("Kontogröße (USD)"); f.fill("50.000"); f.press("Enter"); wait(pg, 3500)
    n2 = int(kv("Stückzahl").replace(".", ""))
    ok(f"Hebel: Kontogröße 50.000 verdoppelt Stückzahl ({n1} -> {n2})", abs(n2 - 2 * n1) <= 1 and n1 > 0)
    f = pg.get_by_label("Risiko je Trade (%)"); f.fill("abc"); f.press("Enter"); wait(pg, 3000)
    ok("Hebel: ungültige Eingabe -> Hinweis, Rechnung läuft weiter", "Ungültig" in main(pg) and "Szenarien je Hebel" in main(pg))
    f.fill("1,0"); f.press("Enter"); wait(pg, 2500)
    ok("Hebel: Vergleich Aktie (Hebel 1,0×) und Turbo, Kostenbalken", pg.locator("table.tbl tbody tr", has_text="Aktie").first.locator("td").nth(1).inner_text().startswith("1,0×") and pg.locator(".js-plotly-plot").count() >= 2)
    ok("Hebel: Auszahlungsdiagramm ohne Werkzeugleiste", pg.locator(".js-plotly-plot").count() >= 1 and pg.locator(".modebar-container .modebar-btn").count() == 0)
    ok("Keine Exceptions", pg.locator('[data-testid="stException"]').count() == 0)
    pg2 = b.new_page(); pg2.goto(BASE + "/gibtsnicht?t=AMZN", wait_until="domcontentloaded"); pg2.get_by_text("Seite nicht gefunden").first.wait_for(timeout=8000)
    t1 = pg2.locator("body").inner_text(); ok("Unbekannte URL: deutsch", "Seite nicht gefunden" in t1 and "Page not found" not in t1)
    pg2.wait_for_timeout(4500); ok("Unbekannte URL: Weiterleitung mit ?t=AMZN", "gibtsnicht" not in pg2.url and "t=AMZN" in pg2.url)
    # Deep-Link mit Tab (angemeldet), Zurück behält Tab
    pg.goto(BASE + "/aktienanalyse?t=META&tab=Analysten", wait_until="networkidle"); wait(pg, 4500)
    ok("Deep-Link /aktienanalyse?t=META&tab=Analysten öffnet Tab Analysten", "Einstufungen" in main(pg) and "tab=Analysten" in pg.url and "t=META" in pg.url)
    pg.locator(".st-key-tabs button", has_text=re.compile("^Bewertung$")).click(); wait(pg, 3500)
    pg.go_back(); wait(pg, 4000)
    ok("Zurück nach Tabwechsel: wieder Analysten", "Einstufungen" in main(pg) and "tab=Analysten" in pg.url)
    pg.reload(wait_until="networkidle"); wait(pg, 4500)
    ok("Neuladen behält Tab Analysten", "Einstufungen" in main(pg))
    c4 = b.new_context(viewport={"width": 1440, "height": 1000}); p4 = c4.new_page()
    p4.goto(BASE + "/?t=NVDA&tab=Bewertung", wait_until="networkidle"); wait(p4, 2500)
    p4.fill('input[type="password"]', PW); p4.keyboard.press("Enter"); wait(p4, 5500)
    ok("Login über Deep-Link: Tab Bewertung + ?t=NVDA bleiben", ("Spanne pessimistisch" in main(p4) or "nicht belastbar" in main(p4)) and "t=NVDA" in p4.url and "tab=Bewertung" in p4.url)
    # META-Chart: keine überlappenden Preislabels
    pg.goto(BASE + "/swing-tool?t=META&tab=Chart+und+Setup", wait_until="networkidle"); wait(pg, 5000)
    fr = pg.frame_locator("iframe").first
    on0 = fr.locator("#chips .chip.on").count()
    ok("Chart und Setup: Schalter vorhanden, ruhige Vorgabe (Zonen, 50/200 Tage an)", fr.locator("#chips .chip").count() >= 6 and on0 == 3)
    fr.locator("#chips .chip", has_text="20-Tage").click(); wait(pg, 600)
    ok("Chart und Setup: Schalter 20-Tage schaltet ein", fr.locator("#chips .chip.on").count() == on0 + 1)
    ok("Chart und Setup: Planleiste mit Einstieg/Stopp/Ziel/CRV", all(x in main(pg) for x in ("Einstieg", "Stopp", "Ziel 1", "Chance/Risiko", "Abstand zur Zone")))
    pg.goto(BASE + "/swing-tool?t=META", wait_until="networkidle"); wait(pg, 5000)
    ok("Überblick ist Standardreiter mit 4 Schritten", pg.locator(".csteps .cs").count() == 4)
    pg.goto(BASE + "/swing-tool?t=META&tab=Investment-Case", wait_until="networkidle"); wait(pg, 4000)
    ok("Alter Deep-Link ?tab=Investment-Case landet auf Überblick", pg.locator(".csteps .cs").count() == 4 and "EINSTIEGSZONE" in main(pg).upper())
    pg.goto(BASE + "/", wait_until="networkidle"); wait(pg, 4000)
    ok("Startseite: kein 'öffnen'", "öffnen" not in main(pg))
    # Tageswerte: 'heute'/'Live' nur, wenn der Wert aus der laufenden Sitzung stammt (sonst 'Schluss TT.MM.')
    import datetime as _d
    _t = pg.locator("body").inner_text(); _today = _d.date.today().strftime("%d.%m.")
    _stale = [m for m in re.findall(r"(?:Schluss|Vortag) (\d\d\.\d\d\.)", _t) if m != _today]
    ok("Startseite: keine 'Heute'-Spalte, wenn Kurse vom Vortag", not (_stale and re.search(r"\tHeute\t|\nHeute\n", pg.locator(".otb").first.inner_text() if pg.locator(".otb").count() else "")))
    _lab = pg.locator(".ch-sub").last.inner_text() if pg.locator(".ch-sub").count() else ""
    ok("Startseite: Chart-Label 'Live' nur bei heutiger Sitzung", not ("Live" in _lab and _stale and "Stand" in _lab and pg.locator(".dtag", has_text="Schluss").count() and "Vortag" in main(pg)))
    pg.locator(".st-key-nav_off_invest a").first.click(); wait(pg, 4500)
    ok("Navigation Investment führt zu /investment", "/investment" in pg.url and "Langfristig investieren" in main(pg))
    pg.locator(".mstrip a.it", has_text="VIX").first.click(); wait(pg, 4500)
    ok("Marktleiste: Klick auf VIX -> Marktansicht ?m=VIX", "m=VIX" in pg.url and pg.locator('[data-testid="stException"]').count() == 0)
    # Investment-Bereich
    pg.goto(BASE + "/investment", wait_until="networkidle"); wait(pg, 4500)
    ok("Investment: Übersicht mit 5 Aktien (Vollpool: 25 je Seite), Nav-Eintrag aktiv", pg.locator(".btb tbody tr").count() == (25 if FULL else 5) and pg.locator(".st-key-nav_on_invest").count() == 1)
    if FULL: pg.locator(".st-key-ib_q input").fill("META"); pg.keyboard.press("Enter"); wait(pg, 4000)
    pg.locator(".btb tbody tr", has_text="Meta Platforms").locator("td").nth(3).click(); wait(pg, 5000)
    ok("Investment: Zeilenklick -> ?t=META, Überblick mit 4 Schritten", "investment" in pg.url and "t=META" in pg.url and pg.locator(".csteps .cs").count() == 4)
    for tab, marker in (("Tranchenplan", "Kaufniveaus im Kursverlauf"), ("Positionsgröße", "Zielposition"), ("Stressszenario", "Historischer Extremfall"), ("Unterstützungen", "Langfristige Unterstützungen"), ("Überblick", "Kaufniveaus")):
        pg.locator(".st-key-tabs button", has_text=re.compile("^" + tab + "$")).click(); wait(pg, 5500)
        ok(f"Investment-Reiter {tab}: Inhalt, ?tab=, ?t=META, kein Fehler", marker in main(pg) and "tab=" in pg.url and "t=META" in pg.url and pg.locator('[data-testid="stException"]').count() == 0)
    pg.goto(BASE + "/investment?t=META&tab=Tranchenplan", wait_until="networkidle"); wait(pg, 4500)
    _pl = _jj.load(open(DD + "/valuation_v4.json"))["stocks"]["META"]["invest_plan"]   # v5: Plan kommt aus der Engine
    ok(f"Investment: Tranchenplan mit {len(_pl['tranches'])} Stufen aus invest_plan, Deep-Link", pg.locator(".ivt tbody tr:not(.sum)").count() == len(_pl["tranches"]))
    import json as _jv; _v3 = _jv.load(open(DD + "/valuation_v4.json"))["stocks"]["META"]; _v2 = _v3["range"]
    _de0 = lambda x: f"{x:,.0f}".replace(",", ".")
    pg.goto(BASE + "/investment", wait_until="networkidle"); wait(pg, 4500)
    if FULL: pg.locator(".st-key-ib_q input").fill("META"); pg.keyboard.press("Enter"); wait(pg, 4000)
    ok("Investment v4: faire Spanne = pessimistisch–optimistisch aus valuation_v4.json", f"{_de0(_v2['pessimistic'])} – {_de0(_v2['optimistic'])}" in main(pg) and _de0(_v2["pessimistic"]) in main(pg))
    pg.goto(BASE + "/investment?t=META&tab=Tranchenplan", wait_until="networkidle"); wait(pg, 4500)
    _de2 = lambda x: f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    ok("Investment v5: alle Tranchen und Stopp = invest_plan aus valuation_v4.json", all(_de2(t["v"]) in main(pg) for t in _pl["tranches"]) and _de2(_pl["stop"]) in main(pg))
    pg.goto(BASE + "/swing-tool?t=META&tab=Ziele", wait_until="networkidle"); wait(pg, 4500)
    ok("Swing: Szenario-Tabelle nutzt fairen Wert v4", "Fairer Wert heute" not in main(pg) or _de0(_v2["base"]) in main(pg))
    pg.goto(BASE + "/investment?t=META&tab=Tranchenplan", wait_until="networkidle"); wait(pg, 4500)
    rng = lambda: pg.evaluate("() => [...document.querySelectorAll('.js-plotly-plot')].map(g => JSON.stringify([g._fullLayout.xaxis.range, g._fullLayout.yaxis.range, g._fullLayout.dragmode, g._fullLayout.xaxis.fixedrange]))")
    r0 = rng(); bb = pg.locator(".js-plotly-plot").first.bounding_box()
    pg.mouse.move(bb["x"] + bb["width"] * .5, bb["y"] + bb["height"] * .5); pg.mouse.down(); pg.mouse.move(bb["x"] + bb["width"] * .15, bb["y"] + bb["height"] * .8, steps=8); pg.mouse.up()
    pg.mouse.wheel(0, -600); wait(pg, 800)
    ok("Plotly (Tranchenplan): Ziehen/Scrollen ändert den sichtbaren Bereich nicht, Achsen fest", rng() == r0 and all(x.endswith('true]') for x in r0))
    import json as _j
    xr = _j.loads(r0[0])[0]; ok("Plotly Investment-Chart: rechts Luft nach dem letzten Datum", xr[1] > "2026-10-20")
    pg.goto(BASE + "/swing-tool?t=META&tab=Chart+und+Setup", wait_until="networkidle"); wait(pg, 5000)
    fr = pg.frames[-1] if False else next(f for f in pg.frames if f != pg.main_frame and f.evaluate("typeof chart") == "object")
    lr = lambda: fr.evaluate("JSON.stringify(chart.timeScale().getVisibleLogicalRange())")
    a0 = lr(); bb = pg.locator("iframe").first.bounding_box()
    pg.mouse.move(bb["x"] + bb["width"] * .5, bb["y"] + bb["height"] * .55); pg.mouse.down(); pg.mouse.move(bb["x"] + bb["width"] * .1, bb["y"] + bb["height"] * .55, steps=8); pg.mouse.up()
    pg.mouse.wheel(0, -600); wait(pg, 800)
    ok(f"Lightweight-Chart: Ziehen/Scrollen ändert den Bereich nicht ({a0})", lr() == a0)
    n_ = fr.evaluate("view().length"); ok("Lightweight-Chart: rechts ≥ 10 Balken Luft", _j.loads(a0)["to"] - (n_ - 1) >= 10)
    pg.goto(BASE + "/investment?t=META&tab=Stressszenario", wait_until="networkidle"); wait(pg, 4500)
    v0 = pg.locator("[class*=st-key-scardsel_] button").inner_text(); c0 = pg.locator(".js-plotly-plot").first.inner_text(); pg.locator(".st-key-scard_1 button").click(); wait(pg, 3500)
    ok("Stressszenario: Klick auf Karte wählt sie (roter Rahmen), wechselt Chart, keine Pills", pg.locator(".st-key-scardsel_1").count() == 1 and pg.locator("[class*=st-key-scardsel_] button").inner_text() != v0 and pg.locator(".js-plotly-plot").first.inner_text() != c0 and pg.locator(".st-key-stress_pick").count() == 0)
    pg.goto(BASE + "/investment?t=META&tab=Tranchenplan", wait_until="networkidle"); wait(pg, 4500)
    t_ = pg.locator(".js-plotly-plot").first.inner_text(); _w = [f"T{t['n']}" for t in _pl["tranches"]] + [f"{round(t['w'] * 100)} %" for t in _pl["tranches"]] + ["Stopp"]
    ok(f"Tranchenplan-Chart: T1–T{len(_pl['tranches'])} mit Gewicht und Stopp rechts beschriftet", all(x in t_ for x in _w) and "Stress" not in t_)
    pg.goto(BASE + "/investment?t=META&tab=Unterst%C3%BCtzungen", wait_until="networkidle"); wait(pg, 4500)
    ok("Unterstützungen: höchstens 4 Marken in Tabelle, nach Abstand sortiert, Details im Akkordeon", 1 <= pg.locator(".tbl").first.locator("tbody tr").count() <= 4 and pg.locator("[data-testid=stExpander]").count() >= 1)
    pg.goto(BASE + "/aktienanalyse?m=VIX", wait_until="networkidle"); wait(pg, 4500)
    h0 = main(pg); pg.locator("button", has_text=re.compile("^5J$")).click(); wait(pg, 3500)
    ok("Marktansicht VIX: Zeitraum-Pills 1M–5J, 5J wechselt Verlauf", all(pg.locator("button", has_text=re.compile(f"^{x}$")).count() for x in ("1M", "3M", "6M", "1J", "3J", "5J")) and "Verlauf 5J" in main(pg) and "Verlauf 1J" in h0)
    pg.goto(BASE + "/investment?t=META&tab=Positionsgr%C3%B6%C3%9Fe", wait_until="networkidle"); wait(pg, 4500)
    f = pg.get_by_label("Depotgröße (USD)"); f.fill("200.000"); f.press("Enter"); wait(pg, 3500)
    ok("Investment: Depotgröße 200.000 -> Zielposition 10.000 USD", "10.000 USD" in main(pg))
    for s_ in ("MELI", "GOOGL", "AMZN", "NVDA"):
        pg.goto(BASE + f"/investment?t={s_}&tab=Worst+Case", wait_until="networkidle"); wait(pg, 3500)
        _p5 = _jv.load(open(DD + "/valuation_v4.json"))["stocks"].get(s_, {}); _n5 = len([x for x in _p5["invest_plan"]["stress"] if x.get("v")]) if (_p5.get("invest_plan") or {}).get("available") and _p5.get("display_mode") == "value" else 1
        ok(f"Investment {s_}: alter Link Worst Case -> Stressszenario, {_n5} Karte(n) aus invest_plan, erste gewählt", pg.locator("[class*=st-key-scard] button").count() == _n5 and pg.locator(".st-key-scardsel_0").count() == 1 and pg.locator('[data-testid="stException"]').count() == 0)
    pg.screenshot(path=f"{OUT}/1440_swing_META_case.png", full_page=True)
    # Login direkt auf einer Unterseite: Pfad und ?t= bleiben, danach Neuladen ohne Login
    c3 = b.new_context(viewport={"width": 1440, "height": 1000}); p3 = c3.new_page()
    p3.goto(BASE + "/swing-tool?t=META", wait_until="networkidle"); wait(p3, 2500)
    p3.fill('input[type="password"]', PW); p3.keyboard.press("Enter"); wait(p3, 5000)
    ok("Login auf /swing-tool?t=META bleibt dort", "swing-tool" in p3.url and "t=META" in p3.url and "Meta Platforms" in main(p3))
    p3.reload(wait_until="networkidle"); wait(p3, 4500)
    ok("Danach Neuladen: weiter angemeldet", p3.locator('input[type="password"]').count() == 0)
    b.close()
for r in res: print(r[1], "-", r[0])
print(sum(r[1] == "pass" for r in res), "/", len(res))
