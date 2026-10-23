"""Successor registrants (holding reorganisations, e.g. a new 'Holdings' CIK taking over the ticker): when the ticker's
CIK has < 4 periodic reports, find the predecessor by normalised registrant name (EDGAR entity search), require a
10-K history ending within 24 months of the successor's first report, and merge companyfacts (successor wins on
identical periods). General rule, no ticker list."""
from __future__ import annotations
import gzip, json, re, time, urllib.parse
from pathlib import Path
from .edgar_fetch import _get, cik_map, CACHE as CF
SUFFIX = r"\b(holdings?|corp(oration)?|inc|incorporated|group|plc|ltd|limited|co|company|new|the)\b"


def norm(n):
    return re.sub(r"[^a-z]", "", re.sub(SUFFIX, "", re.sub(r"\(.*?\)", "", n.lower())))


def _sub(cik):
    return json.loads(_get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"))


def find(t):
    c = cik_map().get(t)
    if not c:
        return None, "keine CIK"
    s = _sub(c); r = s["filings"]["recent"]
    per = [d for f, d in zip(r["form"], r["filingDate"]) if f in ("10-K", "10-Q", "20-F", "40-F")]
    if len(per) >= 4:
        return None, "eigene Historie ausreichend"
    first = min(per) if per else max(r["filingDate"])
    stem = norm(s["name"])
    q = urllib.parse.quote(re.sub(r"[^A-Za-z ]", "", s["name"]).split()[0][:5])
    hits = json.loads(_get(f"https://efts.sec.gov/LATEST/search-index?keysTyped={q}"))["hits"]["hits"]
    best = None
    for h in hits:
        cid = h["_id"]
        if int(cid) == int(c) or norm(h["_source"]["entity"]) != stem:
            continue
        time.sleep(.15); s2 = _sub(cid); r2 = s2["filings"]["recent"]
        ks = [d for f, d in zip(r2["form"], r2["filingDate"]) if f == "10-K"]
        if ks and (int(first[:4]) - int(max(ks)[:4])) <= 2 and (best is None or len(ks) > best[1]):
            best = (cid, len(ks), s2["name"])
    return (best, "ok") if best else (None, "kein Vorgänger gefunden")


def merge(t):
    b, why = find(t)
    if not b:
        return why
    c_new = cik_map()[t]
    new = json.loads(_get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(c_new):010d}.json"))
    old = json.loads(_get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(b[0]):010d}.json"))
    for tax, tags in old["facts"].items():
        nt = new["facts"].setdefault(tax, {})
        for tag, v in tags.items():
            if tag not in nt:
                nt[tag] = v; continue
            for u, rows in v["units"].items():
                have = {(x.get("start"), x["end"]) for x in nt[tag]["units"].get(u, [])}
                nt[tag]["units"].setdefault(u, []).extend(x for x in rows if (x.get("start"), x["end"]) not in have)
    new["predecessor"] = dict(cik=b[0], name=b[2])
    (CF / f"{t}.json.gz").write_bytes(gzip.compress(json.dumps(new).encode()))
    return f"ok: Vorgänger {b[2]} (CIK {b[0]}, {b[1]} 10-K)"
