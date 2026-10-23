"""Eine Quelle: Bewertung v4 (data/valuation_v4.json) speist Szenarien, Bewertungskennzahlen, Investment, Swing-Bewertung
und Rohdaten. Kursabhängige Felder werden aus dem Snapshot-Kurs (cases.json price) neu gerechnet. Swing-Regeln v4:
Mindeststopp 1x Tagesspanne (ADR20 als ATR-Näherung), Ziel = nächster Widerstand inkl. gleitender Durchschnitte,
Phase 3/4 = harte Sperre."""
import json
from lib import D

P4 = D / "valuation_v4.json"
V4 = json.loads(P4.read_text())["stocks"] if P4.exists() else {}
STALE_FIELD_PREFIXES = ("valuation.", "valuation_models.", "tranches.", "deep.", "einstieg.", "renditequelle.", "mcap_tam.")
STALE_FIELDS = {"fundamentals.fv2030_konservativ", "fundamentals.cagr_konservativ", "fundamentals.fv2030_basis", "fundamentals.cagr_basis",
                "fundamentals.fv2030_positiv", "fundamentals.cagr_positiv", "fundamentals.fv2030_basis_gaap", "fundamentals.cagr_basis_gaap",
                "fundamentals.fair_value_today", "fundamentals.growth_assumption", "fundamentals.exit_pe", "fundamentals.implied_rev_cagr",
                "fundamentals.target_upside", "fundamentals.peg", "fundamentals.pe_fwd", "fundamentals.price_raw", "chart.levels.L11",
                "chart.buy_zones", "fundamentals.quick_pe_check"}


def scen5(r, c):
    """5-Jahres-Szenarien aus v4: fairer Wert heute = Szenariowert; Kurs in 5 J. = fairer Wert x (1 + Eigenkapitalkosten)^5
    (Wert wächst mit der geforderten Rendite, keine Ausschüttung angenommen); Rendite p. a. = (Kurs 5 J. / Kurs heute)^(1/5) - 1."""
    out = {}; ke = r["cost_of_capital"]["cost_of_equity"]; price = c["price"]
    sh = (r.get("firm") or {}).get("shares_diluted")
    for k_ui, k in (("konservativ", "pessimistic"), ("basis", "base"), ("positiv", "optimistic")):
        s = (r.get("scenarios") or {}).get(k)
        if not s:
            continue
        fv = s["fair_value"]; p5 = fv * (1 + ke) ** 5
        ys = (s.get("model_detail") or {}).get("years") or []
        if len(ys) >= 5 and sh and "nopat" in ys[4]:
            y5 = ys[4]; eps5 = y5["nopat"] / sh; m5 = y5["nopat"] / y5["revenue"]; g0, g1 = ys[0]["growth"], ys[4]["growth"]
        else:
            g = s.get("growth") or (None, None); ni = (r.get("firm") or {}).get("net_income_ttm")
            eps5 = ni / sh * (1 + (g[1] or 0)) ** 5 if ni and sh else None; m5 = None; g0, g1 = g[0], g[1]
        cagr = (p5 / price) ** 0.2 - 1 if price and p5 > 0 else -1.0
        out[k_ui] = dict(cagr=cagr, cagr_price=cagr, price=p5, fv_today=fv, exit_pe=p5 / eps5 if eps5 and eps5 > 0 else None,
                         eps=eps5, margin=m5, g_start=g0, g_end=g1, sh_yield=0.0, src="v4")
    return out


def apply(CASES):
    for sym, c in CASES.items():
        r = V4.get(sym); price = c.get("price")
        ok = bool(r and r.get("status") == "ok")
        rv = bool(ok and r.get("reliable") and r.get("range_valid", True) and r.get("display_mode", "value") == "value")
        c["v4"] = dict(ok=ok, reliable=rv, display_mode=(r or {}).get("display_mode"), reasons=(r or {}).get("unreliable_reasons") or ([] if ok else [(r or {}).get("status") or "keine Bewertung"]),
                       archetype=(r or {}).get("archetype"))
        if ok and rv:   # v5: Szenarien nur bei gültiger Spanne (keine 0–x-Spannen)
            sc = scen5(r, c)
            if len(sc) == 3:
                nm = ((c.get("annual") or [{}])[-1] or {}).get("net_margin")
                for v in sc.values():
                    if v["margin"] is None: v["margin"] = nm if nm is not None else 0.0
                    if v["g_start"] is None: v["g_start"] = 0.0
                    if v["g_end"] is None: v["g_end"] = v["g_start"]
                c["scenarios"] = sc; c["scen_src"] = "v4"
            rd = r.get("reverse_dcf") or {}
            c["val_criteria"] = [
                dict(name="Basis-Rendite p. a. (5 Jahre, Bewertung v4)", value=sc["basis"]["cagr"], ampel="grün" if sc["basis"]["cagr"] >= .10 else "rot" if sc["basis"]["cagr"] < .08 else "gelb", range="rot < 8 %, grün ≥ 10 %", fmt="pct", note=None),
                dict(name="Konservative Rendite p. a. (5 Jahre, Bewertung v4)", value=sc["konservativ"]["cagr"], ampel="grün" if sc["konservativ"]["cagr"] >= .035 else "rot" if sc["konservativ"]["cagr"] < -.05 else "gelb", range="rot < −5 %, grün ≥ 3,5 %", fmt="pct", note=None)]
            if rd.get("implied_rev_cagr_5y") is not None:
                c["val_criteria"].append(dict(name="Eingepreistes Umsatzwachstum p. a. (Reverse-DCF, 5 Jahre)", value=rd["implied_rev_cagr_5y"], ampel="gelb" if rd["implied_rev_cagr_5y"] > (rd.get("base_rev_cagr_5y") or 0) else "grün",
                                              range="gelb, wenn über dem Basisszenario", fmt="pct", note=f"Basisszenario {rd.get('base_rev_cagr_5y', 0) * 100:.1f} %".replace(".", ",")))
        else:
            c["scen_src"] = "scanner"; c["val_criteria"] = []      # Szenarien-Reiter blendet sie aus (keine v4-Bewertung)
        # kursabhängige Felder auf den Snapshot-Kurs
        ks = c.get("keystats") or {}
        sh = (r or {}).get("firm", {}).get("shares_diluted") if ok and (r or {}).get("firm") else None
        if price and ks:
            old_mcap = ks.get("mcap")
            if sh: ks["mcap"] = price * sh
            elif old_mcap and c.get("mcap_bn"): ks["mcap"] = c["mcap_bn"] * 1e9
            if ks.get("mcap") and old_mcap is not None and ks.get("ev") is not None: ks["ev"] = ks["ev"] - old_mcap + ks["mcap"]
            if ks.get("eps_ttm"): ks["pe_ttm"] = price / ks["eps_ttm"] if ks["eps_ttm"] > 0 else None
            if ks.get("revenue_ttm") and ks.get("mcap"): ks["ps_ttm"] = ks["mcap"] / ks["revenue_ttm"]
        a = c.get("analyst") or {}
        tg = (a.get("targets") or {})
        if price and tg.get("median"):
            a["upside_med"] = tg["median"] / price - 1
            a["target_returns"] = {k: (tg.get(v) / price - 1) if tg.get(v) else None for k, v in (("tief", "low"), ("median", "median"), ("hoch", "high"))}
        # Swing v4
        sma30, slope = c.get("sma30w"), c.get("sma30w_slope")
        if price and sma30 and slope is not None:
            stg = 2 if price > sma30 and slope > 0 else 4 if price < sma30 and slope <= 0 else 3 if price < sma30 else 1
            c["stage"] = stg; c["stage_block"] = stg in (3, 4)
            if stg != 2 and "kein Stage 2" not in (c.get("stage_text") or ""):
                c["stage_text"] = f"kein Stage 2: Phase {stg}"
        p = c.get("plan") or {}
        if p and p.get("stop") and price:
            lv = list(p.get("limits") or [p.get("zone")]); lv = [x for x in lv if x]
            if lv:
                avg = sum(lv) / len(lv); atr = (c.get("adr20") or 0) * price
                if atr and p["stop"] > avg - atr:
                    p["stop_orig"] = p["stop"]; p["stop"] = avg - atr; p["stop_rule"] = "Mindestabstand 1× Ø Tagesspanne (20 Tage)"
    return CASES


def fields_filter(df, sym, c):
    keep = df.feld.str.startswith(("deep.annual", "valuation.v4"))
    df = df[keep | ~df.feld.str.startswith(STALE_FIELD_PREFIXES) & ~df.feld.isin(STALE_FIELDS) & ~df.feld.str.startswith(tuple(f + "[" for f in STALE_FIELDS)) & ~df.feld.str.startswith(tuple(f + "." for f in STALE_FIELDS))].copy()
    df = df[~df.feld.str.startswith("chart.levels.L12") & ~df.feld.str.startswith("chart.levels.L13")]
    price = c.get("price"); ks = c.get("keystats") or {}
    upd = {"fundamentals.price": price, "chart.price": price, "chart.levels.px": price, "price_path.price": price,
           "fundamentals.mcap": ks.get("mcap"), "fundamentals.ev": ks.get("ev"), "fundamentals.pe_ttm": ks.get("pe_ttm"), "fundamentals.ps_ttm": ks.get("ps_ttm"),
           "mcap_tam.mcap": ks.get("mcap"), "hist_multiples.pe_ttm": ks.get("pe_ttm"), "hist_multiples.ps_ttm": ks.get("ps_ttm"),
           "peers.own.mcap": ks.get("mcap"), "peers.own.pe": ks.get("pe_ttm"), "peers.own.ps": ks.get("ps_ttm")}
    for k, v in upd.items():
        if v is not None and (df.feld == k).any():
            df.loc[df.feld == k, "wert"] = str(v)
    r = V4.get(sym)
    if r and r.get("status") == "ok":
        rv = r.get("range_valid", r.get("reliable")) and r.get("display_mode", "value") == "value"
        add = {"valuation.v4.archetype": r["archetype"]["name"], "valuation.v4.display_mode": r.get("display_mode"),
               "valuation.v4.fair_value": r["range"]["base"] if rv else None, "valuation.v4.pessimistic": r["range"]["pessimistic"] if rv else None,
               "valuation.v4.optimistic": r["range"]["optimistic"] if rv else None, "valuation.v4.buy_below": r["buy_zone_below"] if rv else None,
               "valuation.v4.implied_roic_new": (r.get("implied_return") or {}).get("value"),
               "valuation.v4.reliable": r.get("reliable"), "valuation.v4.wacc": r["cost_of_capital"].get("wacc"), "valuation.v4.price": r["price"]}
        import pandas as pd
        df = pd.concat([df, pd.DataFrame([dict(feld=k, wert=str(v)) for k, v in add.items() if v is not None])], ignore_index=True)
    return df
