"""Debt fallback chain (v4, audit CYC fix 1). Point-in-time from SEC companyconcept API, demo-local cache
valuation/cache/debt/<T>.parquet. Used when the base data have total_debt missing or 0.
Chain (first that exists at the as-of date wins):
 1 LongTermDebt (incl. current portion)
 2 LongTermDebtNoncurrent + (LongTermDebtCurrent or DebtCurrent)
 3 LongTermDebtAndCapitalLeaseObligations + LongTermDebtAndCapitalLeaseObligationsCurrent
 4 DebtLongtermAndShorttermCombinedAmount
 5 DebtInstrumentCarryingAmount
 6 ConvertibleNotesPayable + ConvertibleNotesPayableCurrent; SeniorNotes; NotesPayable
 + ShortTermBorrowings and CommercialPaper are added to 1-6 when reported separately.
Captive finance (audit C2): finance receivables (FinancingReceivable..., NotesAndLoansReceivableNetNoncurrent/Current)."""
import json, time, urllib.request, urllib.error, functools
from pathlib import Path
import pandas as pd
from .edgar_fetch import cik_map, UA
CACHE = Path(__file__).parent / "cache" / "debt"
TAGS = ["LongTermDebt", "LongTermDebtNoncurrent", "LongTermDebtCurrent", "DebtCurrent", "LongTermDebtAndCapitalLeaseObligations",
        "LongTermDebtAndCapitalLeaseObligationsCurrent", "DebtLongtermAndShorttermCombinedAmount", "DebtInstrumentCarryingAmount",
        "ConvertibleNotesPayable", "ConvertibleNotesPayableCurrent", "SeniorNotes", "NotesPayable", "ShortTermBorrowings", "CommercialPaper",
        "FinancingReceivableExcludingAccruedInterestAfterAllowanceForCreditLoss", "NotesAndLoansReceivableNetNoncurrent",
        "NotesAndLoansReceivableNetCurrent", "Assets", "InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt"]


def _concept(cik, tag):
    url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{int(cik):010d}/us-gaap/{tag}.json"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
            u = json.load(r)["units"]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    k = "USD" if "USD" in u else max(u, key=lambda x: len(u[x]))
    d = pd.DataFrame(u[k]); d["tag"] = tag
    return d


def build(tickers, refresh=False):
    m = cik_map(); CACHE.mkdir(parents=True, exist_ok=True); n = 0
    for t in tickers:
        p = CACHE / f"{t}.parquet"; c = m.get(t) or m.get(t.replace("-", "."))
        if not c or (p.exists() and not refresh):
            continue
        parts = []
        for tag in TAGS:
            try:
                d = _concept(c, tag)
            except Exception as ex:
                print(t, tag, ex); d = None
            if d is not None:
                parts.append(d)
            time.sleep(.11)
        cols = ["tag", "start", "end", "val", "filed", "form", "fp"]
        df = pd.concat(parts) if parts else pd.DataFrame(columns=cols)
        for k in cols:
            if k not in df: df[k] = None
        df = df[cols]; df["end"] = pd.to_datetime(df.end); df["filed"] = pd.to_datetime(df.filed); df["start"] = pd.to_datetime(df.start)
        df.to_parquet(p); n += 1
    return n


@functools.lru_cache(None)
def _load(t):
    p = CACHE / f"{t}.parquet"
    return pd.read_parquet(p) if p.exists() else None


def _inst(d, tag, asof):
    x = d[(d.tag == tag) & (d.filed <= asof) & d.start.isna()]
    if not len(x):
        return None, None
    e = x.end.max()
    if (asof - e).days > 456:
        return None, None
    return float(x[x.end == e].sort_values("filed").val.iloc[-1]), e


def debt_asof(t, asof):
    """-> dict(total_debt, source, fin_receivables, total_assets, interest_ttm) or None."""
    d = _load(t)
    if d is None or not len(d):
        return None
    a = pd.Timestamp(asof); g = lambda tag: _inst(d, tag, a)[0]
    ltd = g("LongTermDebt"); src = None; tot = None
    if ltd is not None:
        tot, src = ltd, "LongTermDebt"
    elif g("LongTermDebtNoncurrent") is not None:
        tot = g("LongTermDebtNoncurrent") + (g("LongTermDebtCurrent") or g("DebtCurrent") or 0); src = "LongTermDebtNoncurrent+Current"
    elif g("LongTermDebtAndCapitalLeaseObligations") is not None:
        tot = g("LongTermDebtAndCapitalLeaseObligations") + (g("LongTermDebtAndCapitalLeaseObligationsCurrent") or 0); src = "LongTermDebtAndCapitalLeaseObligations"
    elif g("DebtLongtermAndShorttermCombinedAmount") is not None:
        tot, src = g("DebtLongtermAndShorttermCombinedAmount"), "DebtLongtermAndShorttermCombinedAmount"
    elif g("DebtInstrumentCarryingAmount") is not None:
        tot, src = g("DebtInstrumentCarryingAmount"), "DebtInstrumentCarryingAmount"
    else:
        cv = (g("ConvertibleNotesPayable") or 0) + (g("ConvertibleNotesPayableCurrent") or 0) + (g("SeniorNotes") or 0) + (g("NotesPayable") or 0)
        if cv:
            tot, src = cv, "Convertible/Senior/NotesPayable"
    if tot is not None and src != "DebtLongtermAndShorttermCombinedAmount":
        tot += (g("ShortTermBorrowings") or 0) + (g("CommercialPaper") or 0)
    fr = g("FinancingReceivableExcludingAccruedInterestAfterAllowanceForCreditLoss")
    if fr is None:
        nr = (g("NotesAndLoansReceivableNetNoncurrent") or 0) + (g("NotesAndLoansReceivableNetCurrent") or 0)
        fr = nr or None
    # interest expense TTM (duration facts): last 4 quarters if available, else last FY
    it = None
    x = d[d.tag.isin(["InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt"]) & (d.filed <= a) & d.start.notna()]
    if len(x):
        x = x.assign(days=(x.end - x.start).dt.days)
        fy = x[x.days > 330].sort_values("end")
        if len(fy) and (a - fy.end.iloc[-1]).days <= 456:
            it = float(fy.val.iloc[-1])
    return dict(total_debt=tot, source=src, fin_receivables=fr, total_assets=g("Assets"), interest=it)
