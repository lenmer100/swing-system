"""Klicktest Investment: Tranchenplan, Stressszenario (Karten klickbar), Unterstützungen für 8 Aktien."""
import os, re, sys
def _settle(pg, ms=25000):
    """Warten, bis Streamlit fertig gerendert hat (Statusanzeige weg), höchstens 25 s; unter Last brauchen Tabs bis ~15 s."""
    try: pg.wait_for_function("!document.querySelector('[data-testid=stStatusWidget]')", timeout=ms)
    except Exception: pass
    pg.wait_for_timeout(800)
from playwright.sync_api import sync_playwright
BASE = os.environ.get("BASE", "http://127.0.0.1:8512"); PW = __import__("os").environ["DEMO_PASSWORD"]
OUT = "./screenshots/ui_invest"; SYMS = (sys.argv[1] if len(sys.argv) > 1 else "META,GOOGL,KO,JPM,NVDA,NBIS,SAP,PLD").split(",")
res = []
def ok(n, c): res.append((n, "pass" if c else "FAIL"))
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_context(viewport={"width": 1440, "height": 1000}).new_page()
    pg.goto(BASE, wait_until="networkidle"); pg.wait_for_timeout(2500)
    pg.fill('input[type="password"]', PW); pg.keyboard.press("Enter"); pg.wait_for_timeout(4000)
    M = lambda: pg.locator("[data-testid=stMain]")
    for s in SYMS:
        for tab, slug in (("Tranchenplan", "tranchen"), ("Stressszenario", "stress"), ("Unterstützungen", "support")):
            pg.goto(f"{BASE}/investment?t={s}&tab={tab}", wait_until="networkidle"); pg.wait_for_timeout(2500); _settle(pg)
            exc = pg.locator('[data-testid="stException"]').count()
            ok(f"{s} {tab}: keine Exception", exc == 0)
            M().screenshot(path=f"{OUT}/{s}_{slug}.png")
            if tab == "Tranchenplan":
                t = M().inner_text(); ok(f"{s} Tranchen: Plan oder leerer Zustand", ("Tranche 1" in t) or ("Kein Tranchenplan" in t))
            if tab == "Stressszenario" and pg.locator("[class*=st-key-scard_] button").count():
                v0 = pg.locator("[class*=st-key-scardsel_] button").inner_text()
                pg.locator("[class*=st-key-scard_] button").first.click(); pg.wait_for_timeout(2000); _settle(pg)
                v1 = pg.locator("[class*=st-key-scardsel_] button").inner_text()
                ok(f"{s} Stress: Klick auf Karte wechselt Auswahl", v0 != v1)
                M().screenshot(path=f"{OUT}/{s}_stress_klick.png")
    b.close()
for n, r in res: print(r, n)
print(sum(r == "pass" for _, r in res), "/", len(res))
