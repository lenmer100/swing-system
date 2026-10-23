"""Cash + short-term investments (point in time) from SEC EDGAR companyfacts (public API, fair-access UA,
<=8 req/s). Only the extracted series is cached (valuation/cache/liquidity/<TICKER>.parquet)."""
from __future__ import annotations
import json, time, urllib.request
from pathlib import Path
import pandas as pd

CACHE = Path(__file__).parent / "cache" / "liquidity"
CIKS = Path(__import__("os").environ.get("MARKET_STORE", "data_store") + "/derived/edgar_cik_map.json")
UA = __import__("os").environ.get("SEC_USER_AGENT", "your-name your@email.com")
TOTAL = ["CashCashEquivalentsAndShortTermInvestments"]
CASH = ["CashAndCashEquivalentsAtCarryingValue"]
STI = ["MarketableSecuritiesCurrent", "ShortTermInvestments", "AvailableForSaleSecuritiesDebtSecuritiesCurrent", "DebtSecuritiesCurrent"]


def _series_merged(facts, tags):
    """Per period end: first tag in priority order that reports it (firms switch tags over time, e.g. NVDA
    MarketableSecuritiesCurrent -> DebtSecuritiesCurrent in FY2027)."""
    parts = [_series(facts, [tg]).assign(prio=i) for i, tg in enumerate(tags)]
    d = pd.concat([x for x in parts if len(x)]) if any(len(x) for x in parts) else pd.DataFrame(columns=["end", "filed", "val"])
    return d.sort_values(["end", "prio"]).drop_duplicates("end", keep="first") if len(d) else d


def _series(facts, tags):
    rows = []
    for tg in tags:
        for x in facts.get(tg, {}).get("units", {}).get("USD", []):
            if x.get("form", "")[:4] in ("10-K", "10-Q", "20-F") and "end" in x:
                rows.append(dict(end=x["end"], filed=x["filed"], val=x["val"], tag=tg))
        if rows:
            break
    if not rows:
        return pd.DataFrame(columns=["end", "filed", "val"])
    d = pd.DataFrame(rows)
    return d.sort_values("filed").drop_duplicates("end", keep="first")  # first-reported value (PIT)


def fetch(ticker, cik):
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        facts = json.load(r)["facts"].get("us-gaap", {})
    tot = _series(facts, TOTAL)
    cash = _series(facts, CASH)
    sti = _series_merged(facts, STI)
    if len(cash):
        m = cash.merge(sti[["end", "val"]].rename(columns={"val": "sti"}), on="end", how="left")
        m["liq"] = m.val + m.sti.fillna(0)
        m["has_sti"] = m.sti.notna()
        m = m[["end", "filed", "liq", "has_sti"]]
    else:
        m = pd.DataFrame(columns=["end", "filed", "liq"])
    if len(tot):
        t2 = tot.rename(columns={"val": "liq"})[["end", "filed", "liq"]].assign(has_sti=True)
        m = pd.concat([m[~m.end.isin(t2.end)], t2]) if len(m) else t2
        # if both exist for a date, keep the larger (combined tag sometimes omits securities)
        m = m.sort_values("liq").drop_duplicates("end", keep="last")
    m["end"], m["filed"] = pd.to_datetime(m.end), pd.to_datetime(m.filed)
    return m.sort_values("end").reset_index(drop=True)


def load(ticker):
    p = CACHE / f"{ticker}.parquet"
    return pd.read_parquet(p) if p.exists() else None


def liquidity_asof(ticker, asof):
    d = load(ticker)
    if d is None or not len(d):
        return None
    d = d[d.filed <= pd.Timestamp(asof)]
    return None if not len(d) else float(d.sort_values("end").liq.iloc[-1])


def build_cache(tickers, sleep=0.13, refresh=False):
    CACHE.mkdir(parents=True, exist_ok=True)
    ciks = json.loads(CIKS.read_text())
    ok = 0
    for t in tickers:
        if ((CACHE / f"{t}.parquet").exists() and not refresh) or t not in ciks:
            continue
        try:
            fetch(t, ciks[t]).to_parquet(CACHE / f"{t}.parquet"); ok += 1
        except Exception as e:
            pd.DataFrame(columns=["end", "filed", "liq"]).to_parquet(CACHE / f"{t}.parquet")
        time.sleep(sleep)
    return ok


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from valuation.inputs import type_map
    ts = ["META", "MELI", "GOOGL", "AMZN", "NVDA"] + sorted(type_map())
    print(build_cache(ts, refresh="--refresh" in sys.argv))
