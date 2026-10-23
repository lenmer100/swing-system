"""Export data/valuation_v3.json. Usage: python scripts/export_valuation_v3.py [TICKERS...]"""
import json, sys, math
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from valuation import inputs as I, engine_v3 as E

DEMO = Path(__file__).resolve().parents[1] / "data"
PX = Path(__import__("os").environ.get("MARKET_STORE", "data_store") + "/prices")


def clean(o):
    if isinstance(o, dict): return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [clean(v) for v in o]
    if hasattr(o, "item"): o = o.item()
    if isinstance(o, float) and not math.isfinite(o): return None
    if isinstance(o, pd.Timestamp): return str(o.date())
    return o


def _one(args):
    t, asof, price, secs, typ, c = args
    try:
        return t, E.value_v3(t, asof, price, secs, typ=typ, cons=c, detail=True)
    except Exception as ex:
        return t, dict(ticker=t, status=f"Fehler: {type(ex).__name__}: {str(ex)[:120]}")


def run_all(tickers, types, procs=8, log=None):
    from multiprocessing import Pool
    cons = json.loads((DEMO / "consensus.json").read_text())
    v2 = json.loads((DEMO / "valuation_v2.json").read_text())["stocks"] if (DEMO / "valuation_v2.json").exists() else {}
    out, jobs = {}, []
    # one date for all of data/: demo snapshot close (meta.json asof); price = cases.json price (= header)
    ASOF = pd.Timestamp(json.loads((DEMO / "meta.json").read_text())["asof"])
    cases_px = {t: v.get("price") for t, v in json.loads((DEMO / "cases.json").read_text()).items()}
    asof0 = ASOF
    sp = Path(__file__).resolve().parents[1] / "valuation" / "cache" / f"sectors_{pd.Timestamp(asof0).date()}.json"
    secs = json.loads(sp.read_text()) if sp.exists() else clean(I.sector_stats(asof0))
    sp.write_text(json.dumps(clean(secs)))
    for t in tickers:
        p = PX / f"{t}.parquet"
        if not p.exists(): out[t] = dict(ticker=t, status="keine Kurse"); continue
        px = pd.read_parquet(p, columns=["date", "close"]).sort_values("date"); px = px[px.date <= ASOF]
        if not len(px): out[t] = dict(ticker=t, status="keine Kurse"); continue
        c = cons.get(t)
        if c:
            c = dict(c); c.setdefault("months_left_fy0", (v2.get(t) or {}).get("consensus", {}).get("months_left_fy0", 6))
            if len(c.get("years", [])) < 2: c = None
        jobs.append((t, ASOF, float(cases_px.get(t) or px.close.iloc[-1]), secs, types.get(t), c))
    with Pool(procs) as pool:
        for i, (t, r) in enumerate(pool.imap_unordered(_one, jobs, chunksize=2)):
            if t in v2 and v2[t].get("status") == "ok": r["v2"] = dict(fair_value=v2[t]["fair_value"], range=v2[t]["range"])
            out[t] = r
            if log and i % 100 == 0:
                with open(log, "a") as f: f.write(f"- export {i}/{len(jobs)} {pd.Timestamp.now():%H:%M}\n")
    (DEMO / "valuation_v3.json").write_text(json.dumps(clean(dict(meta=dict(version="valuation_v3", note="Regeln: design_ref/VALUATION_V3.md"), stocks=out)), ensure_ascii=False, indent=1))
    return out


def run(tickers, cons_path=DEMO / "consensus.json", out_path=DEMO / "valuation_v3.json", types=None):
    cons = json.loads(Path(cons_path).read_text())
    v2 = json.loads((DEMO / "valuation_v2.json").read_text())["stocks"] if (DEMO / "valuation_v2.json").exists() else {}
    out, secs = {}, None
    for t in tickers:
        p = PX / f"{t}.parquet"
        if not p.exists(): out[t] = dict(ticker=t, status="keine Kurse"); continue
        px = pd.read_parquet(p, columns=["date", "close"]).sort_values("date")
        asof, price = px.date.iloc[-1], float(px.close.iloc[-1])
        if secs is None:
            sp = Path(__file__).resolve().parents[1] / "valuation" / "cache" / f"sectors_{pd.Timestamp(asof).date()}.json"
            secs = json.loads(sp.read_text()) if sp.exists() else I.sector_stats(asof)
            sp.write_text(json.dumps(clean(secs)))
        c = cons.get(t)
        if c:
            fy_end = pd.Timestamp(c.get("fy0_end")) if c.get("fy0_end") else None
            c = dict(c); c.setdefault("months_left_fy0", (v2.get(t) or {}).get("consensus", {}).get("months_left_fy0", 6))
        try:
            r = E.value_v3(t, asof, price, secs, typ=(types or {}).get(t), cons=c if c and len(c.get("years", [])) >= 2 else None)
        except Exception as ex:
            r = dict(ticker=t, status=f"Fehler: {type(ex).__name__}: {ex}")
        if t in v2 and v2[t].get("status") == "ok": r["v2"] = dict(fair_value=v2[t]["fair_value"], range=v2[t]["range"])
        out[t] = r
    Path(out_path).write_text(json.dumps(clean(dict(meta=dict(version="valuation_v3", note="Regeln: design_ref/VALUATION_V3.md"), stocks=out)), ensure_ascii=False, indent=1))
    return out


if __name__ == "__main__":
    if sys.argv[1:] == ["--all"]:
        cases = json.loads((DEMO / "cases.json").read_text()); cons = json.loads((DEMO / "consensus.json").read_text())
        ts = sorted(set(cases) | set(cons))
        res = run_all(ts, {t: v.get("type") for t, v in cases.items()}, log=Path(__file__).resolve().parents[1] / "valuation" / "_V3_PROGRESS.md")
        from collections import Counter
        print(len(res), Counter(r.get("status", "?")[:40] for r in res.values()).most_common(15)); sys.exit()
    ts = sys.argv[1:] or ["META", "MELI", "GOOGL", "AMZN", "NVDA"]
    old = json.loads((DEMO / "cases.json").read_text())
    res = run(ts, types={t: v.get("type") for t, v in old.items()})
    for t, r in res.items():
        if r.get("status") != "ok": print(t, r.get("status")); continue
        cl = r["classification"]; c = r["cost_of_capital"]
        print(f"{t}: px {r['price']:.0f} FV {r['fair_value']:.0f} [{r['range']['pessimistic']:.0f}-{r['range']['optimistic']:.0f}] buy<={r.get('buy_zone_below', 0):.0f} "
              f"intr {r['scenarios']['base']['intrinsic']:.0f} pe {r['scenarios']['base']['pe_value']} w {r['weights']['dcf']:.2f} "
              f"{cl['model']} moat={cl['moat']}({cl['excess_roic_long']}) stage={cl['stage']} cyc={cl['cyclical']} reinv={cl['reinvester']}({cl['fcf_to_ni']}) unc={cl['uncertainty']} "
              f"wacc {c['wacc']:.4f} rf {c['rf']} erp {c['erp']} mT {r['margin']['targets']['base']:.3f} cash {r['firm']['cash']/1e9:.1f} v2 {r.get('v2', {}).get('fair_value')}")
