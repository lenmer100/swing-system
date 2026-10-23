"""v3 rules: fixed thresholds chosen a priori from published practice (see design_ref/VALUATION_V3.md).
No per-ticker exceptions, no parameter search."""
from pathlib import Path
import functools
import pandas as pd

ERP_FILE = Path(__file__).parent / "data" / "damodaran_erp_monthly.csv"

# R2 model by business type (Damodaran ch.21 financial service firms; Simply Wall St model docs)
EXCESS_RETURN_TYPES = {"Bank", "Finanzen", "Versicherung", "Versorger"}   # + regulated utilities: equity/allowed-ROE model (Damodaran, regulated firms)             # regulated capital -> equity excess returns
REIT_TYPES = {"REIT"}                                           # AFFO-based equity DCF
# R6 cyclicals: normal-cycle margin (Damodaran 'normalized earnings', Investment Valuation ch.22)
CYCLICAL_TYPES = {"Halbleiter", "Rohstoffe", "Energie", "Speicher", "Solar", "Hausbau"}
CYCLE_QUARTERS = 40          # up to 10y of TTM observations
CYCLE_MIN_QUARTERS = 20      # at least 5y, else 3y median
# R3 growth stage from consensus revenue growth FY+1 (backtest: trailing 3y CAGR)
STAGE_HYPER, STAGE_HIGH = 0.30, 0.12
DCF_WEIGHT = {"hyper": 1.0, "high": 2 / 3, "mature": 0.5}
REINVESTER_FCF_TO_NI = 0.5   # R3b: FCF/NI < 0.5 (or NI <= 0) -> earnings not cash-representative -> PE weight 0
# R4 moat proxy on long-window ROIC (median of TTM ROIC over up to 10y, >= 5y) vs current WACC (Morningstar moat; KGW ch.11)
MOAT_WIDE_EXCESS, MOAT_NARROW_EXCESS, MOAT_WIDE_MARGIN = 0.10, 0.03, 0.20
REVERSION = {"wide": 0.0, "narrow": 0.5, "none": 1.0}           # share of gap to sector margin closed by yr 5 (Fama/French 2000)
TERMINAL_EXCESS_SHARE = {"wide": 0.5, "narrow": 0.25, "none": 0.0}  # terminal ROIC = WACC + share x excess (cap 10pp)
# R5 uncertainty from analyst EPS dispersion FY+1 -> margin of safety (Morningstar uncertainty ratings)
UNC_LEVELS = [(0.20, "niedrig", 0.20), (0.35, "mittel", 0.30), (0.60, "hoch", 0.40), (9e9, "sehr hoch", 0.50)]
EXPLICIT_YEARS = 10
MOS_NO_ESTIMATES = 0.50
SHARE_CHECK = (0.5, 2.0)    # EDGAR shares vs Yahoo marketCap/close outside -> use marketCap/close (share class/ADR/unit error)
STALE_DAYS = 456            # last period end > 15 months before valuation date -> "Zahlen veraltet" (annual filer missed a cycle)     # no analyst dispersion available -> highest uncertainty class


@functools.lru_cache(None)
def erp_table():
    d = pd.read_csv(ERP_FILE, dtype=str); d["month"] = pd.to_datetime(d.month, format="mixed")
    for c in ("tbond", "erp_sust", "erp_t12m", "erp"):     # source has one row typed as '3,90%' text (Sep 2024)
        d[c] = d[c].map(lambda x: float(x.rstrip("%")) / 100 if isinstance(x, str) and x.endswith("%") else (float(x) if isinstance(x, str) and x else None))
    return d.sort_values("month").reset_index(drop=True)


def erp_asof(asof):
    """Damodaran implied ERP and T-bond rate published for the month containing `asof` (start-of-month value)."""
    d = erp_table(); d = d[d.month <= pd.Timestamp(asof)]
    if not len(d):
        raise ValueError("no ERP before 2008-09")
    r = d.iloc[-1]
    return dict(erp=float(r.erp), rf=float(r.tbond), month=str(r.month.date()), basis=r.erp_basis)


def stage(g):
    return "hyper" if g > STAGE_HYPER else "high" if g > STAGE_HIGH else "mature"


def moat(excess_long, margin_long):
    if excess_long is None:
        return "none"
    if excess_long > MOAT_WIDE_EXCESS and (margin_long or 0) > MOAT_WIDE_MARGIN:
        return "wide"
    return "narrow" if excess_long > MOAT_NARROW_EXCESS else "none"


def uncertainty(disp):
    for lim, name, mos in UNC_LEVELS:
        if disp is not None and disp < lim:
            return name, mos
    return "sehr hoch", 0.50
