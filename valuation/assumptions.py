"""Fixed, documented assumptions (no tuning; chosen a priori from standard practice).
Sources: Damodaran, 'Investment Valuation' 3rd ed. (2012) ch. 7-8, 12-15; Damodaran online data
(pages.stern.nyu.edu/~adamodar: ERP, ratings/spreads, sales-to-capital, marginal tax rates);
Koller/Goedhart/Wessels 'Valuation' (McKinsey) 7th ed. ch. 10-11 (continuing value, ROIC fade);
Fama/French (2000) 'Forecasting Profitability and Earnings' (profitability mean reversion)."""

ERP = 0.050                 # equity risk premium, fixed long-run (Damodaran implied ERP 2012-2025 ~4.1-6.0%)
TERMINAL_G_CAP = 0.035      # terminal growth = min(risk-free, 3.5%) -> always <= rf
EXPLICIT_YEARS = 10         # stage 1: yrs 1-2 consensus, stage 2: yrs 3-10 linear fade, stage 3: terminal
HIGH_GROWTH_YEARS = 5       # cost of capital constant yrs 1-5, then linear to mature (beta 1) by yr 10
MARGIN_CONVERGE_YEARS = 5   # operating margin moves linearly from TTM to target by year 5
MARGIN_REVERSION = 0.5      # base target = own 3y median + 50% of gap to sector median (Fama/French 2000)
ROIC_FADE = 0.5             # terminal ROIC = WACC_mature + 50% of current excess return (KGW ch.11)
ROIC_EXCESS_CAP = 0.10      # terminal excess ROIC capped at +10pp
S2C_BOUNDS = (0.3, 5.0)     # sales-to-capital clamp; fallback sector median, else 1.5 (Damodaran global median ~1.5-2)
S2C_FALLBACK = 1.5
BETA_BOUNDS = (0.6, 2.0)
BETA_REG_WEIGHT = 0.5       # beta = 0.5 * own Blume-adjusted 5y monthly beta + 0.5 * sector median (bottom-up)
GROWTH_CLIP = (-0.10, 0.60) # sanity clamp on any single-year revenue growth input
BACKTEST_G_CLIP = (-0.05, 0.35)
WEIGHT_DCF = 2/3            # combination: intrinsic FCFF DCF primary, justified forward PE secondary
WEIGHT_PE = 1/3
MIN_PEERS = 6               # sector multiples only reported/used with >= 6 peers

# v5: statutory corporate rate by country (Damodaran 'countrytaxrates', 2024/25 edition; static outside the US:
# no foreign rate change in 2012-19 large enough to matter is modelled, documented limitation)
COUNTRY_TAX = {"Germany": 0.30, "Netherlands": 0.258, "Taiwan": 0.20, "Denmark": 0.22, "Japan": 0.3062,
               "United Kingdom": 0.25, "France": 0.25, "Switzerland": 0.196, "Ireland": 0.125, "Canada": 0.265,
               "South Korea": 0.24, "Israel": 0.23, "China": 0.25, "India": 0.25, "Brazil": 0.34, "Argentina": 0.35,
               "Mexico": 0.30, "Sweden": 0.206, "Norway": 0.22, "Italy": 0.24, "Spain": 0.25, "Australia": 0.30,
               "Singapore": 0.17, "Hong Kong": 0.165, "Luxembourg": 0.249, "Belgium": 0.25, "Finland": 0.20,
               "Uruguay": 0.25, "Bermuda": 0.15, "Cayman Islands": 0.0, "Jersey": 0.0}
TCJA = "2017-12-22"   # US: 35 % + state (38 %) until the TCJA was signed, 21 % + state (25 %) after


def marginal_tax(country: str = "US", year=2026) -> float:
    """Marginal statutory rate in the terminal year: US by date (TCJA signing 22.12.2017), other countries by domicile.
    `year` may be an int year or a date. Tax havens (Cayman/Jersey holding companies) fall back to the US rate:
    profits are taxed where earned, not where the holding sits."""
    import pandas as _pd
    if country in ("BR",):
        return 0.34
    if country and country not in ("US", "United States") and country in COUNTRY_TAX and COUNTRY_TAX[country] >= 0.10:
        return COUNTRY_TAX[country]
    d = _pd.Timestamp(f"{year}-07-01") if isinstance(year, int) else _pd.Timestamp(year)
    return 0.38 if d < _pd.Timestamp(TCJA) else 0.25

COUNTRY = {"MELI": "BR"}    # MercadoLibre: main tax jurisdictions Brazil/Argentina/Mexico -> Brazil 34%

# Defence names: pessimistic GAAP basis is used as base case (LM rule; restored in v5)
DEFENCE_SIC = ("3795", "3761", "3482", "3483", "3489")   # 3812 (navigation/detection) left out: it also holds consumer navigation (GRMN) and instruments (TDY)
DEFENCE = {"LMT", "NOC", "GD", "RTX", "LHX", "HII", "RHM.DE", "HAG.DE", "BA.L", "SAAB-B.ST", "KOG.OL", "LDO.MI", "R3NK.DE", "HO.PA"}

# FCFF DCF does not apply to banks/insurers/REITs (Damodaran ch.21): excluded
FINANCIAL_TYPES = {"Finanzen", "Versicherung", "REIT", "AssetManager", "Versicherungsmakler"}

# Damodaran synthetic rating table (large non-financial firms): (min interest coverage, spread)
RATING_SPREADS = [(8.5, 0.0059), (6.5, 0.0078), (5.5, 0.0098), (4.25, 0.0108), (3.0, 0.0122),
                  (2.5, 0.0156), (2.25, 0.0200), (2.0, 0.0240), (1.75, 0.0351), (1.5, 0.0421),
                  (1.25, 0.0515), (0.8, 0.0820), (0.65, 0.0864), (0.2, 0.1134), (-1e9, 0.1512)]

def default_spread(coverage):
    if coverage is None:
        return 0.0108
    for lo, s in RATING_SPREADS:
        if coverage >= lo:
            return s
    return RATING_SPREADS[-1][1]
