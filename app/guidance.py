"""Letzte Guidance aus SEC EDGAR: jüngstes 8-K mit Item 2.02 (Ergebnisse), Exhibit 99.1 (Pressemitteilung).
Feste Regeln: Satz enthält ein Ausblick-Wort (expect, outlook, guidance, anticipate, project, forecast, sees) UND eine Kennzahl
(revenue, net sales, sales, earnings per share, EPS) UND eine Spanne (X to/– Y, between X and Y) oder "plus or minus N %".
Nur US-Emittenten mit 8-K. Ohne Treffer: nichts anzeigen."""
import json, re, time, html as H
from pathlib import Path
import urllib.request

UA = __import__("os").environ.get("SEC_USER_AGENT", "your-name your@email.com")
CACHE = Path(__file__).parent / "data" / "edgar_cache"; CACHE.mkdir(exist_ok=True)
_last = [0.0]

def _get(url, ttl=86400):
    f = CACHE / re.sub(r"[^A-Za-z0-9]+", "_", url)[-180:]
    if f.exists() and time.time() - f.stat().st_mtime < ttl: return f.read_text(errors="ignore")
    wait = 0.15 - (time.time() - _last[0])        # SEC: höchstens 10 Anfragen/s
    if wait > 0: time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
    t = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore"); _last[0] = time.time()
    f.write_text(t); return t

def cik(sym):
    m = json.loads(_get("https://www.sec.gov/files/company_tickers.json", ttl=7 * 86400))
    s = sym.replace(".", "-").upper()
    return next((int(v["cik_str"]) for v in m.values() if v["ticker"].upper() == s), None)

KPI = r"(revenue|revenues|net sales|sales|earnings per share|\beps\b)"
DASH = "[-–—‑−]"
NUMW = r"(\d[\d,.]*|one|two|three|four|five|six|seven|eight|nine|ten|in-line|flat)"
EXCL = r"(headwind|tailwind|basis points|tax rate|forward-looking|capital expenditure|share repurchase|dividend)"
TABLE = r"(Net sales|Total revenues?|Revenues?|Sales|Diluted earnings per share|Adjusted earnings per share|Non-GAAP earnings per share|EPS)[^$~\d]{0,40}~?\$\s?[\d,.]+\s*(billion|million)?\s*" + DASH + r"\s*~?\$?\s?[\d,.]+\s*(billion|million)?"
CUE = r"\b(expect|expects|expected|outlook|guidance|anticipate|anticipates|project|projects|forecast|sees|range of)\b"
RNG = r"(\$?" + NUMW + r"\s*(billion|million)?\s*(to|and|" + DASH + r")\s*\$?" + NUMW + r"\s*(billion|million|%|percent)?|plus or minus\s*\d+(\.\d+)?\s*%)"

def _text(raw):
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw); t = re.sub(r"(?s)<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", H.unescape(t)).replace("\xa0", " ")

def latest(sym):
    """dict(date, url, sentences[]) oder None."""
    c = cik(sym)
    if not c: return None
    sub = json.loads(_get(f"https://data.sec.gov/submissions/CIK{c:010d}.json"))
    r = sub["filings"]["recent"]
    for i, form in enumerate(r["form"]):
        if form != "8-K" or "2.02" not in (r.get("items") or [""] * len(r["form"]))[i]: continue
        acc = r["accessionNumber"][i].replace("-", ""); base = f"https://www.sec.gov/Archives/edgar/data/{c}/{acc}/"
        idx = json.loads(_get(base + "index.json", ttl=30 * 86400))
        names = [x["name"] for x in idx["directory"]["item"]]
        htm = [n for n in names if n.lower().endswith((".htm", ".html")) and "index" not in n.lower() and not re.match(r"R\d+\.htm", n)]
        ex = next((n for n in htm if re.search(r"99[-_.]?0?1|991|exhibit99", n, re.I)), None) or next((n for n in htm if re.search(r"(^|[^a-z])pr\.htm|press|release|earn", n, re.I)), None)
        extra = [n for n in htm if re.search(r"commentary|cfo|outlook", n, re.I) and n != ex]
        if not ex: return dict(date=r["filingDate"][i], url=base, sentences=[])
        url = base + ex; out = []
        for u in [url] + [base + n for n in extra]:
            t = _text(_get(u, ttl=30 * 86400))
            for s in re.split(r"(?<=[.;])\s+(?=[A-Z•0-9])|•", t):
                s = s.strip()
                if 30 < len(s) < 420 and re.search(CUE, s, re.I) and re.search(KPI, s, re.I) and re.search(RNG, s, re.I) and not re.search(EXCL, s, re.I):
                    if s not in out: out.append(s)
            m = re.search(r"(Financial Outlook|Outlook|Guidance)(.{0,1500})", t)
            if m and not out:   # Ausblick als Tabelle (z. B. LMT): erste Spalte = aktuelle Spanne
                for x in re.finditer(TABLE, m.group(2)):
                    if x.group(0) not in out: out.append(x.group(0).strip())
        out = [re.sub(r"^(\d+\s+)?([A-Z][\w&-]*\s+){0,5}(Commentary|Guidance|Outlook)\s+(?=[A-Z])", "", s) for s in out]
        tbl = any(re.match(TABLE, s) for s in out) and "in millions" in t
        return dict(date=r["filingDate"][i], url=url, sentences=out[:4], millions=tbl)
    return None
