"""3-stage FCFF DCF (Damodaran-style) + reverse DCF. Pure functions on a dict of inputs."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
import math
from . import assumptions as A


@dataclass
class DCFInputs:
    revenue0: float            # TTM revenue
    margin0: float             # TTM GAAP operating margin (SBC already expensed = real cost)
    margin_target: float
    growth_y1: float
    growth_y2: float
    terminal_g: float
    tax0: float                # effective tax rate now
    tax_marginal: float
    sales_to_capital: float
    roic_now: float
    wacc0: float
    wacc_mature: float
    net_debt: float            # total debt - cash
    shares: float              # diluted shares
    years: int = A.EXPLICIT_YEARS
    roic_fade: float = A.ROIC_FADE
    extra: dict = field(default_factory=dict)


def growth_path(g1, g2, gT, n=A.EXPLICIT_YEARS):
    g = [g1, g2]
    for t in range(3, n + 1):  # linear fade yrs 3..n from g2 to gT
        g.append(g2 + (gT - g2) * (t - 2) / (n - 2))
    return g


def margin_path(m0, mT, n=A.EXPLICIT_YEARS, k=A.MARGIN_CONVERGE_YEARS):
    return [m0 + (mT - m0) * min(t, k) / k for t in range(1, n + 1)]


def run_dcf(i: DCFInputs, detail=True):
    n = i.years
    g = growth_path(i.growth_y1, i.growth_y2, i.terminal_g, n)
    ex = i.extra or {}
    if ex.get("g_cap3") is not None:            # v4: year 3 starts at min(g2, cap), then linear fade to gT
        g3 = min(i.growth_y2, ex["g_cap3"])
        g = g[:2] + [g3 + (i.terminal_g - g3) * (t - 3) / (n - 3) for t in range(3, n + 1)]
    if ex.get("rev_cap_cagr") is not None:      # v4: revenue yrs 3..n at most rev_2 x (1 + top-decile CAGR)^(n-2)
        import math as _m
        lim = (1 + ex["rev_cap_cagr"]) ** (n - 2)
        tail = lambda k: _m.prod(1 + max(x * k, i.terminal_g) if j < n - 3 else 1 + x for j, x in enumerate(g[2:]))
        if tail(1.0) > lim:
            lo, hi = 0.0, 1.0
            for _ in range(60):
                mid = (lo + hi) / 2
                (lo, hi) = (mid, hi) if tail(mid) <= lim else (lo, mid)
            g = g[:2] + [max(x * lo, i.terminal_g) if j < n - 3 else x for j, x in enumerate(g[2:])]
    if ex.get("rev_path"):                      # v5: explicit revenue path (cyclicals: consensus deviation reverts to trend)
        rp = ex["rev_path"]; prev = i.revenue0; g = []
        for r_ in rp[:n]:
            g.append(r_ / prev - 1); prev = r_
    m = margin_path(i.margin0, i.margin_target, n, ex.get("margin_years") or A.MARGIN_CONVERGE_YEARS)
    rows, rev, disc, pv_sum = [], i.revenue0, 1.0, 0.0
    nol = max(0.0, ex.get("nol0") or 0.0)       # v5: loss carryforward pool (pre-tax); losses add, profits use it up
    for t in range(1, n + 1):
        new_rev = rev * (1 + g[t - 1])
        tax = i.tax0 + (i.tax_marginal - i.tax0) * t / n
        ebit = new_rev * m[t - 1]
        if ebit > 0:
            used = min(nol, ebit); nol -= used
            nopat = ebit - (ebit - used) * tax
        else:
            nol += -ebit; nopat = ebit
        # v5 (audit X3): assets are not sold when demand falls -> no capital release on falling revenue
        reinv = max(0.0, new_rev - rev) / i.sales_to_capital
        fcff = nopat - reinv
        h = A.HIGH_GROWTH_YEARS
        w = i.wacc0 if t <= h else i.wacc0 + (i.wacc_mature - i.wacc0) * (t - h) / (n - h)
        disc /= (1 + w)
        pv = fcff * disc
        pv_sum += pv
        if detail:
            rows.append(dict(year=t, growth=g[t - 1], revenue=new_rev, margin=m[t - 1], ebit=ebit, tax=tax,
                             nopat=nopat, reinvestment=reinv, nol=nol, fcff=fcff, wacc=w, discount=disc, pv=pv))
        rev = new_rev
    # terminal: reinvestment rate = g / ROIC_T
    wT, gT = i.wacc_mature, i.terminal_g
    roic_T = wT + min(A.ROIC_EXCESS_CAP, i.roic_fade * max(0.0, i.roic_now - wT))
    rev_T = rev * (1 + gT)
    nopat_T = rev_T * m[-1] * (1 - i.tax_marginal)
    rr = gT / roic_T if roic_T > 0 else 0.0
    fcff_T = nopat_T * (1 - rr)
    tv = fcff_T / (wT - gT)
    pv_tv = tv * disc
    ev = pv_sum + pv_tv
    equity = ev - i.net_debt
    ps = equity / i.shares if i.shares else float("nan")
    out = dict(value_per_share=ps, ev=ev, equity=equity, pv_explicit=pv_sum, pv_terminal=pv_tv,
               terminal_share=pv_tv / ev if ev else None, terminal=dict(roic=roic_T, reinvestment_rate=rr,
               fcff=fcff_T, value=tv, wacc=wT, g=gT))
    if detail:
        out["years"] = rows
        out["inputs"] = {k: v for k, v in asdict(i).items()}
    return out


def _bisect(f, lo, hi, it=80):
    flo, fhi = f(lo), f(hi)
    if math.isnan(flo) or math.isnan(fhi) or flo * fhi > 0:
        return None
    for _ in range(it):
        mid = (lo + hi) / 2
        fm = f(mid)
        if flo * fm <= 0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    return (lo + hi) / 2


def reverse_dcf(i: DCFInputs, price: float):
    """Implied (a) constant revenue growth yrs 1-2 (then same fade) and (b) implied target margin."""
    from dataclasses import replace
    fg = lambda x: run_dcf(replace(i, growth_y1=x, growth_y2=x), detail=False)["value_per_share"] - price
    fm = lambda x: run_dcf(replace(i, margin_target=x), detail=False)["value_per_share"] - price
    g = _bisect(fg, -0.3, 1.5)
    mt = _bisect(fm, -0.2, 0.9)
    cagr5 = None
    if g is not None:
        p = growth_path(g, g, i.terminal_g, i.years)[:5]
        cagr5 = math.prod(1 + x for x in p) ** (1 / 5) - 1
    base5 = math.prod(1 + x for x in growth_path(i.growth_y1, i.growth_y2, i.terminal_g, i.years)[:5]) ** 0.2 - 1
    return dict(implied_growth_y1_2=g, implied_rev_cagr_5y=cagr5, base_rev_cagr_5y=base5,
                implied_margin_target=mt, base_margin_target=i.margin_target)


def sensitivity(i: DCFInputs, rf: float):
    from dataclasses import replace
    waccs = [-0.01, -0.005, 0.0, 0.005, 0.01]
    gts = [-0.01, -0.005, 0.0, 0.005]
    grid1 = []
    for dw in waccs:
        row = []
        for dg in gts:
            gT = min(i.terminal_g + dg, rf)
            row.append(run_dcf(replace(i, wacc0=i.wacc0 + dw, wacc_mature=i.wacc_mature + dw, terminal_g=gT),
                               detail=False)["value_per_share"])
        grid1.append(row)
    dms = [-0.05, -0.025, 0.0, 0.025, 0.05]
    dgs = [-0.05, -0.025, 0.0, 0.025, 0.05]
    grid2 = [[run_dcf(replace(i, margin_target=i.margin_target + dm, growth_y1=i.growth_y1 + dg,
                                growth_y2=i.growth_y2 + dg), detail=False)["value_per_share"] for dg in dgs] for dm in dms]
    return dict(wacc_x_terminal_g=dict(rows_wacc_delta=waccs, cols_g_delta=gts, base_wacc=i.wacc0,
                                       base_g=i.terminal_g, values=grid1),
                margin_x_growth=dict(rows_margin_delta=dms, cols_growth_delta=dgs, base_margin=i.margin_target,
                                     base_growth=[i.growth_y1, i.growth_y2], values=grid2))
