"""Cost of capital: CAPM with regression + bottom-up beta, synthetic-rating cost of debt, market weights."""
from __future__ import annotations
import numpy as np, pandas as pd
from . import assumptions as A


def monthly_returns(px: pd.DataFrame, col="adj_close") -> pd.Series:
    s = px.set_index("date")[col if col in px else "close"].astype(float)
    return s.resample("ME").last().pct_change().dropna()


def regression_beta(stock_m: pd.Series, mkt_m: pd.Series, asof=None, months=60, min_months=24):
    df = pd.concat([stock_m, mkt_m], axis=1, keys=["s", "m"]).dropna()
    if asof is not None:
        df = df[df.index <= pd.Timestamp(asof)]
    df = df.tail(months)
    if len(df) < min_months:
        return None, len(df)
    b = np.cov(df.s, df.m)[0, 1] / np.var(df.m, ddof=1)
    return float(b), len(df)


def blume(b):
    return None if b is None else 0.67 * b + 0.33


def combine_beta(own_adj, sector_median):
    parts = [x for x in (own_adj, sector_median) if x is not None and np.isfinite(x)]
    if not parts:
        b = 1.0
    elif len(parts) == 1:
        b = parts[0]
    else:
        b = A.BETA_REG_WEIGHT * own_adj + (1 - A.BETA_REG_WEIGHT) * sector_median
    return float(np.clip(b, *A.BETA_BOUNDS))


def wacc(rf, beta, mcap, debt, ebit, interest, tax_marginal, erp=None):
    erp = A.ERP if erp is None else erp
    ke = rf + beta * erp
    cov = (ebit / interest) if interest and interest > 0 else (100.0 if ebit and ebit > 0 else None)
    spread = A.default_spread(cov)
    kd_pre = rf + spread
    kd = kd_pre * (1 - tax_marginal)
    d = max(debt or 0.0, 0.0)
    wd = d / (mcap + d) if (mcap + d) > 0 else 0.0
    w = (1 - wd) * ke + wd * kd
    ke_m = rf + 1.0 * erp
    w_m = (1 - wd) * ke_m + wd * kd
    return dict(rf=rf, erp=erp, beta=beta, cost_of_equity=ke, interest_coverage=cov, spread=spread,
                cost_of_debt_pre_tax=kd_pre, cost_of_debt_after_tax=kd, weight_debt=wd, wacc=w,
                wacc_mature=w_m, cost_of_equity_mature=ke_m)
