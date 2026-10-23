"""Goodwill (point in time) from SEC companyconcept API (us-gaap/Goodwill, else ifrs-full/Goodwill), for the
v3 moat rule 'ROIC ex goodwill' (acquired goodwill is not operating capital; Koller/Goedhart/Wessels ch. 11/16:
ROIC excluding goodwill measures underlying economics, ROIC including goodwill measures acquisition returns)."""
import json, sys, time, urllib.request, urllib.error, functools
from pathlib import Path
import pandas as pd
from .edgar_fetch import cik_map, UA
from . import edgar_supp as E
CACHE = Path(__file__).parent / "cache" / "goodwill"


def fetch(t, cik):
    for tax in ("us-gaap", "ifrs-full"):
        url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{int(cik):010d}/{tax}/Goodwill.json"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
                u = json.load(r)["units"]
        except urllib.error.HTTPError as e:
            if e.code == 404: time.sleep(.12); continue
            raise
        u = {k_: v_ for k_, v_ in u.items() if isinstance(v_, list) and v_}
        if not u:      # v5: SEC companyconcept sometimes returns empty units (KO) -> companyfacts fallback
            url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json"
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
                u = {k_: v_ for k_, v_ in ((json.load(r).get("facts", {}).get(tax, {}).get("Goodwill") or {}).get("units") or {}).items() if v_}
            if not u: time.sleep(.12); continue
        k = max(u, key=lambda x: len(u[x])); d = pd.DataFrame(u[k])
        d["end"] = pd.to_datetime(d.end); d["filed"] = pd.to_datetime(d.filed); d["cur"] = k
        return d.sort_values("filed").drop_duplicates("end", keep="first")[["end", "filed", "val", "cur"]]
    return pd.DataFrame(columns=["end", "filed", "val", "cur"])


def build(tickers, refresh=False):
    m = cik_map(); CACHE.mkdir(parents=True, exist_ok=True); n = 0
    for t in tickers:
        p = CACHE / f"{t}.parquet"
        c = m.get(t) or m.get(t.replace("-", "."))
        if not c or (p.exists() and not refresh): continue
        try:
            fetch(t, c).to_parquet(p); n += 1
        except Exception as ex:
            print(t, ex)
        time.sleep(.12)
    return n


@functools.lru_cache(None)
def _load(t):
    p = CACHE / f"{t}.parquet"
    if not p.exists(): return None
    d = pd.read_parquet(p)
    if len(d) and d.cur.iloc[0] != "USD":
        fx = E._fx(d.cur.iloc[0], d.filed)
        if fx is None: return None
        d = d.assign(val=d.val.values * fx.values)
    return d


def goodwill_asof(t, avail, period_end=None):
    """Latest goodwill reported by `avail` (0 if the firm reports none at all; None if not fetched)."""
    d = _load(t)
    if d is None: return None
    if not len(d): return 0.0
    x = d[d.filed <= pd.Timestamp(avail)]
    if period_end is not None:
        x = x[x.end <= pd.Timestamp(period_end)]
    return float(x.val.iloc[-1]) if len(x) else 0.0


if __name__ == "__main__":
    cases = json.loads((Path(__file__).parents[1] / "data" / "cases.json").read_text())
    print(build(sorted(cases)))
