"""Forward-PE module: time-weighted NTM EPS, forward PE vs own history/sector, justified PE
(two-stage equity model with payout = 1 - g/ROE, Gordon terminal; Damodaran ch.18) and fair price."""
from __future__ import annotations
import math
from . import assumptions as A


def ntm_eps(eps_fy0, eps_fy1, months_left_fy0, rev_g_fy1=None):
    """Time-weighted NTM EPS. If FY0 EPS > FY1 EPS while revenue still grows, FY0 is treated as
    containing one-offs and replaced by FY1 / (1 + revenue growth FY1) (documented normalisation)."""
    w = max(0.0, min(1.0, months_left_fy0 / 12.0))
    norm = False
    e0 = eps_fy0
    if eps_fy0 and eps_fy1 and eps_fy1 < eps_fy0 and (rev_g_fy1 or 0) > 0:
        e0, norm = eps_fy1 / (1 + rev_g_fy1), True
    return dict(ntm_eps=w * e0 + (1 - w) * eps_fy1, weight_fy0=w, eps_fy0_used=e0, normalised_fy0=norm)


def justified_pe(ke, g1, roe, gT, years_high=5, years_fade=5):
    """Value of 1 unit of NTM EPS: EPS grows g1 for `years_high` yrs, fades linearly to gT, payout = 1-g/ROE.
    Terminal ROE fades halfway to cost of equity. Returns justified forward PE."""
    roe = max(roe, ke)
    roeT = ke + 0.5 * max(0.0, roe - ke)
    eps, pv, n = 1.0, 0.0, years_high + years_fade
    path = []
    for t in range(1, n + 1):
        g = g1 if t <= years_high else g1 + (gT - g1) * (t - years_high) / years_fade
        r_t = roe + (roeT - roe) * max(0, t - years_high) / years_fade
        payout = max(0.0, 1 - g / r_t)
        if t > 1:
            eps *= 1 + g
        pv += eps * payout / (1 + ke) ** t
        path.append(dict(year=t, g=g, roe=r_t, payout=payout, eps_index=eps))
    payoutT = max(0.0, 1 - gT / roeT)
    tv = eps * (1 + gT) * payoutT / (ke - gT)
    pv += tv / (1 + ke) ** n
    gordon = payoutT / (ke - gT)
    return dict(justified_pe=pv, gordon_mature_pe=gordon, roe_terminal=roeT, path=path)


def forward_block(price, cons_years, months_left, ke, roe, gT, hist_pe=None, sector=None, gaap_eps_ttm=None,
                  scenario="base"):
    y0, y1 = cons_years[0], cons_years[1]
    key = {"base": "eps", "pessimistic": "eps_low", "optimistic": "eps_high"}[scenario]
    e0, e1 = y0.get(key) or y0["eps"], y1.get(key) or y1["eps"]
    nt = ntm_eps(e0, e1, months_left, y1.get("rev_growth"))
    eps_g = (y1["eps"] / nt["eps_fy0_used"] - 1) if nt["eps_fy0_used"] > 0 else None
    cands = [x for x in (eps_g, y0.get("rev_growth"), y1.get("rev_growth")) if x is not None]
    g1 = sorted(cands)[len(cands) // 2] if cands else 0.05
    g1 = max(0.0, min(0.25, g1)) + {"base": 0, "pessimistic": -0.03, "optimistic": 0.03}[scenario]
    g1 = max(0.0, g1)
    jp = justified_pe(ke, g1, roe, gT)
    ntm = nt["ntm_eps"]
    basis_gap = None
    if gaap_eps_ttm and gaap_eps_ttm > 0:
        basis_gap = nt["eps_fy0_used"] / gaap_eps_ttm - 1  # >0 = consensus above GAAP TTM (growth and/or adjusted)
    fwd_pe = price / ntm if ntm > 0 else None
    out = dict(scenario=scenario, ntm=nt, forward_pe=fwd_pe, growth_used=g1, eps_growth_fy1=eps_g,
               cost_of_equity=ke, roe=roe, terminal_g=gT, justified=jp,
               fair_price=jp["justified_pe"] * ntm if ntm > 0 else None,
               peg_reference=(fwd_pe / (g1 * 100)) if fwd_pe and g1 > 0 else None,
               consensus_vs_gaap_ttm=basis_gap)
    if hist_pe:
        out["vs_history"] = hist_pe
    if sector:
        out["vs_sector"] = sector
    return out
