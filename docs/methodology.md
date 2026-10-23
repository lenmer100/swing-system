# Methodology

## 1. Principles
- Rules, not fitting: no machine learning, no parameter search, no per-ticker tuning.
- Point-in-time data only; periods: **test 2012–19, validation 2020–21, 2023+ sealed**.
- Reported (SEC) figures first; analyst estimates only where the archetype requires them, uncapped only for the first 1–2 years.
- If a model does not fit, the output is *"not reliable"* with reasons — never a 0–x range.

## 2. Valuation archetypes
| Archetype | Trigger (simplified) | Model |
|---|---|---|
| Quality compounder | stable high margins & returns | FCFF-DCF, margin held at current level when rising |
| Bank / broker | financial SIC codes | ROTCE excess-return model on tangible equity |
| Insurer | insurance SIC | excess return on equity, combined-ratio sanity check |
| REIT | REIT status | NAV / FFO-based |
| Utility | regulated utility | dividend/rate-base DCF with low growth |
| Cyclical | cyclical sector or deep revenue/margin drawdowns | DCF on mid-cycle margin (≤10y median) |
| Hyper-growth | growth ≥ 25 % | DCF, consensus yrs 1–2, sector mature margin |
| Capacity build-out | capex ≥ 40 % of revenue, growth ≥ 20 %, FCF < 0 | **implied return on new capacity** instead of a fair value; funding gap as dilution |
| Turnaround | negative operating margin | DCF to sector margin, ≥ 50 % safety margin |
| Conglomerate | multiple reportable segments | sum-of-the-parts |
| Defence | list/SIC | pessimistic GAAP basis as base case |
| Growth with emerging margin | growth ≥ 8 % | DCF to sector margin |

Cost of capital: CAPM with peer beta (archetype × sector), country risk premium, cost of debt from coupon. Equity bridges include investments in affiliates, leases and dilution. Ranges are bounded (pessimistic ≥ 0.5× base, optimistic ≤ 2× base).

## 3. Swing logic
1. Pivots (swing highs/lows) and 20/50/100/200-day averages define support and resistance **zones**.
2. Entry zone = nearest qualified support; status: in zone / near / waiting.
3. Stop = min(zone, pivot low) − 1 ATR (moved below a deeper zone if one is close); knock-out for leveraged products = stop − 1 ATR.
4. Targets = next resistance zones; net reward/risk includes product financing costs.
5. Warnings for entries > 10 % above the 200-day line and for zones with only two touches.
Measured stop/target probabilities per setup group are shown next to each plan.

## 4. Investment plan
Tranches at fair-value-related buy levels and supports, a volatility-bucket thesis stop (~32–37 % below the base level), and stress scenarios ordered from historical worst case to thesis break.

## 5. Backtest design
- Universe with point-in-time index membership, including delisted names.
- Monthly evaluation dates; every model run on data truncated to that date (filings by filing date).
- Valuation: level check (fair value / price), rank correlation with forward returns, comparison against the previous engine and a simple FCF-yield baseline.
- Swing: limit-order fills, gaps executed at the open, stop wins same-day ties, 126-day time stop, turbo financing 5 % p.a.
- Rules are chosen on test and only confirmed on validation.
