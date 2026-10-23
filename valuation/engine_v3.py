"""Valuation v3: implied ERP (Damodaran, same month as rf), model by business type, moat/stage/cycle rules,
uncertainty-based buy zone. Rules in rules_v3.py, documented in design_ref/VALUATION_V3.md."""
from __future__ import annotations
from dataclasses import replace
import math
import pandas as pd
from . import assumptions as A, rules_v3 as R, inputs as I
from .history import long_window
from .dcf import DCFInputs, run_dcf, reverse_dcf, sensitivity, growth_path
from .capital import wacc as wacc_fn, combine_beta
from .forward_pe import forward_block


def _clip(x, lo, hi):
    return max(lo, min(hi, x))


def excess_returns(bv, roe0, ke, g1, g2, gT, share, n=R.EXPLICIT_YEARS):
    """Equity excess-return model (Damodaran ch.21): value = BV + PV of (ROE - ke) x BV."""
    roeT = ke + share * max(0.0, roe0 - ke)
    gs = growth_path(g1, g2, gT, n)
    b, pv, rows = bv, bv, []
    for t in range(1, n + 1):
        roe = roe0 + (roeT - roe0) * t / n
        g = min(gs[t - 1], roe)                       # book growth cannot exceed ROE (retention <= 1)
        ex = (roe - ke) * b
        pv += ex / (1 + ke) ** t
        rows.append(dict(year=t, roe=roe, book=b, excess=ex))
        b *= 1 + g
    tv = (roeT - ke) * b * (1 + gT) / (ke - gT) / (1 + ke) ** n
    return dict(equity=pv + tv, pv_terminal=tv, roe_terminal=roeT, years=rows)


def affo_model(affo0, book, ke, g1, g2, gT, n=R.EXPLICIT_YEARS):
    """REIT: FCFE ~ AFFO x (1 - g/ROE_affo); AFFO approximated by FFO (maintenance capex not separable on disk)."""
    roe = max(affo0 / book, ke) if book and book > 0 else ke
    gs = growth_path(g1, g2, gT, n)
    a, pv = affo0, 0.0
    for t in range(1, n + 1):
        a *= 1 + gs[t - 1]
        pv += a * max(0.0, 1 - gs[t - 1] / roe) / (1 + ke) ** t
    tv = a * (1 + gT) * max(0.0, 1 - gT / roe) / (ke - gT) / (1 + ke) ** n
    return dict(equity=pv + tv, pv_terminal=tv, roe_affo=roe)


def classify(t, typ, fs, lw, cap, g_stage, cons=None):
    cyc = typ in R.CYCLICAL_TYPES
    model = "excess_returns" if typ in R.EXCESS_RETURN_TYPES else "affo" if typ in R.REIT_TYPES else "fcff"
    # R4 (v3.1): moat on ROIC ex goodwill where goodwill data exists (acquisitions not penalised), else ROIC incl. goodwill
    rk = "roic_ex_goodwill_median" if lw and lw.get("roic_ex_goodwill_median") is not None else "roic_median"
    excess = (lw[rk] - cap["wacc"]) if lw and lw.get(rk) is not None else None
    moat = R.moat(excess, (lw or {}).get("margin_median"))
    stg = R.stage(g_stage)
    fcf_ni = None
    if fs.get("net_income_ttm") and fs.get("fcf_ttm") is not None and fs["net_income_ttm"] > 0:
        fcf_ni = fs["fcf_ttm"] / fs["net_income_ttm"]
    reinvester = fcf_ni is None or fcf_ni < R.REINVESTER_FCF_TO_NI
    unc = mos = disp = None
    if cons:
        y1 = cons["years"][1]
        if y1.get("eps_high") is not None and y1.get("eps_low") is not None and y1.get("eps"):
            disp = (y1["eps_high"] - y1["eps_low"]) / abs(y1["eps"])
        unc, mos = R.uncertainty(disp)
    return dict(model=model, cyclical=cyc, moat=moat, excess_roic_long=excess, moat_basis="ROIC ohne Goodwill" if rk == "roic_ex_goodwill_median" else "ROIC inkl. Goodwill", stage=stg, growth_for_stage=g_stage,
                fcf_to_ni=fcf_ni, reinvester=reinvester, uncertainty=unc, margin_of_safety=mos, eps_dispersion=disp,
                defence=t in A.DEFENCE)


def _fcf(t, asof):
    r = I.fund_asof(t, asof)
    if r is None:
        return None
    v = r.get("fcf_ttm") if "fcf_ttm" in r.index else None
    if v is not None and pd.notna(v):
        return float(v)
    o, c = r.get("op_cash_flow_ttm"), r.get("capex_ttm")
    return float(o - abs(c)) if pd.notna(o) and pd.notna(c) else None


import functools as _ft


@_ft.lru_cache(None)
def _cases_mcap():
    p = __import__("pathlib").Path(__file__).resolve().parents[1] / "data" / "cases.json"
    return {k: v.get("mcap_bn") for k, v in __import__("json").loads(p.read_text()).items()} if p.exists() else {}


def value_v3(t, asof, price, sectors, typ=None, cons=None, growth=None, detail=True):
    """cons: consensus dict (live); growth: (g1, g2) override for backtest (trailing CAGR)."""
    typ = typ or I.type_map().get(t)
    sec = sectors.get(typ, {})
    fs = I.firm_stats(t, asof)
    if (fs is None or not fs.get("shares_diluted")) and typ in (R.EXCESS_RETURN_TYPES | R.REIT_TYPES):
        return value_financial(t, asof, price, sec, typ, cons, growth)
    if fs is None or not fs.get("shares_diluted"):
        return dict(ticker=t, status="keine EDGAR-Daten")
    fs["fcf_ttm"] = _fcf(t, asof)
    fs["shares_note"] = None
    _yi = __import__("pathlib").Path(__import__("os").environ.get("MARKET_STORE", "data_store") + "/derived/yf_info") / f"{t}.json"
    _mc = __import__("json").loads(_yi.read_text()).get("marketCap") if _yi.exists() else None
    if not _mc:
        _mc = (_cases_mcap().get(t) or 0) * 1e9 or None     # demo snapshot market cap (same price date)
    if _mc and price:
        if _mc and not R.SHARE_CHECK[0] <= (_mc / price) / fs["shares_diluted"] <= R.SHARE_CHECK[1]:
            fs["shares_note"] = f"Aktienzahl korrigiert: EDGAR {fs['shares_diluted'] / 1e6:,.1f} Mio. -> Börsenwert/Kurs {_mc / price / 1e6:,.1f} Mio."
            fs["shares_diluted"] = _mc / price
    e = R.erp_asof(asof); rf, erp = e["rf"], e["erp"]
    gT = min(rf, A.TERMINAL_G_CAP)
    tax_m = A.marginal_tax(A.COUNTRY.get(t, "US"), pd.Timestamp(asof).year)
    eff, interest = I.tax_and_interest(t, asof)
    tax_eff = _clip(eff if eff is not None else tax_m, 0.05, tax_m)
    own_b, nb = I.own_beta(t, asof)
    beta = combine_beta(own_b, sec.get("beta_median"))
    mcap = price * fs["shares_diluted"]
    cap = wacc_fn(rf, beta, mcap, fs["total_debt"], fs["ebit_ttm"], interest, tax_m, erp=erp)
    cap.update(erp_month=e["month"], erp_basis=e["basis"], beta_regression_blume=own_b, beta_sector_median=sec.get("beta_median"))
    lw = long_window(t, asof, tax_m)

    if cons and any(y.get(k) is None for y in cons["years"][:2] for k in ("rev", "rev_growth", "rev_low", "rev_high")):
        cons = None                                            # incomplete consensus -> treated as no consensus
    cons_note = None
    rep_cur = fs.get("currency_reported") or "USD"
    if cons:
        y0 = cons["years"][0]; base_rev = y0["rev"] / (1 + y0["rev_growth"])
        if rep_cur != "USD":                                   # Yahoo consensus in reporting currency -> USD for the level check
            from .edgar_supp import _fx
            fxs = _fx(rep_cur, [pd.Timestamp(asof)]); base_rev = base_rev * float(fxs.iloc[0]) if fxs is not None else base_rev
        if not 0.67 <= base_rev / fs["revenue_ttm"] <= 1.5:   # consensus revenue base inconsistent with EDGAR (currency/unit/period) -> unusable
            cons, cons_note = None, f"Konsens verworfen: Umsatzbasis {base_rev / fs['revenue_ttm']:.2f}x EDGAR"
    if cons:
        y = cons["years"]; rev_last = y[0]["rev"] / (1 + y[0]["rev_growth"])
        G = {"base": (y[0]["rev_growth"], y[1]["rev_growth"]),
             "pessimistic": (y[0]["rev_low"] / rev_last - 1, y[1]["rev_low"] / y[0]["rev_low"] - 1),
             "optimistic": (y[0]["rev_high"] / rev_last - 1, y[1]["rev_high"] / y[0]["rev_high"] - 1)}
        g_stage = y[1]["rev_growth"]
    else:
        g = growth if growth is not None else (fs["rev_cagr_3y"] if fs["rev_cagr_3y"] is not None else 0.03)
        g = _clip(g, *A.BACKTEST_G_CLIP)
        G = {"base": (g, g), "pessimistic": (g - 0.05, g - 0.05), "optimistic": (g + 0.05, g + 0.05)}
        g_stage = g
    cl = classify(t, typ, fs, lw, cap, g_stage, cons)

    # margins: normal-cycle for cyclicals, else own 3y median; reversion by moat
    own = lw["margin_median"] if (cl["cyclical"] and lw and lw["long_enough"]) else fs["margin_3y_median"]
    smed = sec.get("margin_median")
    smed = own if smed is None or not math.isfinite(smed) else smed
    rev_share = R.REVERSION[cl["moat"]]
    targets = {"base": own + rev_share * (smed - own),
               "pessimistic": min(own + rev_share * (smed - own), smed, own),
               "optimistic": max(own, smed if rev_share > 0 else own, fs["margin_ttm"] if not cl["cyclical"] else own)}
    m0 = own if cl["cyclical"] else fs["margin_ttm"]       # cyclicals start from normal-cycle margin
    s2c_c, s2c_r = fs.get("sales_to_capital_cycle"), fs.get("sales_to_capital_raw")
    s2c_base = s2c_c or s2c_r or sec.get("s2c_median") or A.S2C_FALLBACK
    cands = [x for x in (s2c_c, s2c_r) if x] or [s2c_base]
    S2C = {"base": s2c_base, "pessimistic": min(cands), "optimistic": max(cands)}
    ic = fs["invested_capital"] or 0
    roic_now = (lw or {}).get("roic_median") or (fs["ebit_ttm"] * (1 - tax_eff) / ic if ic > 0 else cap["wacc"])

    w_dcf = R.DCF_WEIGHT[cl["stage"]]
    if cl["reinvester"] or not cons or rep_cur != "USD":   # PE block needs USD EPS per listed share; foreign consensus EPS is local/ordinary-share
        w_dcf = 1.0                                      # PE block dropped for reinvesters (and in backtest: no PIT consensus)
    scen = {}
    for s in ("pessimistic", "base", "optimistic"):
        g1, g2 = G[s]
        if cl["model"] == "fcff":
            di = DCFInputs(revenue0=fs["revenue_ttm"], margin0=m0, margin_target=targets[s],
                           growth_y1=_clip(g1, *A.GROWTH_CLIP), growth_y2=_clip(g2, *A.GROWTH_CLIP), terminal_g=gT,
                           tax0=tax_eff, tax_marginal=tax_m, sales_to_capital=_clip(S2C[s], *A.S2C_BOUNDS), roic_now=roic_now,
                           wacc0=cap["wacc"], wacc_mature=cap["wacc_mature"], net_debt=fs["total_debt"] - fs["cash"],
                           shares=fs["shares_diluted"], years=R.EXPLICIT_YEARS, roic_fade=R.TERMINAL_EXCESS_SHARE[cl["moat"]])
            d = run_dcf(di, detail=detail and s == "base"); intrinsic = d["value_per_share"]
            if s == "base":
                base_inputs = di
        elif cl["model"] == "excess_returns":
            roe0 = _clip((fs["net_income_ttm"] or 0) / fs["equity"], -0.2, 0.4) if fs.get("equity") else cap["cost_of_equity"]
            d = excess_returns(fs["equity"] or 0, roe0, cap["cost_of_equity"], g1, g2, gT, R.TERMINAL_EXCESS_SHARE[cl["moat"]])
            intrinsic = d["equity"] / fs["shares_diluted"]
        else:
            r = I.fund_asof(t, asof); ffo = r.get("ffo_ttm") if r is not None and "ffo_ttm" in r.index else None
            if ffo is None or pd.isna(ffo) or ffo <= 0:
                return dict(ticker=t, status="REIT ohne FFO-Daten", classification=cl)
            d = affo_model(float(ffo), fs.get("equity"), cap["cost_of_equity"], g1, g2, gT)
            intrinsic = d["equity"] / fs["shares_diluted"]
        fp = None; pe_val = None
        if cons and w_dcf < 1.0:
            fp = forward_block(price, cons["years"], cons.get("months_left_fy0", 6), cap["cost_of_equity"],
                               _clip((fs["net_income_ttm"] or 0) / fs["equity"], 0.05, 0.40) if fs.get("equity") else 0.12, gT, scenario=s)
            pe_val = fp["fair_price"]
        fv = w_dcf * intrinsic + (1 - w_dcf) * (pe_val if pe_val else intrinsic)
        scen[s] = dict(fair_value=fv, intrinsic=intrinsic, pe_value=pe_val, model_detail=d, forward_pe=fp, margin_target=targets.get(s))
    base = scen["pessimistic" if cl["defence"] else "base"]
    cl["consensus_note"] = cons_note; cl["only_annual"] = fs.get("only_annual", False)
    cl["stale"] = (pd.Timestamp(asof) - pd.Timestamp(fs["last_quarter_end"])).days > R.STALE_DAYS   # 'Zahlen veraltet'
    cl["reporting_currency"] = rep_cur
    out = dict(ticker=t, status="ok", asof=str(pd.Timestamp(asof).date()), price=price, type=typ, classification=cl,
               fair_value=base["fair_value"], upside=base["fair_value"] / price - 1,
               range=dict(pessimistic=min(x["fair_value"] for x in scen.values()), base=base["fair_value"],
                          optimistic=max(x["fair_value"] for x in scen.values())),
               weights=dict(dcf=w_dcf, forward_pe=1 - w_dcf), cost_of_capital=cap, terminal_growth=gT,
               margin=dict(start=m0, own_basis=own, own_basis_kind="Zyklusmedian bis 10J" if cl["cyclical"] and lw and lw["long_enough"] else "eigener 3J-Median",
                           sector_median=smed, reversion_share=rev_share, targets=targets),
               long_window=lw, firm=fs if detail else None, scenarios=scen if detail else None,
               sotp=dict(applied=False, reason="EDGAR companyfacts liefert keine Segment-Dimensionen; Segmentparsing der 10-K-Anhänge nicht implementiert -> konsolidiertes Modell mit Langfrist-ROIC-Moat (dokumentierter Fallback)"))
    out["buy_zone_below"] = base["fair_value"] * (1 - (cl["margin_of_safety"] if cl["margin_of_safety"] is not None else R.MOS_NO_ESTIMATES))
    if detail and cl["model"] == "fcff":
        out["reverse_dcf"] = reverse_dcf(base_inputs, price)
        out["sensitivity"] = sensitivity(base_inputs, rf)
    return out


def value_financial(t, asof, price, sec, typ, cons=None, growth=None):
    """Banks/insurers (excess returns on book) and REITs (AFFO~FFO) when the FCFF inputs (revenue/EBIT) are
    absent in EDGAR. Needs only book equity, net income / FFO and diluted shares (point-in-time)."""
    r = I.fund_asof(t, asof)
    gv = lambda k: float(r[k]) if r is not None and k in r.index and pd.notna(r[k]) else None
    bv, ni, sh = gv("equity"), gv("net_income_ttm"), gv("shares_best") or gv("shares_dil")
    if not bv or bv <= 0 or ni is None or not sh:
        return dict(ticker=t, status="keine EDGAR-Daten")
    e = R.erp_asof(asof); rf, erp = e["rf"], e["erp"]; gT = min(rf, A.TERMINAL_G_CAP)
    own_b, _ = I.own_beta(t, asof); beta = combine_beta(own_b, sec.get("beta_median"))
    ke = rf + beta * erp
    if cons:
        y = cons["years"]; g = y[1].get("rev_growth") or y[0].get("rev_growth") or 0.03
    elif growth is not None:
        g = growth
    else:
        r3, r0 = gv("revenue_ttm_l12"), gv("revenue_ttm")
        g = (r0 / r3) ** (1 / 3) - 1 if r3 and r0 and r3 > 0 and r0 > 0 else 0.03
    g = _clip(g, *A.BACKTEST_G_CLIP)
    lw = long_window(t, asof)
    nis = [x for x in (ni, gv("net_income_ttm_l4"), gv("net_income_ttm_l12")) if x is not None]
    roe0 = _clip(float(pd.Series(nis).median()) / bv, -0.2, 0.4)   # normalised: median of TTM, -1y, -3y (as 3y-median margin rule)
    roe_long = (lw or {}).get("roe_median")
    excess = (roe_long if roe_long is not None else roe0) - ke
    cl = classify(t, typ, dict(net_income_ttm=ni, fcf_ttm=None), None, dict(wacc=ke), g, cons)
    cl.update(moat=R.moat(excess, 1.0), excess_roic_long=excess, reinvester=False, basis="Eigenkapitalrendite (ROE) statt ROIC")
    share = R.TERMINAL_EXCESS_SHARE[cl["moat"]]
    scen = {}
    for s, dg in (("pessimistic", -0.05), ("base", 0.0), ("optimistic", 0.05)):
        if cl["model"] == "excess_returns":
            d = excess_returns(bv, roe0 + (dg / 5), ke, g + dg, g + dg, gT, share)
        else:
            ffo = gv("ffo_ttm")
            if not ffo or ffo <= 0:
                return dict(ticker=t, status="REIT ohne FFO-Daten")
            d = affo_model(ffo, bv, ke, g + dg, g + dg, gT)
        v = d["equity"] / sh
        scen[s] = dict(fair_value=v, intrinsic=v, pe_value=None, model_detail=d, forward_pe=None, margin_target=None)
    vals = [x["fair_value"] for x in scen.values()]
    base = scen["pessimistic" if cl["defence"] else "base"]["fair_value"]
    mos = cl["margin_of_safety"] if cl["margin_of_safety"] is not None else R.MOS_NO_ESTIMATES
    return dict(ticker=t, status="ok", asof=str(pd.Timestamp(asof).date()), price=price, type=typ, classification=cl,
                fair_value=base, upside=base / price - 1, range=dict(pessimistic=min(vals), base=base, optimistic=max(vals)),
                weights=dict(dcf=1.0, forward_pe=0.0), terminal_growth=gT,
                cost_of_capital=dict(cost_of_equity=ke, wacc=ke, rf=rf, erp=erp, beta=beta, erp_month=e["month"], erp_basis=e["basis"]),
                firm=dict(equity=bv, net_income_ttm=ni, shares_diluted=sh, roe_ttm=ni / bv), scenarios=scen,
                buy_zone_below=base * (1 - mos), reverse_dcf=None, sensitivity=None,
                sotp=dict(applied=False, reason="Finanzwert: Bewertung auf Eigenkapitalbasis"))
