"""Fetch SEC companyfacts for a ticker list into valuation/cache/companyfacts/<T>.json.gz (public API,
fair-access UA, <=8 req/s). CIK: scanner map (read-only) + demo-local supplement from SEC company_tickers*.json."""
import gzip, json, sys, time, urllib.request
from pathlib import Path
UA = __import__("os").environ.get("SEC_USER_AGENT", "your-name your@email.com")
HERE = Path(__file__).parent; CACHE = HERE / "cache" / "companyfacts"; SUPP = HERE / "data" / "cik_supp.json"
SCANNER_MAP = Path(__import__("os").environ.get("MARKET_STORE", "data_store") + "/derived/edgar_cik_map.json")


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=60) as r:
        b = r.read()
        return gzip.decompress(b) if r.headers.get("Content-Encoding") == "gzip" else b


def cik_map():
    m = json.loads(SCANNER_MAP.read_text())
    if not SUPP.exists():
        s = {}
        for u in ("https://www.sec.gov/files/company_tickers.json", "https://www.sec.gov/files/company_tickers_exchange.json"):
            d = json.loads(_get(u)); time.sleep(.2)
            if "fields" in d:
                i, j = d["fields"].index("cik"), d["fields"].index("ticker")
                for row in d["data"]: s.setdefault(row[j].upper(), f"{int(row[i]):010d}")
            else:
                for v in d.values(): s.setdefault(v["ticker"].upper(), f"{int(v['cik_str']):010d}")
        SUPP.write_text(json.dumps(s))
    s = json.loads(SUPP.read_text())
    return {**{k.replace(".", "-"): v for k, v in s.items()}, **s, **m}


def fetch(tickers):
    m = cik_map(); CACHE.mkdir(parents=True, exist_ok=True); ok, miss = 0, []
    for t in tickers:
        c = m.get(t) or m.get(t.replace("-", "."))
        if not c: miss.append(t); continue
        p = CACHE / f"{t}.json.gz"
        if p.exists(): ok += 1; continue
        try:
            b = _get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(c):010d}.json"); p.write_bytes(gzip.compress(b)); ok += 1
        except Exception as e:
            miss.append(f"{t}:{e}")
        time.sleep(.15)
    return ok, miss


if __name__ == "__main__":
    ts = sys.argv[1:]
    if ts == ["--missing"]:
        d = json.loads((HERE.parent / "data" / "valuation_v3.json").read_text())["stocks"]
        ts = [t for t, r in d.items() if r.get("status") == "keine EDGAR-Daten"]
    print(fetch(ts))
