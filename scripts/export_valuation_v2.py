"""Export data/valuation_v2.json (valuation engine v2). Usage: python scripts/export_valuation_v2.py [TICKERS...]"""
import json, sys, math
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from valuation import inputs as I, engine as E

DEMO = Path(__file__).resolve().parents[1] / "data"


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if hasattr(o, "item"):
        o = o.item()
    if isinstance(o, float) and not math.isfinite(o):
        return None
    return o


def main(tickers):
    cons = json.loads((DEMO / "consensus.json").read_text())
    old = json.loads((DEMO / "cases.json").read_text())
    out = {}
    secs_cache = {}
    for t in tickers:
        px = pd.read_parquet(Path(__import__("os").environ.get("MARKET_STORE", "data_store") + "/prices") / f"{t}.parquet", columns=["date", "close"]).sort_values("date")
        asof, price = px.date.iloc[-1], float(px.close.iloc[-1])
        key = str(pd.Timestamp(asof).date())
        if key not in secs_cache:
            secs_cache[key] = I.sector_stats(asof)
        r = E.value_stock(t, asof, price, cons[t], secs_cache[key], typ=old.get(t, {}).get("type"))
        if t in old:
            ms = [m["value"] for m in old[t]["models"] if isinstance(m, dict) and m.get("value")]
            r["v1_comparison"] = dict(median=old[t].get("models_median"), min=min(ms) if ms else None,
                                      max=max(ms) if ms else None, implied_g=old[t].get("implied_g"), r="fix 9 %")
        out[t] = r
    meta = dict(version="valuation_v2", note="Fixed assumptions, no parameter search. See design_ref/VALUATION_V2.md.")
    (DEMO / "valuation_v2.json").write_text(json.dumps(clean(dict(meta=meta, stocks=out)), ensure_ascii=False, indent=1))
    return out


if __name__ == "__main__":
    ts = sys.argv[1:] or ["META", "MELI", "GOOGL", "AMZN", "NVDA"]
    res = main(ts)
    for t, r in res.items():
        if r.get("status") != "ok":
            print(t, r.get("status")); continue
        c = r["cost_of_capital"]; f = r["scenarios"]["base"]["forward_pe"]; rv = r["reverse_dcf"]
        print(f"{t}: px {r['price']:.0f} FV {r['fair_value']:.0f} [{r['range']['pessimistic']:.0f}/{r['range']['optimistic']:.0f}] "
              f"DCF {r['scenarios']['base']['dcf_value']:.0f} PE {f['fair_price']:.0f} wacc {c['wacc']:.3f} beta {c['beta']:.2f} "
              f"fPE {f['forward_pe']:.1f} jPE {f['justified']['justified_pe']:.1f} implCAGR5 {rv['implied_rev_cagr_5y']} "
              f"base5 {rv['base_rev_cagr_5y']:.3f} mT {r['scenarios']['base']['dcf']['inputs']['margin_target']:.3f} s2c {r['scenarios']['base']['dcf']['inputs']['sales_to_capital']:.2f} TV% {r['scenarios']['base']['dcf']['terminal_share']:.2f} old {r.get('v1_comparison')}")
