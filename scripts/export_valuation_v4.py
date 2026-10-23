"""Export data/valuation_v4.json (archetype-driven). Usage: python scripts/export_valuation_v4.py --all | TICKERS"""
import json, sys, math
from pathlib import Path
from multiprocessing import Pool
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from valuation import inputs as I, engine_v4 as E
from scripts.export_valuation_v3 import clean

DEMO = Path(__file__).resolve().parents[1] / "data"
CACHE = Path(__file__).resolve().parents[1] / "valuation" / "cache"
G = {}


def _init(g):
    G.update(g)


def _fpe(t, asof, price, c):
    if not c or len(c.get("years", [])) < 2:
        return None
    try:
        n, _ = E.ntm_eps_clean(c, E.months_left_fy0(t, asof, c), price)
        return price / n if n else None
    except Exception:
        return None


def _p1(args):
    t, asof, price, typ, c = args
    try:
        a, why, x = E.arch_of(t, asof, price, typ, c)
        if a is None:
            return None
        fs = I.firm_stats(t, asof); b, _ = I.own_beta(t, asof)
        return dict(ticker=t, typ=typ, arch=a, margin=fs["margin_ttm"], s2c=fs["sales_to_capital_cycle"] or fs["sales_to_capital_raw"],
                    beta=b, capex_rev=x["capex_rev"], growth=x["growth"], fwd_pe=_fpe(t, asof, price, c))
    except Exception:
        return None


def _one(args):
    t, asof, price, typ, c = args
    try:
        return t, E.value_v4(t, asof, price, G["peers"], G["secs"], typ=typ, cons=c, detail=True)
    except Exception as ex:
        return t, dict(ticker=t, status=f"Fehler: {type(ex).__name__}: {str(ex)[:120]}")


def jobs_for(tickers, types):
    cons = json.loads((DEMO / "consensus.json").read_text())
    ASOF = pd.Timestamp(json.loads((DEMO / "meta.json").read_text())["asof"])
    cpx = {t: v.get("price") for t, v in json.loads((DEMO / "cases.json").read_text()).items()}
    jobs = []
    for t in tickers:
        p = Path(__import__("os").environ.get("MARKET_STORE", "data_store") + "/prices") / f"{t}.parquet"
        price = cpx.get(t)
        if not price and p.exists():
            px = pd.read_parquet(p, columns=["date", "close"]); px = px[px.date <= ASOF]
            price = float(px.close.iloc[-1]) if len(px) else None
        if not price:
            continue
        c = cons.get(t)
        if c and len(c.get("years", [])) < 2:
            c = None
        jobs.append((t, ASOF, float(price), types.get(t), c))
    return ASOF, jobs


def run(tickers, types, procs=8):
    ASOF, jobs = jobs_for(tickers, types)
    sp = CACHE / f"sectors_{ASOF.date()}.json"
    secs = json.loads(sp.read_text()) if sp.exists() else clean(I.sector_stats(ASOF))
    pp = CACHE / f"peers_v4_{ASOF.date()}.json"
    if pp.exists() and len(tickers) < 50:
        peers = json.loads(pp.read_text())
    else:
        _, alljobs = jobs_for(sorted(types), types) if len(tickers) < 50 else (None, jobs)
        with Pool(procs) as pool:
            rows = [r for r in pool.map(_p1, alljobs, chunksize=4) if r]
        peers = clean(E.peer_stats(rows)); pp.write_text(json.dumps(peers))
    out = {}
    with Pool(procs, initializer=_init, initargs=(dict(peers=peers, secs=secs),)) as pool:
        for t, r in pool.imap_unordered(_one, jobs, chunksize=2):
            out[t] = r
    return ASOF, out, peers


def dual_listings(res):
    """A-F9: one issuer = one data basis. Home listing 'X.<suffix>' and US line 'X' with the same company name ->
    the home line takes the EDGAR filer's valuation, scaled by the price ratio (FX x ADR ratio)."""
    n = 0
    for t in list(res):
        if "." not in t:
            continue
        base = t.split(".")[0]
        a, h = res.get(base), res.get(t)
        if not a or not h or a.get("status") != "ok" or not a.get("price") or not h.get("price"):
            continue
        na, nh = (E._info(base).get("longName") or "").lower(), (E._info(t).get("longName") or "").lower()
        if not na or not nh or na.split()[0] != nh.split()[0]:
            continue
        k = h["price"] / a["price"]
        c = json.loads(json.dumps(a, default=str)); c["ticker"] = t; c["price"] = h["price"]
        for key in ("fair_value", "buy_zone_below"):
            if c.get(key) is not None: c[key] = c[key] * k
        c["range"] = {kk: (v * k if v is not None else None) for kk, v in c["range"].items()}
        c["dual_listing"] = dict(basis=base, price_ratio=k, note=f"Doppellisting: Bewertung aus {base} (EDGAR-Filer), umgerechnet mit Kursverhältnis {k:.4f} (FX × ADR-Verhältnis)")
        res[t] = c; n += 1
    return n


def input_hash():
    """Mega audit 16: SHA-256 over every input the export reads (data files by content, caches by name+size+mtime, code by content)."""
    import hashlib
    h = hashlib.sha256(); parts = {}
    for f in ["consensus.json", "cases.json", "meta.json"]:
        b = (DEMO / f).read_bytes(); parts[f] = hashlib.sha256(b).hexdigest()[:12]; h.update(b)
    V = Path(__file__).resolve().parents[1] / "valuation"
    for d in ["cache/fund_supp", "cache/debt", "cache/companyfacts", "cache/concepts", "cache/goodwill", "cache/xbrl", "data"]:
        hh = hashlib.sha256()
        for q in sorted((V / d).rglob("*")) if (V / d).exists() else []:
            if q.is_file():
                st = q.stat(); hh.update(f"{q.name}|{st.st_size}|{int(st.st_mtime)}".encode())
        parts[d] = hh.hexdigest()[:12]; h.update(hh.digest())
    for q in sorted(V.glob("*.py")) + [Path(__file__)]:
        h.update(q.read_bytes())
    parts["code"] = "in total"
    return dict(sha256=h.hexdigest(), parts=parts)


def write_archetypes(res, asof):
    """Stable, readable snapshot of the classifier output (sorted, fixed columns, rounded) -> data/archetypes_v4.csv."""
    cols = ["capex_rev", "growth", "growth_fwd", "growth_trailing", "margin", "margin_3y", "margin_long", "margin_p10", "rev_drawdown",
            "fcf_yield", "dilution_3y", "sbc_rev", "revenue", "mcap", "structural_break", "cycle"]
    rows = []
    for t in sorted(res):
        r = res[t]
        if r.get("status") != "ok":
            continue
        a = r["archetype"]; f = a.get("features") or {}
        rows.append(dict(ticker=t, asof=str(asof.date()), archetype=a["key"], name=a["name"], rule=a.get("rule"), reliable=r.get("reliable"),
                         **{k: (round(f[k], 4) if isinstance(f.get(k), float) else f.get(k)) for k in cols}))
    pd.DataFrame(rows).to_csv(DEMO / "archetypes_v4.csv", index=False)


if __name__ == "__main__":
    cases = json.loads((DEMO / "cases.json").read_text()); types = {t: v.get("type") for t, v in cases.items()}
    if sys.argv[1:] == ["--all"]:
        cons = json.loads((DEMO / "consensus.json").read_text())
        ts = sorted(set(cases) | set(cons))
        asof, res, peers = run(ts, types)
        print("Doppellistings vereinheitlicht:", dual_listings(res))
        from valuation.invest_plan import plan as _plan
        for _t, _r in res.items():
            if _r.get("status") == "ok":
                _r["invest_plan"] = _plan(_r, asof)
        (DEMO / "valuation_v4.json").write_text(json.dumps(clean(dict(meta=dict(version="valuation_v4", engine="v5", asof=str(asof.date()), note="Regeln: design_ref/VALUATION_V4.md", input_hash=input_hash(),
                                                                                peers={k: v for k, v in peers.items() if not k.startswith("_")}), stocks=res)), ensure_ascii=False, indent=1))
        write_archetypes(res, asof)
        from collections import Counter
        print(len(res), Counter(r.get("status", "?")[:40] for r in res.values()).most_common(8))
        print(Counter((r.get("archetype") or {}).get("key") for r in res.values() if r.get("status") == "ok").most_common())
        sys.exit()
    asof, res, _ = run(sys.argv[1:], types)
    for t, r in res.items():
        if r.get("status") != "ok": print(t, r.get("status")); continue
        a = r["archetype"]; c = r["cost_of_capital"]; f = r.get("firm") or {}
        print(f"{t}: {a['key']} ({a['rule']}) px {r['price']:.2f} FV {r['fair_value']:.1f} [{r['range']['pessimistic']:.1f}-{r['range']['optimistic']:.1f}] buy {r['buy_zone_below']:.1f} "
              f"rel {r['reliable']} {r['unreliable_reasons']} wacc {c['wacc']:.3f} crp {c.get('crp')} mT {({k: round(v, 3) for k, v in r['margin']['targets'].items()} if r.get('margin') else None)} sh {(f.get('shares_diluted') or 0)/1e6:.0f}M {f.get('shares_note')} {r['classification'].get('consensus_note')}")
