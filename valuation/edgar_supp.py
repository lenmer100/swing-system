"""Demo-local supplementary point-in-time fundamentals from SEC companyfacts, for names whose scanner fund_pit
has no usable revenue/operating-income TTM (foreign 20-F/40-F filers with annual or semiannual data only,
US filers without OperatingIncomeLoss). Does not touch the scanner's data store.

TTM per period end E: a ~12-month fact ending at E, else FY(prev) + YTD(E) - YTD(E-1y) (10-Q quarters or 6-K halves
if tagged). PIT = first 'filed' date. Rows are put on a quarterly grid (value = latest filing available by then),
so '12 rows = 3 years' holds as in fund_pit. Non-USD reporting currency -> USD at the FX rate on the availability date.
EBIT fallback: pre-tax income + interest expense (documented). ADR: shares scaled to Yahoo sharesOutstanding when the
ratio is outside 0.8-1.25 (ADR ratio). Flag only_annual when the latest TTM comes from an annual report."""
from __future__ import annotations
import gzip, json, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).parent; CF = HERE / "cache" / "companyfacts"; OUT = HERE / "cache" / "fund_supp"
FX = Path(__import__("os").environ.get("MARKET_STORE", "data_store") + "/derived/v35_fx"); YFI = Path(__import__("os").environ.get("MARKET_STORE", "data_store") + "/derived/yf_info")

DUR = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "RevenueFromContractWithCustomerIncludingAssessedTax",
                "SalesRevenueNet", "RevenuesNetOfInterestExpense", "Revenue", "RevenueFromContractsWithCustomers"],
    "opinc": ["OperatingIncomeLoss", "ProfitLossFromOperatingActivities"],
    "pretax": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
               "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments", "ProfitLossBeforeTax"],
    "interest": ["InterestExpense", "InterestExpenseNonoperating", "FinanceCosts"],
    "ni": ["NetIncomeLoss", "ProfitLossAttributableToOwnersOfParent", "ProfitLoss"],
    "ocf": ["NetCashProvidedByUsedInOperatingActivities", "CashFlowsFromUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
              "PurchaseOfPropertyPlantAndEquipment"],
    "sbc": ["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense", "AdjustmentsForSharebasedPayments"],
    "dna": ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization", "DepreciationAmortisationAndImpairmentLossReversalOfImpairmentLossRecognisedInProfitOrLoss", "DepreciationAndAmortisationExpense"],
    "shares": ["WeightedAverageNumberOfDilutedSharesOutstanding", "WeightedAverageNumberOfSharesOutstandingDiluted",
               "AdjustedWeightedAverageShares", "WeightedAverageShares"],
}
INST = {
    "equity": ["StockholdersEquity", "EquityAttributableToOwnersOfParent", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest", "Equity"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue", "CashAndCashEquivalents", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "debt_lt": ["LongTermDebtNoncurrent", "NoncurrentPortionOfNoncurrentBorrowings", "LongTermBorrowings", "NoncurrentBorrowings",
                "LongtermBorrowings", "NoncurrentPortionOfNoncurrentBondsIssued", "NoncurrentBondsIssued"],
    "debt_cur": ["LongTermDebtCurrent", "CurrentPortionOfNoncurrentBorrowings", "ShortTermBorrowings", "CurrentBorrowings", "CommercialPaper",
                 "ShorttermBorrowings", "CurrentPortionOfLongtermBorrowings", "CurrentBondsIssuedAndCurrentPortionOfNoncurrentBondsIssued"],
    "debt_tot": ["LongTermDebt", "Borrowings", "DebtInstrumentCarryingAmount"],
}


def _facts(t):
    p = CF / f"{t}.json.gz"
    if not p.exists():
        return None
    f = json.loads(gzip.decompress(p.read_bytes()))["facts"]
    out = {}
    for tax in ("us-gaap", "ifrs-full"):
        for k, v in f.get(tax, {}).items():
            out.setdefault(k, v)
    return out


def _rows(facts, tags, shares=False):
    """Facts of all tags merged per (start,end) in priority order (first tag wins), one currency, first-filed (PIT)."""
    parts, cur = [], None
    for pri, tag in enumerate(tags):
        if tag not in facts: continue
        units = facts[tag]["units"]
        if shares:
            k = "shares" if "shares" in units else None
        else:
            cands = {u: len(v) for u, v in units.items() if len(u) == 3 and u.isupper()}
            k = cur if cur in cands else (max(cands, key=cands.get) if cands and not cur else None)   # reporting currency = most facts
        if not k: continue
        d = pd.DataFrame(units[k])
        if not len(d): continue
        cur = cur or k
        d["cur"], d["pri"] = k, pri
        if "start" not in d: d["start"] = None
        parts.append(d)
    if not parts: return None
    d = pd.concat(parts, ignore_index=True)
    d["end"] = pd.to_datetime(d.end); d["filed"] = pd.to_datetime(d.filed); d["start"] = pd.to_datetime(d.start)
    d = d.sort_values(["filed", "pri"]).drop_duplicates(["start", "end"], keep="first")   # earliest filing wins (PIT)
    return d.drop(columns="pri")


def _ttm(d):
    """TTM per period end with PIT filed date and annual flag."""
    if d is None: return pd.DataFrame(columns=["end", "filed", "val", "annual"])
    d = d[d.start.notna()].copy(); d["days"] = (d.end - d.start).dt.days
    fy = d[d.days.between(330, 380)]
    out = {r.end: (r.filed, r.val, True) for r in fy.itertuples()}
    ytd = d[d.days.between(80, 300)]
    for r in ytd.itertuples():
        if r.end in out: continue
        f_ = fy[(fy.end - r.start).abs() <= pd.Timedelta(days=10)]          # FY ending just before YTD start
        p_ = ytd[((ytd.end - (r.end - pd.DateOffset(years=1))).abs() <= pd.Timedelta(days=10)) & ((ytd.days - r.days).abs() <= 10)]
        if len(f_) and len(p_):
            out[r.end] = (max(r.filed, f_.filed.iloc[0], p_.filed.iloc[0]), f_.val.iloc[0] + r.val - p_.val.iloc[0], False)
    if not out: return pd.DataFrame(columns=["end", "filed", "val", "annual"])
    return pd.DataFrame([(e, *v) for e, v in out.items()], columns=["end", "filed", "val", "annual"]).sort_values("end")


def _inst(d):
    if d is None: return pd.DataFrame(columns=["end", "filed", "val"])
    return d.sort_values("filed").drop_duplicates("end", keep="first")[["end", "filed", "val"]].sort_values("end")


def _fx(cur, dates):
    if cur == "USD": return pd.Series(1.0, index=dates)
    p = FX / f"{cur}USD.parquet"
    if p.exists():
        s = pd.read_parquet(p).close
    elif (FX / f"USD{cur}.parquet").exists():
        s = 1 / pd.read_parquet(FX / f"USD{cur}.parquet").close
    else:
        return None
    s.index = pd.to_datetime(s.index); s = s.sort_index()
    return pd.Series(np.interp(pd.to_datetime(dates).astype("int64"), s.index.astype("int64"), s.values), index=dates)


DEBT_PARTS = {}


def build(t):
    f = _facts(t)
    if f is None: return None, "keine companyfacts"
    S = {k: _rows(f, v, shares=(k == "shares")) for k, v in DUR.items()}
    I_ = {k: _rows(f, v) for k, v in INST.items()}
    rcur = (S["revenue"].cur.iloc[0] if S["revenue"] is not None else "USD")
    # one series per debt tag (same reporting currency); overlapping US tags (LongTermDebtNoncurrent vs LongTermBorrowings) are
    # avoided by taking the bond tags plus the first borrowing tag only
    def _parts(tags):
        bond = [x for x in tags if "Bond" in x]; other = [x for x in tags if "Bond" not in x]
        out, got = [], False
        for tg in other:
            r_ = _rows(f, [tg])
            if r_ is not None and len(r_) and r_.cur.iloc[0] == rcur and not got: out.append(("bor", _inst(r_))); got = True
        for tg in bond:
            r_ = _rows(f, [tg])
            if r_ is not None and len(r_) and r_.cur.iloc[0] == rcur: out.append(("bond", _inst(r_)))
        return out
    global DEBT_PARTS
    DEBT_PARTS = {k: _parts(INST[k]) for k in ("debt_lt", "debt_cur")}
    rev = _ttm(S["revenue"])
    if not len(rev): return None, "kein Umsatz in companyfacts"
    cur = S["revenue"].cur.iloc[0]
    T = {k: _ttm(S[k]) for k in DUR if k != "shares"}
    sh = S["shares"]; sh = sh[sh.start.notna() & ((sh.end - sh.start).dt.days.between(80, 380))].sort_values("end") if sh is not None else None
    ends = rev.end.tolist()
    rows = []
    for e in ends:
        rr = rev[rev.end == e].iloc[0]
        row = dict(end=e, filed=rr.filed, revenue_ttm=rr.val, annual=rr.annual)
        for k, col in (("opinc", "operating_income_ttm"), ("ni", "net_income_ttm"), ("ocf", "op_cash_flow_ttm"), ("capex", "capex_ttm"),
                       ("sbc", "sbc_ttm"), ("dna", "dna_ttm"), ("pretax", "_pretax"), ("interest", "_int")):
            x = T[k]; x = x[x.end == e]
            row[col] = float(x.val.iloc[0]) if len(x) else np.nan
        if np.isnan(row["operating_income_ttm"]) and not np.isnan(row["_pretax"]):
            row["operating_income_ttm"] = row["_pretax"] + (0 if np.isnan(row["_int"]) else abs(row["_int"])); row["ebit_proxy"] = True
        for k in INST:
            if k in ("debt_lt", "debt_cur"):   # borrowings and bonds are separate line items -> sum distinct tags at this date
                bor, bond = None, 0.0
                for kind, x in DEBT_PARTS[k]:
                    x = x[(x.end <= e) & (x.end >= e - pd.Timedelta(days=100))]
                    if not len(x): continue
                    if kind == "bor": bor = float(x.val.iloc[-1])
                    else: bond += float(x.val.iloc[-1])
                # IFRS: bonds are often a subset of borrowings (NVO); if bonds exceed borrowings they are separate (TSM bank loans)
                row[k] = np.nan if bor is None and not bond else (bor or 0) + bond if bond > (bor or 0) else bor; continue
            x = _inst(I_[k]); x = x[(x.end <= e) & (x.end >= e - pd.Timedelta(days=100))]
            row[k] = float(x.val.iloc[-1]) if len(x) else np.nan
        if sh is not None and len(sh):
            x = sh[(sh.end <= e) & (sh.end >= e - pd.Timedelta(days=100))]
            row["shares_dil"] = float(x.val.iloc[-1]) if len(x) else np.nan
        rows.append(row)
    d = pd.DataFrame(rows).sort_values("end")
    d["total_debt"] = np.where(d.debt_tot.notna(), d.debt_tot, np.where(d[["debt_lt", "debt_cur"]].notna().any(axis=1), d.debt_lt.fillna(0) + d.debt_cur.fillna(0), np.nan))
    d["total_debt"] = d.total_debt.fillna(0)
    d["capex_ttm"] = -d.capex_ttm.abs()
    d["fcf_ttm"] = d.op_cash_flow_ttm + d.capex_ttm
    d["shares_dil"] = d.get("shares_dil", pd.Series(np.nan, index=d.index)).ffill()
    # ADR / share-class check: listed-share equivalent = Yahoo marketCap / last close (counts all classes, ADR-adjusted).
    # Scale EDGAR share counts only if the ratio is outside 0.8-1.25 (ADR ratio, e.g. TSM 1 ADR = 5 shares).
    yi = YFI / f"{t}.json"; note = []
    if yi.exists():
        info = json.loads(yi.read_text()); mc = info.get("marketCap"); px = info.get("previousClose") or info.get("regularMarketPrice") or info.get("currentPrice")
        pp = Path(__import__("os").environ.get("MARKET_STORE", "data_store") + "/prices") / f"{t}.parquet"
        if not px and pp.exists():
            px = float(pd.read_parquet(pp, columns=["close"]).close.iloc[-1])
        last = d.shares_dil.dropna()
        from .engine_v4 import foreign_filer   # v4: ADR rule only for 20-F/40-F filers (US multi-class filers: EDGAR count is authoritative)
        if mc and px and len(last) and foreign_filer(t):
            ratio = (mc / px) / last.iloc[-1]
            if not 0.8 <= ratio <= 1.25:
                d["shares_dil"] *= ratio; note.append(f"ADR-Verhältnis {ratio:.3f} (Börsenwert/Kurs)")
    if d.shares_dil.isna().all() and yi.exists() and json.loads(yi.read_text()).get("sharesOutstanding"):
        d["shares_dil"] = float(json.loads(yi.read_text())["sharesOutstanding"]); note.append("Aktienzahl Yahoo (EDGAR ohne verwässerte Aktien)")
    d["shares_best"] = d.shares_dil
    # FX to USD at availability date (flows and stocks alike: point-in-time translation)
    fx = _fx(cur, d.filed)
    if fx is None: return None, f"Währung {cur} ohne FX-Reihe"
    for c in ("revenue_ttm", "operating_income_ttm", "net_income_ttm", "op_cash_flow_ttm", "capex_ttm", "sbc_ttm", "dna_ttm",
              "equity", "cash", "total_debt", "fcf_ttm"):
        d[c] = d[c] * fx.values
    if cur != "USD": note.append(f"{cur}->USD")
    d = d[d.revenue_ttm.notna() & d.operating_income_ttm.notna()]
    if not len(d): return None, "kein operatives Ergebnis"
    # quarterly grid: at each quarter end Q, latest row filed by Q; last row at its own filing date
    d = d.rename(columns={"filed": "avail_date", "end": "last_quarter_end"}).sort_values("avail_date")
    grid = pd.date_range(d.avail_date.min(), pd.Timestamp.today().normalize(), freq="QE").tolist() + [d.avail_date.max()]
    g = []
    for q in sorted(set(grid)):
        x = d[d.avail_date <= q]
        if len(x):
            r = x.sort_values("last_quarter_end").iloc[-1].to_dict(); r["avail_date"] = min(q, max(q, r["avail_date"])); g.append(r)
    g = pd.DataFrame(g).drop_duplicates(subset=["avail_date"]).sort_values("avail_date").reset_index(drop=True)
    for c in ("revenue_ttm", "net_income_ttm", "op_cash_flow_ttm", "capex_ttm"):
        g[c + "_l4"] = g[c].shift(4); g[c + "_l12"] = g[c].shift(12)
    g["ticker"] = t; g["source"] = "edgar_supp"; g["only_annual"] = g.annual.astype(bool); g["currency_reported"] = cur
    g["ffo_ttm"] = g.net_income_ttm + g.dna_ttm.fillna(0)
    g["supp_note"] = ", ".join(note)
    return g, "ok"


def run(tickers):
    OUT.mkdir(parents=True, exist_ok=True); res = {}
    for t in tickers:
        try:
            g, st = build(t)
        except Exception as ex:
            g, st = None, f"Fehler {type(ex).__name__}: {ex}"
        if g is not None:
            g.drop(columns=[c for c in g.columns if c.startswith("_")]).to_parquet(OUT / f"{t}.parquet")
        res[t] = st
    return res


if __name__ == "__main__":
    ts = sys.argv[1:] or sorted(p.name[:-8] for p in CF.glob("*.json.gz"))
    r = run(ts)
    from collections import Counter
    print(Counter(r.values())); print({k: v for k, v in r.items() if v != "ok"})
