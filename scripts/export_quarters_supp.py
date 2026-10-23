"""Quarterly Finanzdaten for names the scanner snapshot missed or has stale (foreign/old). Source: SEC companyfacts
cache (valuation/edgar_fetch.py). Quarter = 3-month fact, else YTD minus previous YTD with the same start (as
export_snapshot). Writes into data/quarters.json only for names whose list is empty or older than the supplement;
names without any recent quarterly facts (20-F/40-F annual filers) get [] -> UI shows 'nur Jahreszahlen'."""
import json, sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from valuation import edgar_supp as E

D = Path(__file__).resolve().parents[1] / "data"
KEYS = {"revenue": E.DUR["revenue"], "operating_income": E.DUR["opinc"], "net_income": E.DUR["ni"], "op_cash_flow": E.DUR["ocf"],
        "capex": E.DUR["capex"], "cost_of_revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfSales"],
        "eps_diluted": ["EarningsPerShareDiluted", "DilutedEarningsLossPerShare"]}


def _q(d):
    if d is None: return {}
    x = d[d.start.notna()].copy(); x["days"] = (x.end - x.start).dt.days
    cum = {(r.start, r.end): r.val for r in x.itertuples()}; out = {}
    for e in sorted(x.end.unique()):
        d3 = x[(x.end == e) & x.days.between(80, 100)]
        if len(d3): out[e] = float(d3.val.iloc[-1]); continue
        for r in x[(x.end == e) & x.days.between(101, 300)].itertuples():
            prev = [v for (s_, e_), v in cum.items() if s_ == r.start and 70 < (e - e_).days < 110]
            if prev: out[e] = float(r.val - prev[0]); break
    return out


def build(t):
    f = E._facts(t)
    if f is None: return None
    raw = {k: E._rows(f, v) for k, v in KEYS.items()}
    if raw["eps_diluted"] is None:   # EPS unit is USD/shares
        for tag in KEYS["eps_diluted"]:
            if tag in f:
                u = f[tag]["units"]; k = next(iter(u)); d = pd.DataFrame(u[k]); d["start"] = pd.to_datetime(d.get("start")); d["end"] = pd.to_datetime(d.end); d["filed"] = pd.to_datetime(d.filed)
                raw["eps_diluted"] = d.sort_values("filed").drop_duplicates(["start", "end"]); break
    cur = raw["revenue"].cur.iloc[0] if raw["revenue"] is not None else "USD"
    k = {key: _q(v) for key, v in raw.items()}
    ends = sorted(k["revenue"])[-24:]
    fx = E._fx(cur, ends) if cur != "USD" else None
    rows = []
    for i, e in enumerate(ends):
        m = float(fx.iloc[i]) if fx is not None else 1.0
        g = lambda key: k[key].get(e)
        rev = g("revenue"); ocf, capex = g("op_cash_flow"), g("capex")
        fcf = ocf - abs(capex) if ocf is not None and capex is not None else None
        div = lambda a: a / rev if a is not None and rev else None
        rows.append({"end": str(pd.Timestamp(e).date()), "label": f"Q{(pd.Timestamp(e).month - 1) // 3 + 1} {pd.Timestamp(e).year}",
                     "revenue": rev * m if rev is not None else None, "eps": g("eps_diluted") if cur == "USD" else None, "fcf": fcf * m if fcf is not None else None,
                     "gross_margin": div(rev - g("cost_of_revenue")) if g("cost_of_revenue") is not None and rev else None,
                     "op_margin": div(g("operating_income")), "net_margin": div(g("net_income")), "fcf_margin": div(fcf)})
    return rows


if __name__ == "__main__":
    q = json.loads((D / "quarters.json").read_text()); cases = json.loads((D / "cases.json").read_text())
    ts = sys.argv[1:] or sorted(p.name[:-8] for p in E.CF.glob("*.json.gz"))
    changed = {}
    for t in ts:
        if t not in cases: continue
        old = q.get(t) or []
        try: new = build(t) or []
        except Exception as ex: print(t, "Fehler", ex); continue
        last_annual = (cases[t].get("annual") or [{}])[-1].get("fy_end", "0000")
        new_ok = bool(new) and new[-1]["end"] >= last_annual[:10]
        old_ok = bool(old) and old[-1]["end"] >= last_annual[:10]
        if new_ok and (not old_ok or new[-1]["end"] > old[-1]["end"]):
            q[t] = new; changed[t] = f"{len(new)} Quartale bis {new[-1]['end']}"
        elif not old_ok and old:
            q[t] = []; changed[t] = "veraltet entfernt (nur Jahreszahlen)"
    (D / "quarters.json").write_text(json.dumps(q, indent=1))
    from collections import Counter
    print(len(changed), Counter(v.split(" ")[0] if "veraltet" not in v else "veraltet" for v in changed.values()).most_common(3)); print(dict(list(changed.items())[:12]))
