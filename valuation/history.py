"""Long-window point-in-time history per firm: TTM operating margin and ROIC over up to 10 years."""
from __future__ import annotations
import numpy as np, pandas as pd
from . import inputs as I, assumptions as A, rules_v3 as R


def long_window(t, asof, tax=0.25):
    f = I.fund(t)
    if f is None:
        return None
    f = f[f.avail_date <= pd.Timestamp(asof)].tail(R.CYCLE_QUARTERS)
    if "operating_income_ttm" not in f:
        return None
    from .goodwill import goodwill_asof
    m, roic, roic_x = [], [], []
    for r in f.itertuples(index=False):
        rr = pd.Series(r._asdict())
        if not rr.revenue_ttm or pd.isna(rr.operating_income_ttm):
            continue
        m.append(rr.operating_income_ttm / rr.revenue_ttm)
        ic = I.invested_capital(rr, t)
        if ic and ic > 0:
            roic.append(rr.operating_income_ttm * (1 - tax) / ic)
            gw = goodwill_asof(t, rr.avail_date, rr.last_quarter_end if "last_quarter_end" in rr and pd.notna(rr.last_quarter_end) else None)
            if gw is not None and ic - gw > 0:
                roic_x.append(rr.operating_income_ttm * (1 - tax) / (ic - gw))
    n = len(m)
    return dict(n_quarters=n, margin_median=float(np.median(m)) if m else None,
                roic_median=float(np.median(roic)) if len(roic) >= R.CYCLE_MIN_QUARTERS else None,
                roic_ex_goodwill_median=float(np.median(roic_x)) if len(roic_x) >= R.CYCLE_MIN_QUARTERS else None,
                roic_n=len(roic), long_enough=n >= R.CYCLE_MIN_QUARTERS)
