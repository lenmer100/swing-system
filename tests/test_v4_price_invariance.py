"""Audit G1: fair value must not follow the price. Re-value with price x0.7 and x1.3; base fair value may move only
through the market-value debt weight in WACC (and the forward P/E block, which uses no price): tolerance 5 %."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from valuation import engine_v4 as E, inputs as I
from scripts.export_valuation_v4 import jobs_for, CACHE

NAMES = ["NBIS", "ASTS", "IREN", "SE", "NVDA", "META", "PLTR", "APP", "UBER", "AXON", "F", "JPM"]
TOL = 0.05


def main():
    types = I.type_map()
    asof, jobs = jobs_for(NAMES, types)
    peers = json.loads((CACHE / f"peers_v4_{asof.date()}.json").read_text())
    secs = json.loads((CACHE / f"sectors_{asof.date()}.json").read_text())
    bad, rows = [], []
    for t, a, p, ty, c in jobs:
        v = {k: E.value_v4(t, a, p * k, peers, secs, typ=ty, cons=c, detail=False) for k in (0.7, 1.0, 1.3)}
        if any(x.get("status") != "ok" for x in v.values()):
            rows.append((t, "n/a")); continue
        ar = {k: x["archetype"]["key"] for k, x in v.items()}
        if len(set(ar.values())) > 1:      # price crosses a market-cap class boundary (mega 500 Mrd.): different model, not a price anchor
            rows.append((t, f"Archetypwechsel {ar} – ausgenommen")); continue
        b = v[1.0]["range"]["base"]; d = max(abs(v[k]["range"]["base"] / b - 1) for k in (0.7, 1.3)) if b else 0
        rows.append((t, f"{v[0.7]['range']['base']:.1f} / {b:.1f} / {v[1.3]['range']['base']:.1f}  Δmax {d:.1%}"))
        if d > TOL:
            bad.append(t)
    for r in rows:
        print(*r)
    print("FAIL" if bad else "PASS", bad)
    return not bad


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
