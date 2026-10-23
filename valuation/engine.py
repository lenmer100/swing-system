"""Combine DCF + forward PE into one fair value with economically argued scenarios."""
from __future__ import annotations
from dataclasses import replace
import math
import pandas as pd
from . import assumptions as A
from .dcf import DCFInputs, run_dcf, reverse_dcf, sensitivity
from .capital import wacc as wacc_fn, combine_beta
from .forward_pe import forward_block
from . import inputs as I


def _clip(x, lo, hi):
    return max(lo, min(hi, x))


def build_dcf_inputs(fs, sec, cap, g1, g2, gT, tax_eff, tax_m, scenario="base"):
    own, smed = fs["margin_3y_median"], sec.get("margin_median") if sec else None
    if smed is None or not math.isfinite(smed):
        smed = own
    if scenario == "base":
        mT = own + A.MARGIN_REVERSION * (smed - own)
    elif scenario == "pessimistic":   # worst of own median / current / sector (full adverse reversion)
        mT = min(own, fs["margin_ttm"], smed)
    else:                             # optimistic: best of own median / current / sector
        mT = max(own, fs["margin_ttm"], smed)
    s2c = fs["sales_to_capital_cycle"] or fs["sales_to_capital_raw"]
    cands = [x for x in (fs["sales_to_capital_cycle"], fs["sales_to_capital_raw"]) if x]
    if scenario == "pessimistic" and cands:   # current capex wave persists (lower capital efficiency)
        s2c = min(cands)
    elif scenario == "optimistic" and cands:
        s2c = max(cands)
    s2c_src = ("eigene Historie, Median rollierender 3J-Fenster (bis 10J)" if fs["sales_to_capital_cycle"]
               else "eigene letzte 3J (dUmsatz/dInvestiertes Kapital)")
    if s2c is None:
        s2c, s2c_src = (sec or {}).get("s2c_median") or A.S2C_FALLBACK, "Sektormedian (eigene Historie nicht verwertbar)"
    s2c = _clip(s2c, *A.S2C_BOUNDS)
    ic = fs["invested_capital"] or 0
    roic = fs["ebit_ttm"] * (1 - tax_eff) / ic if ic > 0 else cap["wacc"]
    i = DCFInputs(revenue0=fs["revenue_ttm"], margin0=fs["margin_ttm"], margin_target=mT,
                  growth_y1=_clip(g1, *A.GROWTH_CLIP), growth_y2=_clip(g2, *A.GROWTH_CLIP), terminal_g=gT,
                  tax0=tax_eff, tax_marginal=tax_m, sales_to_capital=s2c, roic_now=roic,
                  wacc0=cap["wacc"], wacc_mature=cap["wacc_mature"],
                  net_debt=fs["total_debt"] - fs["cash"], shares=fs["shares_diluted"])
    i.extra = dict(margin_own_3y_median=own, margin_sector_median=smed, s2c_source=s2c_src, scenario=scenario)
    return i


def value_stock(t, asof, price, cons, sectors, typ=None):
    typ = typ or I.type_map().get(t)
    sec = sectors.get(typ, {})
    fs = I.firm_stats(t, asof)
    if fs is None:
        return dict(ticker=t, status="keine EDGAR-Daten")
    if typ in A.FINANCIAL_TYPES:
        return dict(ticker=t, status="FCFF-DCF nicht anwendbar (Finanzwert)")
    rf = I.risk_free(asof)
    gT = min(rf, A.TERMINAL_G_CAP)
    year = pd.Timestamp(asof).year
    tax_m = A.marginal_tax(A.COUNTRY.get(t, "US"), year)
    eff, interest = I.tax_and_interest(t, asof)
    tax_eff = _clip(eff if eff is not None else tax_m, 0.05, tax_m)
    own_b, nb = I.own_beta(t, asof)
    beta = combine_beta(own_b, sec.get("beta_median"))
    mcap = price * fs["shares_diluted"]
    cap = wacc_fn(rf, beta, mcap, fs["total_debt"], fs["ebit_ttm"], interest, tax_m)
    cap.update(beta_regression_blume=own_b, beta_months=nb, beta_sector_median=sec.get("beta_median"))

    yrs = cons["years"]
    g = {"base": (yrs[0]["rev_growth"], yrs[1]["rev_growth"])}
    rev_last_fy = yrs[0]["rev"] / (1 + yrs[0]["rev_growth"])
    g["pessimistic"] = (yrs[0]["rev_low"] / rev_last_fy - 1, yrs[1]["rev_low"] / yrs[0]["rev_low"] - 1)
    g["optimistic"] = (yrs[0]["rev_high"] / rev_last_fy - 1, yrs[1]["rev_high"] / yrs[0]["rev_high"] - 1)

    fy_m, last_fy_end = I.fy_end_month(t)
    fy0_end = last_fy_end + pd.DateOffset(years=1) if last_fy_end is not None else pd.Timestamp(year, 12, 31)
    while fy0_end < pd.Timestamp(asof):
        fy0_end += pd.DateOffset(years=1)
    months_left = (fy0_end - pd.Timestamp(asof)).days / 30.44
    hist = I.pe_history(t, asof, price)
    sec_pe = dict(median=sec.get("pe_median"), n=sec.get("pe_n"), basis="trailing GAAP",
                  used=bool(sec.get("pe_n") and sec["pe_n"] >= A.MIN_PEERS))
    roe = (fs["net_income_ttm"] / fs["equity"]) if fs["equity"] and fs["equity"] > 0 and fs["net_income_ttm"] else 0.12
    roe = _clip(roe, 0.05, 0.40)

    defence = t in A.DEFENCE
    scen = {}
    for s in ("pessimistic", "base", "optimistic"):
        di = build_dcf_inputs(fs, sec, cap, *g[s], gT, tax_eff, tax_m, s)
        d = run_dcf(di, detail=(s == "base"))
        fp = forward_block(price, yrs, months_left, cap["cost_of_equity"], roe, gT,
                           hist_pe=hist if s == "base" else None, sector=sec_pe if s == "base" else None,
                           gaap_eps_ttm=(hist or {}).get("gaap_eps_ttm"), scenario=s)
        fv = A.WEIGHT_DCF * d["value_per_share"] + A.WEIGHT_PE * (fp["fair_price"] or d["value_per_share"])
        scen[s] = dict(fair_value=fv, dcf=d, forward_pe=fp, dcf_value=d["value_per_share"], pe_value=fp["fair_price"])
        if s == "base":
            base_inputs = di
    order = sorted(scen, key=lambda k: scen[k]["fair_value"])
    base = scen["pessimistic" if defence else "base"]
    rev = reverse_dcf(base_inputs, price)
    sens = sensitivity(base_inputs, rf)
    return dict(ticker=t, status="ok", asof=str(pd.Timestamp(asof).date()), price=price, type=typ,
                basis="GAAP pessimistisch (Rüstung)" if defence else "GAAP (SBC als Kosten)",
                fair_value=base["fair_value"], upside=base["fair_value"] / price - 1,
                range=dict(pessimistic=scen["pessimistic"]["fair_value"], base=scen["base"]["fair_value"],
                           optimistic=scen["optimistic"]["fair_value"]),
                weights=dict(dcf=A.WEIGHT_DCF, forward_pe=A.WEIGHT_PE),
                firm=fs, cost_of_capital=cap, terminal_growth=gT, tax=dict(effective_3y=eff, used_start=tax_eff, marginal=tax_m),
                sector=dict(type=typ, **{k: v for k, v in sec.items() if k != "tickers"}, peers_sample=sec.get("tickers", [])[:15]),
                consensus=dict(snapshot=cons.get("snapshot"), years=yrs, fy0_end=str(fy0_end.date()), months_left_fy0=months_left),
                scenarios=scen, reverse_dcf=rev, sensitivity=sens,
                scenario_logic=dict(
                    pessimistic="Umsatz = Konsens-Tiefstschätzung FY0/FY1; Zielmarge = min(3J-Median, aktuell, Sektormedian); Kapitaleffizienz = schlechtere aus letzten 3J und Zyklusmedian; EPS-Tief, Wachstum -3 Pp.",
                    base="Umsatz = Konsens-Mittel; Zielmarge = eigener 3J-Median + 50 % der Lücke zum Sektormedian; EPS-Konsens",
                    optimistic="Umsatz = Konsens-Höchstschätzung; Zielmarge = max(3J-Median, aktuell, Sektormedian); bessere Kapitaleffizienz; EPS-Hoch, +3 Pp."))
