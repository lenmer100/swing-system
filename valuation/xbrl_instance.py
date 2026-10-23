"""Latest 10-K/10-Q/20-F/40-F XBRL instance per ticker (SEC Archives, public). Gives what companyfacts lacks:
custom-tag facts (F/GM debt) and dimensional facts (revenue by geography for country risk).
Cache: valuation/cache/xbrl/<T>.parquet with name, value, end, start, dims (axis=member;...)."""
from __future__ import annotations
import json, re, sys, time
from pathlib import Path
import pandas as pd
from .edgar_fetch import _get, cik_map
CACHE = Path(__file__).parent / "cache" / "xbrl"
FORMS = ("10-K", "10-Q", "20-F", "40-F")


def _latest(cik, annual=False):
    s = json.loads(_get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"))["filings"]["recent"]
    for f, a, d in zip(s["form"], s["accessionNumber"], s["filingDate"]):
        if f in (("10-K", "20-F", "40-F") if annual else FORMS):
            return f, a, d
    return None


def _instance_url(cik, acc):
    base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}"
    idx = json.loads(_get(base + "/index.json"))["directory"]["item"]
    xs = [i["name"] for i in idx if i["name"].endswith("_htm.xml")]
    if not xs:
        xs = [i["name"] for i in idx if i["name"].endswith(".xml") and not re.search(r"(FilingSummary|_cal|_def|_lab|_pre)", i["name"])]
    return base + "/" + xs[0] if xs else None


def parse(xml: str):
    ctx = {}
    for m in re.finditer(r"<(?:xbrli:)?context\b[^>]*id=\"([^\"]+)\"[^>]*>(.*?)</(?:xbrli:)?context>", xml, re.S):
        cid, body = m.group(1), m.group(2)
        inst = re.search(r"<(?:xbrli:)?instant>([^<]+)<", body); st = re.search(r"<(?:xbrli:)?startDate>([^<]+)<", body)
        en = re.search(r"<(?:xbrli:)?endDate>([^<]+)<", body)
        dims = ";".join(f"{a}={b.strip()}" for a, b in re.findall(r"dimension=\"([^\"]+)\"[^>]*>([^<]+)<", body))
        ctx[cid] = (inst.group(1) if inst else (en.group(1) if en else None), st.group(1) if st else None, dims)
    rows = []
    for m in re.finditer(r"<([A-Za-z0-9\-]+:[A-Za-z0-9_]+)\b([^>]*?)contextRef=\"([^\"]+)\"([^>]*)>([^<]*)</\1>", xml):
        name, a1, cid, a2, val = m.groups()
        attrs = a1 + a2
        if "unitRef" not in attrs:
            continue
        try:
            v = float(val.strip())
        except ValueError:
            continue
        sc = re.search(r"scale=\"(-?\d+)\"", attrs)
        if sc and "ix:" in name:
            v *= 10 ** int(sc.group(1))
        e, s, d = ctx.get(cid, (None, None, ""))
        rows.append((name, v, e, s, d))
    df = pd.DataFrame(rows, columns=["name", "value", "end", "start", "dims"])
    df["end"] = pd.to_datetime(df.end, errors="coerce"); df["start"] = pd.to_datetime(df.start, errors="coerce")
    return df.drop_duplicates()


def build(tickers, annual=False, refresh=False):
    m = cik_map(); CACHE.mkdir(parents=True, exist_ok=True); res = {}
    for t in tickers:
        p = CACHE / f"{t}{'_k' if annual else ''}.parquet"
        if p.exists() and not refresh:
            res[t] = "cached"; continue
        c = m.get(t) or m.get(t.replace("-", ".")) or m.get(t.replace("-", ""))
        if not c:
            res[t] = "keine CIK"; continue
        try:
            lf = _latest(c, annual)
            if not lf:
                res[t] = "kein Filing"; continue
            u = _instance_url(c, lf[1]); time.sleep(.12)
            if not u:
                res[t] = "keine Instanz"; continue
            df = parse(_get(u).decode("utf-8", "ignore")); df["form"], df["filed"] = lf[0], lf[2]
            df.to_parquet(p); res[t] = f"ok {lf[0]} {len(df)}"
        except Exception as ex:
            res[t] = f"Fehler {type(ex).__name__}"
        time.sleep(.12)
    return res


def load(t, annual=False):
    p = CACHE / f"{t}{'_k' if annual else ''}.parquet"
    return pd.read_parquet(p) if p.exists() else None


if __name__ == "__main__":
    print(build(sys.argv[1:]))


DEBT_SETS = [("us-gaap:DebtLongtermAndShorttermCombinedAmount",),
             ("us-gaap:LongTermDebtAndCapitalLeaseObligations", "us-gaap:LongTermDebtAndCapitalLeaseObligationsCurrent", "us-gaap:ShortTermBorrowings", "us-gaap:CommercialPaper"),
             ("us-gaap:LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities", "us-gaap:ShortTermBorrowings", "us-gaap:CommercialPaper"),
             ("us-gaap:LongTermDebtNoncurrent", "us-gaap:LongTermDebtCurrent", "us-gaap:ShortTermBorrowings", "us-gaap:CommercialPaper"),
             ("us-gaap:LongTermDebt", "us-gaap:ShortTermBorrowings", "us-gaap:CommercialPaper"),
             ("us-gaap:DebtCurrent", "us-gaap:LongTermDebtNoncurrent"),
             ("us-gaap:LongTermDebtAndCapitalLeaseObligations", "us-gaap:DebtCurrent"),
             ("us-gaap:NotesAndLoansPayable", "us-gaap:OtherShortTermBorrowings", "us-gaap:LongTermDebtAndCapitalLeaseObligations"),
             ("us-gaap:DebtInstrumentCarryingAmount",)]
FIN_SEG = re.compile(r"(Credit|Financ|Capital|Bank)", re.I)
SEG_AXIS = "us-gaap:StatementBusinessSegmentsAxis"


def _combine(v):
    """v: {tag(no prefix): value}. -> (total, parts) or None. Noncurrent + current + short-term borrowings, no double count."""
    for k in ("DebtLongtermAndShorttermCombinedAmount", "LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities"):
        if k in v:
            return v[k], [k]
    nc = next((k for k in ("LongTermDebtAndCapitalLeaseObligations", "LongTermDebtNoncurrent", "LongTermDebt", "NotesAndLoansPayable",
                           "DebtInstrumentCarryingAmount") if k in v), None)
    cur = next((k for k in ("LongTermDebtAndCapitalLeaseObligationsCurrent", "LongTermDebtCurrent", "DebtCurrent") if k in v), None)
    if nc is None and cur is None:
        return None
    parts = [k for k in (nc, cur) if k]
    if cur != "DebtCurrent" and nc != "LongTermDebt":
        parts += [k for k in ("ShortTermBorrowings", "CommercialPaper", "OtherShortTermBorrowings") if k in v]
    return float(sum(v[k] for k in parts)), parts


def debt(t):
    """-> dict(total, finance, source, end) from the latest instance: undimensioned facts first; if the filer reports
    debt only by business segment (Ford, GM), sum the members and split off finance segments (Credit/Financial)."""
    d = load(t)
    if d is None or not len(d):
        return None
    e = d[d.start.isna()].end.value_counts().idxmax()          # balance-sheet date = most frequent instant
    x = d[(d.end == e) & d.start.isna() & d.name.str.startswith("us-gaap:")].assign(tag=lambda z: z.name.str.split(":").str[1])
    r = _combine(x[x.dims == ""].groupby("tag").value.max().to_dict())
    if r:
        return dict(total=r[0], finance=0.0, source="Instanz: " + "+".join(r[1]), end=str(e.date()))
    seg = x[x.dims.str.match(r"^[^;=]*(Segment|Business|Group)[^;=]*Axis=[^;]+$")]
    per = {}
    for mem, g in seg.assign(mem=seg.dims.str.split("=").str[1]).groupby("mem"):
        rr = _combine(g.groupby("tag").value.max().to_dict())
        if rr:
            per[mem] = rr[0]
    if not per:
        return None
    fin = sum(v for m, v in per.items() if FIN_SEG.search(m) and not re.search(r"Excluding|Automotive|Industrial", m, re.I))
    return dict(total=float(sum(per.values())), finance=float(fin), end=str(e.date()),
                source="Instanz je Segment: " + ", ".join(f"{m.split(':')[-1]} {v / 1e9:.1f} Mrd." for m, v in per.items()))
