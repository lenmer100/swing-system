"""v5: point-in-time XBRL concepts from SEC companyconcept (same mechanics as goodwill.py), cached per ticker.
Instant concepts -> latest value filed <= asof; duration concepts -> latest ~annual (330-400 d) value filed <= asof,
or 4-quarter sum. Used for: NOL carryforwards, intangibles, preferred, AOCI, dividends, insurer premiums/losses."""
import json, time, urllib.request, urllib.error, functools
from pathlib import Path
import pandas as pd
from .edgar_fetch import cik_map, UA
from . import edgar_supp as E
CACHE = Path(__file__).parent / "cache" / "concepts"

CONCEPTS = {   # key -> candidate tags (first found wins)
    "nol": ["DeferredTaxAssetsOperatingLossCarryforwards", "DeferredTaxAssetsOperatingLossCarryforwardsDomestic"],
    "intangibles": ["IntangibleAssetsNetExcludingGoodwill", "FiniteLivedIntangibleAssetsNet"],
    "preferred": ["PreferredStockValue", "PreferredStockValueOutstanding"],
    "aoci": ["AccumulatedOtherComprehensiveIncomeLossNetOfTax"],
    "dividends": ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends", "DividendsCommonStockCash", "DividendsCommonStock"],
    "pref_div": ["PreferredStockDividendsIncomeStatementImpact", "DividendsPreferredStock"],
    "premiums": ["PremiumsEarnedNet", "PremiumsEarnedNetPropertyAndCasualty"],
    "losses": ["PolicyholderBenefitsAndClaimsIncurredNet", "IncurredClaimsPropertyCasualtyAndLiability"],
    "uw_expense": ["DeferredPolicyAcquisitionCostAmortizationExpense", "OtherUnderwritingExpense", "SellingGeneralAndAdministrativeExpense"],
    "inv_income": ["NetInvestmentIncome"],
    "ppe_net": ["PropertyPlantAndEquipmentNet"],
    # v5.1
    "eq_method": ["EquityMethodInvestments", "InvestmentsInAffiliatesSubsidiariesAssociatesAndJointVentures"],
    "receivables": ["AccountsReceivableNetCurrent", "ReceivablesNetCurrent"],
    "inventory": ["InventoryNet"],
    "ppe_alt": ["PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization", "PropertyPlantAndEquipmentNetIncludingRightOfUseAssets"],
    "ppe_gross": ["PropertyPlantAndEquipmentGross"],
    "ppe_accdep": ["AccumulatedDepreciationDepletionAndAmortizationPropertyPlantAndEquipment"],
    "payables": ["AccountsPayableCurrent", "AccountsPayableAndAccruedLiabilitiesCurrent"],
}
FIN_ONLY = {"preferred", "aoci", "pref_div", "premiums", "losses", "uw_expense", "inv_income"}


def _get(cik, tag, tax="us-gaap"):
    url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{int(cik):010d}/{tax}/{tag}.json"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
            u = json.load(r)["units"]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    k = max(u, key=lambda x: len(u[x])); d = pd.DataFrame(u[k]); d["cur"] = k
    return d


def build(tickers, keys, refresh=False):
    m = cik_map(); CACHE.mkdir(parents=True, exist_ok=True); n = 0
    for t in tickers:
        c = m.get(t) or m.get(t.replace("-", "."))
        if not c:
            continue
        p = CACHE / f"{t}.parquet"
        old = pd.read_parquet(p) if p.exists() and not refresh else pd.DataFrame()
        have = set(old.key) if len(old) else set()
        parts = [old] if len(old) else []
        for key in keys:
            if key in have:
                continue
            got = None
            for tag in CONCEPTS[key]:
                try:
                    got = _get(c, tag)
                except Exception as ex:
                    print(t, key, ex); got = None
                time.sleep(.11)
                if got is not None and len(got):
                    break
            if got is None or not len(got):
                got = pd.DataFrame(dict(end=[None], val=[None], filed=[None], cur=[None]))
            got["key"] = key
            cols = [c_ for c_ in ("start", "end", "val", "filed", "form", "cur", "key") if c_ in got]
            parts.append(got[cols]); n += 1
        if parts:
            d = pd.concat(parts, ignore_index=True)
            for c_ in ("start", "end", "filed"):
                if c_ in d:
                    d[c_] = pd.to_datetime(d[c_], errors="coerce")
            d["val"] = pd.to_numeric(d["val"], errors="coerce")
            d.to_parquet(p)
    return n


@functools.lru_cache(None)
def _load(t):
    p = CACHE / f"{t}.parquet"
    if not p.exists():
        return None
    d = pd.read_parquet(p)
    out = []
    for k, g in d.groupby("key"):
        g = g.dropna(subset=["val", "filed"])
        if len(g) and g.cur.iloc[0] not in (None, "USD") and not str(g.cur.iloc[0]).startswith("USD"):
            fx = E._fx(g.cur.iloc[0], g.filed)
            g = g.assign(val=g.val.values * fx.values) if fx is not None else g.iloc[0:0]
        out.append(g)
    return pd.concat(out) if out else d.iloc[0:0]


def fetched(t, key):
    p = CACHE / f"{t}.parquet"
    if not p.exists():
        return False
    return key in set(pd.read_parquet(p, columns=["key"]).key)


def instant(t, key, asof, max_age_days=500):
    """Latest instant value filed <= asof (None if not fetched/never reported; 0 not assumed)."""
    d = _load(t)
    if d is None:
        return None
    x = d[(d.key == key) & (d.filed <= pd.Timestamp(asof))]
    if "start" in x:
        x = x[x.start.isna()]
    x = x[x.end >= pd.Timestamp(asof) - pd.Timedelta(days=max_age_days)]
    if not len(x):
        return None
    x = x.sort_values(["end", "filed"])
    return float(x.val.iloc[-1])


def annual(t, key, asof, n=1, max_age_days=500):
    """Annual (330-400 day) duration values filed <= asof, newest first, distinct period ends (list, up to n)."""
    d = _load(t)
    if d is None or "start" not in d:
        return []
    x = d[(d.key == key) & (d.filed <= pd.Timestamp(asof))].dropna(subset=["start"])
    dur = (x.end - x.start).dt.days
    x = x[(dur >= 330) & (dur <= 400)].sort_values(["end", "filed"]).drop_duplicates("end", keep="last")
    x = x[x.end <= pd.Timestamp(asof)]
    if not len(x) or x.end.iloc[-1] < pd.Timestamp(asof) - pd.Timedelta(days=max_age_days):
        return []
    return [float(v) for v in x.val.iloc[::-1].head(n)]


def d_annual(t, key, asof, n=10, max_age_days=500):
    """Like annual() but returns [(period_end, value)] newest first."""
    d = _load(t)
    if d is None or "start" not in d:
        return []
    x = d[(d.key == key) & (d.filed <= pd.Timestamp(asof))].dropna(subset=["start"])
    dur = (x.end - x.start).dt.days
    x = x[(dur >= 330) & (dur <= 400)].sort_values(["end", "filed"]).drop_duplicates("end", keep="last")
    x = x[x.end <= pd.Timestamp(asof)]
    if not len(x) or x.end.iloc[-1] < pd.Timestamp(asof) - pd.Timedelta(days=max_age_days):
        return []
    return [(pd.Timestamp(e), float(v)) for e, v in zip(x.end.iloc[::-1].head(n), x.val.iloc[::-1].head(n))]


if __name__ == "__main__":
    import sys
    from . import inputs as I
    tm = I.type_map(); cases = json.loads((Path(__file__).parents[1] / "data" / "cases.json").read_text())
    tick = sorted(set(cases) | set(tm))
    fin = [t for t in tick if tm.get(t) in ("Finanzen", "Versicherung", "REIT", "AssetManager", "Versicherungsmakler", "Versorger", "Gesundheitsdienste", "Payments")]
    print("fin", build(fin, list(CONCEPTS)), flush=True)
    print("all", build(tick, ["nol", "intangibles", "dividends", "ppe_net"]), flush=True)


def build_cf(tickers, keys=None, refresh=False, workers=4):
    """Faster path: one companyfacts request per ticker, all concepts extracted (same output format)."""
    import gzip, io
    from concurrent.futures import ThreadPoolExecutor
    keys = keys or list(CONCEPTS)
    m = cik_map(); CACHE.mkdir(parents=True, exist_ok=True)
    def one(t):
        c = m.get(t) or m.get(t.replace("-", "."))
        p = CACHE / f"{t}.parquet"
        if not c:
            return 0
        old = pd.read_parquet(p) if p.exists() and not refresh else pd.DataFrame()
        have = set(old.key) if len(old) else set()
        need = [k for k in keys if k not in have]
        if not need:
            return 0
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(c):010d}.json"
        for attempt in range(3):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"}), timeout=60) as r:
                    raw = r.read()
                    if r.headers.get("Content-Encoding") == "gzip":
                        raw = gzip.decompress(raw)
                facts = json.loads(raw).get("facts", {}).get("us-gaap", {})
                break
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    facts = {}; break
                time.sleep(2)
            except Exception:
                time.sleep(2)
        else:
            return 0
        parts = [old] if len(old) else []
        for key in need:
            got = None
            for tag in CONCEPTS[key]:
                if tag in facts:
                    u = facts[tag]["units"]; k = max(u, key=lambda x: len(u[x]))
                    got = pd.DataFrame(u[k]); got["cur"] = k
                    if len(got):
                        break
            if got is None or not len(got):
                got = pd.DataFrame(dict(end=[None], val=[None], filed=[None], cur=[None]))
            got["key"] = key
            parts.append(got[[c_ for c_ in ("start", "end", "val", "filed", "form", "cur", "key") if c_ in got]])
        d = pd.concat(parts, ignore_index=True)
        for c_ in ("start", "end", "filed"):
            if c_ in d:
                d[c_] = pd.to_datetime(d[c_], errors="coerce")
        d["val"] = pd.to_numeric(d["val"], errors="coerce")
        d.to_parquet(p)
        time.sleep(0.25)
        return 1
    with ThreadPoolExecutor(workers) as ex:
        return sum(ex.map(one, tickers))
