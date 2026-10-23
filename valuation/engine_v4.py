"""Valuation v4: archetype-driven. Archetype from point-in-time numbers (archetype.py); model, peer group, growth and
margin rules per archetype; universal guards. Rules: design_ref/VALUATION_V4.md. Builds on the v3 building blocks."""
from __future__ import annotations
from dataclasses import replace
import functools, json, math
import numpy as np, os
DIAG = set(filter(None, os.environ.get("V4_DIAG", "").split(",")))   # level decomposition switches (diagnosis only)
from pathlib import Path
import pandas as pd
from . import assumptions as A, rules_v3 as R, inputs as I, archetype as AR, v5rules as V5, concepts as C
from .history import long_window
from .dcf import DCFInputs, run_dcf, reverse_dcf, sensitivity
from .capital import wacc as wacc_fn, combine_beta
from .forward_pe import forward_block
from .engine_v3 import excess_returns, affo_model, value_financial, _fcf, _cases_mcap, _clip

# --- fixed v4 parameters (documented, not optimised) -------------------------------------------------
PRE_REV_WEIGHTS = {"failure": 0.40, "base": 0.40, "optimistic": 0.20}   # failure = value 0 (limited liability)
TURNAROUND_MOS = 0.50
HYPER_GROWTH_CLIP = (-0.50, 3.00)            # consensus yrs 1-2 not capped beyond data-error bounds
INFRA_CAPEX_REV = 0.15                       # mature capital-intensive peers: capex >= 15 % of revenue, margin > 0, not build-out
COUPON_BOUNDS = (0.0, 0.15)                  # coupon-based cost of debt: rf .. rf + 15 pp
UNRELIABLE = (0.25, 3.0)
SHARE_GUARD = (0.1, 10.0)                    # v5: EDGAR shares x price vs market value outside 0.1-10x = data error, not a share class
TURN_SHARE_CAP = 0.85                        # max default probability applied (D-rated firms still have a going-concern tail)
BUILDOUT_ROIC_BAND = 0.03                    # buildout range: ROIC on new capacity = WACC -/+ 3 pp
BUILDOUT_CONV_Y = 3                          # new capacity reaches mature margin within 3 years (GROWTH fix 1)
ACQ_JUMP = 0.25                              # consensus year-1 jump > max(25 %, 2x 3y CAGR) = bought growth (CYC X4)
PERIM_G = 0.25; PERIM_REV = 0.10             # consensus |g1| > 25 % while EDGAR revenue moved < 10 %: perimeter change (MEGA 7)
MIN_PEERS = 6                                # archetype x sector peer group used when >= 6 members, else archetype                     # fair/price outside -> 'Bewertung nicht belastbar'
CRP_FILE = Path(__file__).parent / "data" / "damodaran_crp_fetched_2026-10-21.csv"
YFI = Path(__import__("os").environ.get("MARKET_STORE", "data_store") + "/derived/yf_info")
CF = Path(__file__).parent / "cache" / "companyfacts"
FIL = Path(__import__("os").environ.get("MARKET_STORE", "data_store") + "/filings_raw")


@functools.lru_cache(None)
def _crp():
    d = pd.read_csv(CRP_FILE)
    return dict(zip(d.country, d.crp))


@functools.lru_cache(None)
def _info(t):
    p = YFI / f"{t}.json"
    return json.loads(p.read_text()) if p.exists() else {}


@functools.lru_cache(None)
def foreign_filer(t):
    """20-F/40-F filer (foreign private issuer): ADR/ordinary-share mismatch possible only here."""
    if any(FIL.glob(f"{t}_20-F_*")) or any(FIL.glob(f"{t}_40-F_*")):
        return True
    p = CF / f"{t}.json.gz"
    if p.exists():
        import gzip
        d = json.load(gzip.open(p))
        for tax in d.get("facts", {}).values():
            for c in list(tax.values())[:30]:
                for u in c["units"].values():
                    if any(x.get("form") in ("20-F", "40-F") for x in u[-20:]):
                        return True
    return False


def country_risk(t, asof=None):
    """Damodaran CRP weighted by revenue geography from the latest annual XBRL instance (live only: filed <= asof and
    <= 15 months old); otherwise domicile (yfinance 'country') as documented fallback."""
    c = _info(t).get("country")
    dom = 0.0 if (not c or c == "United States") else _crp().get(c)
    dom = float(dom) if dom is not None and math.isfinite(dom) else 0.0
    if asof is not None:
        from . import geo_crp as GC, xbrl_instance as X
        d = X.load(t, annual=True)
        if d is not None and len(d) and "filed" in d:
            fd = pd.Timestamp(d.filed.iloc[0])
            if fd <= pd.Timestamp(asof) and (pd.Timestamp(asof) - fd).days <= 456:
                v, why = GC.revenue_crp(t, _crp(), dom)
                if v is not None:
                    return v, c or "United States", "Umsatzregionen (XBRL): " + why
    return dom, c or "United States", "Sitz" + ("" if not dom else " (Umsatzregionen nicht verfügbar)")


def months_left_fy0(t, asof, cons):
    """Time-weighted NTM: months from asof to the end of consensus FY0."""
    m, _ = I.fy_end_month(t)
    fy = cons["years"][0].get("fy")
    if not fy:
        return 6
    end = pd.Timestamp(year=int(fy), month=m, day=1) + pd.offsets.MonthEnd(0)
    return float(_clip((end - pd.Timestamp(asof)).days / 30.44, 0, 12))


TERMINAL_G_EQ_RF = True
G_CAP3 = 0.40            # audit G2: year 3 growth = min(g2, 40 %), then linear fade to g_T
REV_CAP_CAGR = 0.2244    # audit G2: revenue yrs 3-10 <= rev_2 x (1+22.44 %)^8; 22.44 % = top-decile 3y revenue CAGR, pool 2012-19 (v34_panel, n=22,053)
STALE_HYPER_DAYS = 200   # audit G5: growth > 50 % -> base older than 200 days is stale
RANGE_BOUND = (0.5, 2.0)  # v5: methodical range bounds (pess >= 0.5x base, opt <= 2x base)
RANGE_MAX = 3.0          # audit C8: optimistic <= 3x base, pessimistic >= base/3
CAPTIVE_SHARE = 0.20     # audit C2: finance receivables >= 20 % of assets -> captive finance arm valued separately
CAPTIVE_LEVERAGE = 0.90
CAPTIVE_PB = 1.0  # captive arms fund ~90 % of receivables with debt; equity = 10 % at book (P/B 1 = ROE ~ CoE)


AFFO_SHARE = 0.90        # audit C5: AFFO = FFO - maintenance capex proxy (10 % of FFO), documented approximation


def _fin_history(t, asof, fs, ke):
    """ROE history (bank 40q, utility/REIT 20q), book and FFO/share 3y CAGR from EDGAR TTM rows."""
    f = I.fund(t)
    if f is None:
        return {}
    f = f[f.avail_date <= pd.Timestamp(asof)]
    if not len(f) or "equity" not in f:
        return {}
    h = f.tail(40)
    roe = (h.net_income_ttm / h.equity).replace([np.inf, -np.inf], np.nan).dropna()
    roe = roe[(roe > -0.5) & (roe < 0.6)]
    out = {}
    if len(roe) >= 8:
        r5 = roe.tail(20) if (fs.get("typ_hint") != "bank") else roe
        out.update(roe_median=float(roe.median()), roe_p25=float(roe.quantile(.25)), roe_p75=float(roe.quantile(.75)),
                   roe_median_5y=float(r5.median()), persistence=float((roe > ke).mean()), roe_n=int(len(roe)))
    if len(f) >= 13:
        e0, e3 = f.equity.iloc[-1], f.equity.iloc[-13]
        if e0 and e3 and e0 > 0 and e3 > 0:
            out["book_cagr"] = float((e0 / e3) ** (1 / 3) - 1)
        if "ffo_ttm" in f:
            s0 = f.shares_best.iloc[-1] if "shares_best" in f else None; s3 = f.shares_best.iloc[-13] if "shares_best" in f else None
            a0, a3 = f.ffo_ttm.iloc[-1], f.ffo_ttm.iloc[-13]
            if s0 and s3 and a0 and a3 and a0 > 0 and a3 > 0:
                out["ffo_cagr"] = float(((a0 / s0) / (a3 / s3)) ** (1 / 3) - 1)
    return out


def ntm_eps_clean(cons, ml, price, scenario="base"):
    """NTM EPS: time-weighted FY0/FY1; FY0 dropped if FY1 < FY0 while revenue grows (FY0 holds a one-off gain);
    EPS currency checked by plausibility (forward P/E 5-80, else no P/E block). -> (eps or None, note)."""
    y0, y1 = cons["years"][0], cons["years"][1]
    k = {"base": "eps", "pessimistic": "eps_low", "optimistic": "eps_high"}[scenario]
    e0, e1 = y0.get(k) or y0.get("eps"), y1.get(k) or y1.get("eps")
    if not e0 or not e1:
        return None, "EPS-Konsens fehlt"
    note = None
    if e1 < e0 and (y1.get("rev_growth") or 0) > 0:
        e0 = e1; note = "FY0-EPS über FY1 bei steigendem Umsatz -> Einmalgewinn, nur FY1 genutzt"
    ntm = (e0 * ml + e1 * (12 - ml)) / 12
    if ntm <= 0:
        return None, "NTM-EPS ≤ 0"
    pe = price / ntm
    if not 5 <= pe <= 80:
        return None, (note + "; " if note else "") + f"Forward-KGV {pe:.0f}× unplausibel (Währung/Basis) -> kein KGV-Block"
    return ntm, note


ONEOFF_MIN = 0.01        # one-off charges count only if >= 1 % of revenue (immaterial items are noise)
FCF_NOPAT_HI = 1.2       # 3y FCF/NOPAT > 1.2: GAAP EBIT depressed by non-cash charges -> start at own 3y median margin


def _normalised_start(t, asof, fs, x):
    """Start margin = TTM + material one-off charges of the last FY (impairment, restructuring, litigation; EDGAR raw,
    PIT); if 3y FCF/NOPAT > 1.2 the start is at least the own 3y median margin."""
    m = fs["margin_ttm"]; notes = []
    d = I.raw(t); rev = fs.get("revenue_ttm")
    if d is not None and rev:
        a = pd.Timestamp(asof)
        z = d[(d.filed <= a) & d.key.isin(["impairment", "restructuring", "litigation"]) & d.start.notna()]
        z = z[((z.end - z.start).dt.days > 330) & ((a - z.end).dt.days <= 456)]
        if len(z):
            last = z.sort_values("filed").groupby("key").last()
            one = float(last.val.clip(lower=0).sum()) / rev
            if one >= ONEOFF_MIN:
                m += one; notes.append(f"Einmalkosten {one:.1%} vom Umsatz zurückgerechnet ({', '.join(last.index)})")
    f = I.fund(t)
    if f is not None and fs.get("margin_3y_median") is not None:
        f = f[f.avail_date <= pd.Timestamp(asof)].tail(12)
        if len(f) >= 12 and "operating_income_ttm" in f and "op_cash_flow_ttm" in f and "capex_ttm" in f:
            q = f.iloc[[3, 7, 11]]
            nopat = (pd.to_numeric(q.operating_income_ttm, errors="coerce") * 0.75).sum()
            fcf = (pd.to_numeric(q.op_cash_flow_ttm, errors="coerce") - pd.to_numeric(q.capex_ttm, errors="coerce").abs()).sum()
            if nopat > 0 and fcf / nopat > FCF_NOPAT_HI and fs["margin_3y_median"] > m:
                m = fs["margin_3y_median"]; notes.append(f"FCF/NOPAT 3J {fcf / nopat:.2f} > {FCF_NOPAT_HI}: Start = eigener 3J-Median")
    return m, "; ".join(notes) or None


def _fin_kind(arch, typ):
    return "reit" if arch == "reit" else "utility" if arch == "utility" else "insurer" if typ == "Versicherung" else "bank"


def _financial_v4(t, asof, price, sec, typ, cons, r):
    """Banks/insurers/REITs/utilities without FCFF inputs (JPM etc.): v5 equity paths (ROTCE, combined ratio, actual
    payout, regulated ROE ex goodwill); book value and shares as in v3."""
    e = R.erp_asof(asof); rf, erp = e["rf"], e["erp"]; gT = rf if TERMINAL_G_EQ_RF else min(rf, A.TERMINAL_G_CAP)
    fm = r["firm"]; sh = fm["shares_diluted"]
    cap = dict(r["cost_of_capital"]); ke = cap["cost_of_equity"]
    crp, ctry, crp_basis = country_risk(t, asof)
    if typ == "REIT":
        ke = rf + min(cap.get("beta") or 1.0, 1.0) * erp
    ke += crp or 0
    cap.update(cost_of_equity=ke, wacc=ke, crp=crp, crp_country=ctry, crp_basis=crp_basis)
    kind = "reit" if typ == "REIT" else "utility" if typ == "Versorger" else "insurer" if typ == "Versicherung" else "bank"
    rr = I.fund_asof(t, asof)
    gv = lambda k: float(rr[k]) if rr is not None and k in rr.index and pd.notna(rr[k]) else None
    tax = A.marginal_tax(A.COUNTRY.get(t) or _info(t).get("country") or "US", asof)
    q = equity_v5(t, asof, kind, price, dict(equity=fm["equity"], net_income=gv("net_income_ttm"), shares=sh,
                                             revenue=gv("revenue_ttm"), rev_cagr_3y=((gv("revenue_ttm") / gv("revenue_ttm_l12")) ** (1 / 3) - 1)
                                             if gv("revenue_ttm") and gv("revenue_ttm_l12") and gv("revenue_ttm_l12") > 0 and gv("revenue_ttm") > 0 else None), ke, gT, tax, cons, rf)
    if q is None:
        return r
    scen = {s: dict(fair_value=v, intrinsic=v, pe_value=None, model_detail=d, forward_pe=None, margin_target=None) for s, (v, d) in q["scen"].items()}
    vals = [x["fair_value"] for x in scen.values()]; base = scen["base"]["fair_value"]
    cl = r["classification"]; mos = cl["margin_of_safety"] if cl.get("margin_of_safety") is not None else R.MOS_NO_ESTIMATES
    cl["model_notes"] = q["notes"]; cl["model_flags"] = q["flags"]
    r.update(fair_value=base, upside=base / price - 1, range=dict(pessimistic=min(vals), base=base, optimistic=max(vals)),
             terminal_growth=gT, cost_of_capital=cap, scenarios=scen, buy_zone_below=base * (1 - mos), fin_history=q["fin"], raw_pess=min(vals))
    return r


# ================================ v5 equity-side model paths =====================================================
EQ_FIN_SIC = ("6211", "6282", "6324", "6200", "6726", "6199", "6141", "6153")   # brokers, asset managers, managed care, exchanges, consumer lenders without bank charter
EQ_FIN_TYPES = {"AssetManager"}


def equity_route(t, typ, x):
    """CYC F2 / GROWTH 9: financial businesses whose debt/customer money is operating (brokers, exchanges, asset managers,
    managed care, fintech lenders without a bank balance sheet) are valued on equity, never FCFF."""
    if typ in EQ_FIN_TYPES:
        return "fin_equity"
    if (x.get("capex_rev") or 0) >= 0.15:
        # v5.1 (IREN): a finance SIC with capex >= 15 % of revenue (same threshold as the bank rule) runs a physical asset
        # base (data centres, mining) - its debt finances plants, not a loan book -> FCFF, not the equity model
        return None
    v = AR._sic().get(t)
    sic = str(v[0]) if v and v[0] else ""
    if sic.startswith(EQ_FIN_SIC):
        return "fin_equity"
    if typ == "Finanzen" and (x.get("loans_share") or 0) < AR.BANK_LOANS_SHARE:
        return "fin_equity"
    return None


def _reit_v5(affo0, ke, g, gT, payout, roe_affo, n=R.EXPLICIT_YEARS):
    """REIT (CYC R1/R2): dividends = AFFO x actual payout; organic growth up to inflation needs no retention, growth
    above it is funded by retention at the AFFO return on book."""
    from .dcf import growth_path
    gs = growth_path(g, g, gT, n); a, pv = affo0, 0.0
    po = lambda gg: max(0.0, min(payout, 1 - max(0.0, gg - V5.INFLATION) / roe_affo)) if roe_affo > 0 else payout
    for k in range(1, n + 1):
        a *= 1 + gs[k - 1]; pv += a * po(gs[k - 1]) / (1 + ke) ** k
    po_T = max(0.0, 1 - max(0.0, gT - V5.INFLATION) / roe_affo) if roe_affo > 0 else payout   # terminal payout from fundamentals
    tv = a * (1 + gT) * po_T / (ke - gT) / (1 + ke) ** n
    return dict(equity=pv + tv, pv_terminal=tv, payout=payout, roe_affo=roe_affo)


def equity_v5(t, asof, kind, price, fsl, ke, gT, tax, cons, rf):
    """-> dict(scen={s: (value/share, detail)}, notes, flags) for kind in bank/insurer/utility/fin_equity/reit.
    fsl: dict(equity, net_income, shares, revenue, rev_cagr_3y)."""
    bv, ni, sh = fsl.get("equity"), fsl.get("net_income"), fsl.get("shares")
    if not bv or bv <= 0 or not sh:
        return None
    notes, flags = [], []
    fin = _fin_history(t, asof, dict(typ_hint="bank" if kind == "bank" else None), ke)
    scen = {}
    if kind == "reit":
        r = I.fund_asof(t, asof); ffo = r.get("ffo_ttm") if r is not None and "ffo_ttm" in r.index else None
        if ffo is None or pd.isna(ffo) or ffo <= 0:
            return None
        affo = AFFO_SHARE * float(ffo)
        po = V5.payout_ratio(t, asof, affo); po_src = "tatsächliche Dividende/AFFO"
        if po is None:
            po, po_src = 0.85, "Dividende nicht getaggt -> 85 % (REIT-Pflicht ≥ 90 % des steuerl. Gewinns)"
        po = _clip(po, 0.5, 1.0)
        g = _clip(fin.get("ffo_cagr") if fin.get("ffo_cagr") is not None else 0.03, -0.05, 0.10)
        roe_a = max(affo / bv, ke)
        for s, dg in (("pessimistic", -0.02), ("base", 0.0), ("optimistic", 0.02)):
            d = _reit_v5(affo, ke, g + dg, gT, po, roe_a)
            scen[s] = (max(0.0, d["equity"] / sh), dict(d, growth=g + dg))
        notes.append(f"AFFO {affo / 1e9:,.2f} Mrd. (0,9 × FFO), Ausschüttung {po:.0%} ({po_src}), Wachstum FFO/Aktie {g:.1%}")
        return dict(scen=scen, notes=notes, flags=flags, fin=fin, book=bv)
    if kind == "bank":
        s, tbv = V5.tangible_roe_series(t, asof, 24)
        if s is not None and len(s) >= 8 and tbv and tbv > 0:
            roe = dict(base=float(s.median()), pessimistic=float(s.quantile(.25)), optimistic=float(s.quantile(.75)))
            pers = float((s > ke).mean()); book = tbv
            notes.append(f"ROTCE (NI − Vorzugsdiv.)/(EK − Vorzugsaktien − Goodwill − Immat.) Median 6J {roe['base']:.1%}; Basis materielles EK {tbv / 1e9:,.1f} Mrd.")
        elif fin.get("roe_median") is not None:
            roe = dict(base=fin["roe_median"], pessimistic=fin["roe_p25"], optimistic=fin["roe_p75"]); pers = fin["persistence"]; book = bv
            notes.append("ROTCE nicht berechenbar (Goodwill/Vorzugsaktien fehlen) -> ROE auf Gesamt-EK")
        else:
            return None
        if (fsl.get("rev_cagr_3y") or 0) >= 0.25 and roe["base"] < ke and cons and cons["years"][1].get("eps"):
            fwd = cons["years"][1]["eps"] * sh / book                 # CYC F1: loss history before a structural change
            if fwd > roe["base"]:
                notes.append(f"Start-ROTCE = Vorwärts-ROE aus Konsens {fwd:.1%} (Umsatz-CAGR ≥ 25 %, Verlusthistorie)")
                roe = dict(base=fwd, pessimistic=min(fwd, roe["base"] + (fwd - roe["base"]) / 2), optimistic=fwd + 0.02)
                pers = max(pers, 0.5)
        share = V5.persistence_share(pers)
        po = V5.payout_ratio(t, asof, ni) if ni and ni > 0 else None
        g = _clip(roe["base"] * (1 - po), 0.0, 0.10) if po is not None else None
        if g is None:
            g = _clip(fin.get("book_cagr") if fin.get("book_cagr") is not None else 0.04, 0.0, 0.10)
        notes.append(f"Wachstum = ROE × Thesaurierung {g:.1%}" if po is not None else f"Wachstum = Buchwert-CAGR {g:.1%}")
    elif kind == "insurer":
        aoci = C.instant(t, "aoci", asof) or 0.0
        eq = bv - aoci
        norm = V5.insurer_normalised(t, asof, tax)
        s, _ = V5.tangible_roe_series(t, asof, 20, ex_aoci=True)
        if norm and eq > 0:
            r0 = norm["ni_norm"] / eq
            notes.append(f"Nettomarge auf verdiente Prämien, Median {norm['years']}J {norm['net_margin_premiums']:.1%} (≈ 1 − Combined Ratio + Float-Ertrag), normalisierter Gewinn {norm['ni_norm'] / 1e9:,.2f} Mrd.; EK ohne AOCI {eq / 1e9:,.1f} Mrd.")
            if fsl.get("revenue") and norm["premiums"] / fsl["revenue"] < 0.70:
                flags.append("Mischkonzern-Versicherer (Nicht-Versicherungsumsatz ≥ 30 %): Summe der Teile fehlt")
        elif s is not None and len(s) >= 8 and eq > 0:
            r0 = float(s.median()); notes.append(f"ROE ohne AOCI, 5J-Median {r0:.1%} (keine Combined-Ratio-Daten)")
        elif fin.get("roe_median_5y") is not None:
            r0 = fin["roe_median_5y"]; eq = bv; notes.append("ROE auf Gesamt-EK (AOCI/Prämien nicht getaggt)")
        else:
            return None
        roe = dict(base=r0, pessimistic=r0 - 0.02, optimistic=r0 + 0.02); book = eq
        pers = float((s > ke).mean()) if s is not None and len(s) else fin.get("persistence")
        share = min(0.5, V5.persistence_share(pers))           # I3: underwriting cycle -> excess fades faster
        po = V5.payout_ratio(t, asof, ni) if ni and ni > 0 else None
        g = _clip(r0 * (1 - po), 0.0, 0.10) if po is not None else _clip(fin.get("book_cagr") or 0.04, 0.0, 0.10)
    elif kind == "utility":
        f = I.fund(t); f = f[f.avail_date <= pd.Timestamp(asof)].tail(20) if f is not None else None
        from .goodwill import goodwill_asof
        gw = goodwill_asof(t, asof) or 0.0
        if f is None or len(f) < 8:
            return None
        eqx = (f.equity - gw)
        imp = pd.to_numeric(f.get("impairment_ttm"), errors="coerce").fillna(0) if "impairment_ttm" in f else 0
        ok = (eqx > 0) & ~(imp >= 0.01 * f.equity)
        rs = (f.net_income_ttm[ok] / eqx[ok]).replace([np.inf, -np.inf], np.nan).dropna()
        if len(rs) < 6:
            return None
        r0 = float(rs.median()); book = bv - gw
        roe = dict(base=r0, pessimistic=r0 - 0.01, optimistic=r0 + 0.01)
        share = 1.0                                         # U1: allowed ROE is structural, no fade to ke
        g = _clip(fin.get("book_cagr") if fin.get("book_cagr") is not None else 0.04, 0.0, gT)
        notes.append(f"regulierte ROE auf EK ohne Goodwill (5J-Median ohne Impairment-Quartale) {r0:.1%}; Übergewinn bleibt (kein Fade); Rate-Base-Wachstum {g:.1%}")
    else:   # fin_equity
        r0 = fin.get("roe_median_5y") if fin.get("roe_median_5y") is not None else (ni / bv if ni is not None else None)
        if r0 is None:
            return None
        if (fsl.get("rev_cagr_3y") or 0) >= 0.25 and cons and cons["years"][1].get("eps") and r0 < ke:
            fwd = cons["years"][1]["eps"] * sh / bv
            if fwd > r0:
                notes.append(f"Start-ROE = Vorwärts-ROE aus Konsens {fwd:.1%} (Verlusthistorie vor Strukturwechsel)"); r0 = fwd
        roe = dict(base=r0, pessimistic=r0 - 0.02, optimistic=r0 + 0.02); book = bv
        share = V5.persistence_share(fin.get("persistence"))
        po = V5.payout_ratio(t, asof, ni) if ni and ni > 0 else None
        g = _clip(r0 * (1 - po), 0.0, 0.15) if po is not None else _clip(fsl.get("rev_cagr_3y") or 0.05, 0.0, 0.15)
        notes.append(f"Eigenkapitalmodell (Finanzgeschäft: Schulden/Kundengelder operativ), ROE 5J {r0:.1%}")
    for s in ("pessimistic", "base", "optimistic"):
        r_ = _clip(roe[s], -0.2, 0.5)
        d = excess_returns(book, r_, ke, g, g, gT, share)
        scen[s] = (max(0.0, d["equity"] / sh), dict(d, roe_start=r_, excess_share=share, growth=g, book_basis=book))
    return dict(scen=scen, notes=notes, flags=flags, fin=fin, book=book)


def _debt_chain(t, asof, fs):
    """Audit C1/D2: total debt through an XBRL tag fallback chain; captive finance arm carved out."""
    from . import debt as D
    di = D.debt_asof(t, asof) or {}
    td0 = fs.get("total_debt") or 0
    td = max(td0, di.get("total_debt") or 0)
    info = dict(scanner=td0, chain=di.get("total_debt"), source=di.get("source") if td > td0 else "Scanner", interest=di.get("interest"))
    # v4.2: latest XBRL instance (custom/segment-only debt: Ford, GM; KO) - live only (filed <= asof, balance date <= 200 days old)
    from . import xbrl_instance as X
    xi = None
    try:
        dd = X.load(t)
        if dd is not None and len(dd) and pd.Timestamp(dd.filed.iloc[0]) <= pd.Timestamp(asof):
            xi = X.debt(t)
            if xi and (pd.Timestamp(asof) - pd.Timestamp(xi["end"])).days > 200:
                xi = None
    except Exception:
        xi = None
    if xi and xi["total"] > 0 and (td <= 0 or xi["total"] > 1.25 * td):
        info.update(instance=xi)
        if xi["finance"] > 0:
            # captive finance arm: its debt funds receivables, not the industrial business -> excluded; v5 (CYC C5): the
            # arm's own equity (~10 % of its funding, CAPTIVE_LEVERAGE) is added at book (P/B 1)
            td = xi["total"] - xi["finance"]
            fs["captive_equity"] = xi["finance"] * (1 / CAPTIVE_LEVERAGE - 1)
            info.update(captive=True, matched_debt=xi["finance"], captive_equity=fs["captive_equity"], source=xi["source"] + " (Finanzsparte herausgenommen, deren EK zum Buchwert addiert)")
            fs["total_debt"] = td
            _, it = I.tax_and_interest(t, asof); info["interest"] = it; info["zero_debt_interest"] = False
            fs["debt_info"] = info
            return
        td = xi["total"]; info["source"] = xi["source"]
    fr, ta = di.get("fin_receivables"), di.get("total_assets")
    if fr and ta and fr / ta >= CAPTIVE_SHARE and td > 0:
        matched = min(td, CAPTIVE_LEVERAGE * fr)
        fs["captive_equity"] = fr - matched
        info.update(captive=True, fin_receivables=fr, matched_debt=matched, captive_equity=fr - matched)
        td -= matched
    fs["total_debt"] = td
    _, it = I.tax_and_interest(t, asof)
    it = it or di.get("interest")
    info["interest"] = it
    # material interest only (leases/fees of debt-free firms are not debt): > max(50 Mio., 0.5 % of revenue)
    info["zero_debt_interest"] = bool(td <= 0 and not info.get("captive") and it and it > max(50e6, 0.005 * (fs.get("revenue_ttm") or 0)))
    fs["debt_info"] = info


def peer_stats(rows):
    """rows: list of dict(arch, margin, s2c, beta, capex_rev). -> stats by archetype + 'infra' group."""
    df = pd.DataFrame(rows)
    out = {}
    def st(g):
        s2c = g.s2c.dropna().clip(*A.S2C_BOUNDS)
        return dict(n=int(len(g)), margin_median=float(g.margin.median()), margin_p25=float(g.margin.quantile(.25)),
                    margin_p75=float(g.margin.quantile(.75)), s2c_median=float(s2c.median()) if len(s2c) else None,
                    beta_median=float(g.beta.dropna().median()) if g.beta.notna().any() else None)
    for a, g in df.groupby("arch"):
        out[a] = st(g)
    for (a, ty), g in df.groupby(["arch", "typ"]):
        if len(g) >= MIN_PEERS:
            out[f"{a}|{ty}"] = st(g)
    inf = df[(df.capex_rev >= INFRA_CAPEX_REV) & (df.margin > 0) & (df.arch != "buildout")]
    if len(inf) >= 6:
        out["infra"] = st(inf)
    prof = df[(df.margin > 0)]
    out["_profitable_by_typ"] = {k: st(g) for k, g in prof.groupby("typ")} if "typ" in prof else {}
    if "fwd_pe" in df:
        q = df[df.fwd_pe.between(5, 80)]
        out["_pe_by_typ"] = {k: dict(n=int(len(g)), median=float(g.fwd_pe.median())) for k, g in q.groupby("typ")}
    if "growth" in df:
        mat = df[(df.margin > 0) & (df.growth < 0.15)]
        out["_mature_by_typ"] = {k: st(g) for k, g in mat.groupby("typ") if len(g) >= MIN_PEERS}
    return out


def arch_of(t, asof, price, typ, cons=None, growth=None, chain=None):
    """-> (final class, rule, features); features['raw_class'] = unfiltered class (for the caller's chain state)."""
    fs = I.firm_stats(t, asof)
    if fs is None:
        return None, None, None
    fs["fcf_ttm"] = _fcf(t, asof) or None
    x = AR.features(t, asof, fs, price, cons, typ)
    if cons is None and growth is not None and not x["structural_break"]:
        x["growth"] = growth
    prev, rawp = chain if chain is not None else _chain(t, asof, price, typ, fs)
    a, why = AR.classify(typ, x, prev, rawp)
    x["raw_class"] = AR.raw_class(typ, x)
    return a, why, x


def _chain(t, asof, price, typ, fs_now, quarters=4):
    """Live hysteresis state: unfiltered classes of the last 4 quarters (trailing numbers, same price), filtered
    through the same chain -> (final class last quarter, unfiltered class last quarter)."""
    raws, xs = [], []
    try:
        seen = {fs_now.get("last_quarter_end")}
        for k in range(quarters, 0, -1):
            a0 = pd.Timestamp(asof) - pd.Timedelta(days=91 * k)
            fs0 = I.firm_stats(t, a0)
            if fs0 is None or fs0.get("last_quarter_end") in seen:
                continue
            seen.add(fs0.get("last_quarter_end"))
            fs0["fcf_ttm"] = _fcf(t, a0) or None
            x0 = AR.features(t, a0, fs0, price, None, typ)
            if fs0.get("rev_cagr_3y") is not None:
                x0["growth"] = fs0["rev_cagr_3y"]
            xs.append(x0); raws.append(AR.raw_class(typ, x0))
    except Exception:
        pass
    if not raws:
        return None, None
    fin = raws[0]
    for q in range(1, len(raws)):
        fin = AR.classify(typ, xs[q], fin, raws[q - 1])[0]
    return fin, raws[-1]


def value_v4(t, asof, price, peers, sectors, typ=None, cons=None, growth=None, detail=True, chain=None):
    typ = typ or I.type_map().get(t)
    sec = sectors.get(typ, {})
    fs = I.firm_stats(t, asof)
    if fs is not None and not fs.get("shares_diluted") and price:
        mc0 = _info(t).get("marketCap") or (_cases_mcap().get(t) or 0) * 1e9
        if mc0:
            # v4.2: EDGAR has no share count (multi-class filers report class-A equivalents, BRK) -> market value / price,
            # marked; the valuation stays usable but the share basis is shown
            fs["shares_diluted"] = mc0 / price
            fs["shares_note"] = f"Aktienzahl aus Börsenwert/Kurs ({mc0 / price / 1e6:,.0f} Mio.; EDGAR ohne Aktienzahl)"
    if (fs is None or not fs.get("shares_diluted")) and typ in (AR.BANK_TYPES | {"REIT", "Versorger"}) and (
            typ != "Finanzen" or (AR._loans_share(t, asof) or 0) >= AR.BANK_LOANS_SHARE):   # audit F1: bank model only with a bank balance sheet
        r = value_financial(t, asof, price, sec, typ, cons, growth)
        if r.get("status") == "ok":
            r = _financial_v4(t, asof, price, sec, typ, cons, r)
        if r.get("status") == "ok":
            a = "bank" if typ in AR.BANK_TYPES else "reit" if typ == "REIT" else "utility"
            r["archetype"] = dict(key=a, name=AR.ARCH[a][0], rationale=AR.ARCH[a][1], rule="Bilanztyp", features={})
            _guards(r, price)
        return r
    if fs is None or not fs.get("shares_diluted"):
        f_ = I.fund(t)
        st = ("keine EDGAR-Daten" if f_ is None else "Datenlücke: EDGAR ohne Aktienzahl" if fs is not None
              else f"Datenlücke: EDGAR-Historie {len(f_)} TTM-Zeilen (< 4 Quartale)" if len(f_) < 4 else "Datenlücke: EDGAR-Kennzahlen unvollständig")
        return dict(ticker=t, status=st)
    fs["fcf_ttm"] = _fcf(t, asof)
    if fs["fcf_ttm"] == 0:
        fs["fcf_ttm"] = None                                  # mega audit 2: exact 0 = missing tag, not a value
    fs["shares_note"] = fs.get("shares_note")
    # ADR / share-class rule only for 20-F/40-F filers (US filers' EDGAR share count is authoritative)
    mc = (_info(t).get("marketCap") or (_cases_mcap().get(t) or 0) * 1e9 or None) if price else None
    share_ratio = (mc / price) / fs["shares_diluted"] if mc else None
    if share_ratio and not SHARE_GUARD[0] <= share_ratio <= SHARE_GUARD[1] and not foreign_filer(t):
        # v5 bug fix (GROWTH Q7/fix 10, ERIE): EDGAR share count off by > 10x vs market value/price -> data gap, no value
        return dict(ticker=t, status=f"Datenlücke: Aktienzahl (EDGAR {fs['shares_diluted']:,.0f} vs. Börsenwert/Kurs {mc / price:,.0f})")
    if share_ratio and not R.SHARE_CHECK[0] <= share_ratio <= R.SHARE_CHECK[1] and not foreign_filer(t):
        fs["share_class_note"] = f"Börsenwert/Kurs = {share_ratio:.2f}× EDGAR-Aktienzahl (US-Emittent: EDGAR maßgeblich; Mehrklassen-/Up-C-Struktur oder Split prüfen)"
    if foreign_filer(t) and price:
        if mc and not R.SHARE_CHECK[0] <= share_ratio <= R.SHARE_CHECK[1]:
            fs["shares_note"] = f"Aktienzahl korrigiert (20-F/40-F, ADR-Verhältnis): EDGAR {fs['shares_diluted'] / 1e6:,.1f} Mio. -> Börsenwert/Kurs {mc / price / 1e6:,.1f} Mio."
            fs["shares_diluted"] = mc / price
    _debt_chain(t, asof, fs)
    x = AR.features(t, asof, fs, price, cons, typ)
    if cons is None and growth is not None and not x["structural_break"]:
        x["growth"] = growth
    prev, rawp = chain if chain is not None else _chain(t, asof, price, typ, fs)
    arch, why = AR.classify(typ, x, prev, rawp)
    raw_arch = AR.raw_class(typ, x)
    seg = None
    if arch not in AR.HARD and arch not in ("cyclical", "turnaround"):
        try:
            from . import sotp as SO
            seg = SO.segments(t, asof)
        except Exception:
            seg = None
        if seg and seg["conglomerate"] and all(s_["ebit"] > 0 for s_ in seg["segments"] if not s_["other"] and (s_.get("share") or 0) >= 0.15):
            arch, why = "conglomerate", f"{len([s_ for s_ in seg['segments'] if not s_['other']])} Segmente, Margenabstand {seg['margin_spread']:.0%} (XBRL-Segmente {seg['fy_end']})"
    pe = dict(peers.get(f"{arch}|{typ}") or peers.get(arch) or {})
    pe_kind = "Archetyp × Sektor" if peers.get(f"{arch}|{typ}") else "Archetyp"
    pbt = (peers.get("_profitable_by_typ") or {}).get(typ)
    if arch in ("mega", "conglomerate", "defence") and pbt and pbt.get("n", 0) >= MIN_PEERS:
        pe = dict(pbt, beta_median=pe.get("beta_median") or pbt.get("beta_median")); pe_kind = f"Geschäftsmodell (profitable {typ})"   # v5 MEGA 9
    eq_route = equity_route(t, typ, x) if arch not in ("bank", "reit", "utility") else None
    if x["structural_break"]:                      # truncate history: pre-break medians are another company
        fs["margin_3y_median"] = fs["margin_ttm"]; fs["rev_cagr_3y"] = None
        fs["sales_to_capital_cycle"] = None; fs["sales_to_capital_raw"] = None
    e = R.erp_asof(asof); rf, erp = e["rf"], e["erp"]
    gT = rf if TERMINAL_G_EQ_RF else min(rf, A.TERMINAL_G_CAP)   # mega audit 1: Damodaran's implied ERP is solved with g = rf
    tax_m = A.marginal_tax(A.COUNTRY.get(t) or _info(t).get("country") or "US", asof)   # v5: by domicile and TCJA date
    eff, interest = I.tax_and_interest(t, asof)
    tax_eff = _clip(eff if eff is not None else tax_m, 0.05, tax_m)
    data_notes = []
    if interest and fs["total_debt"] and fs["total_debt"] > 0 and interest / fs["total_debt"] > 0.15:
        # v5 MEGA 10: interest > 15 % of debt is a tag error (GE: 12.5 bn) -> no coverage-based spread from it
        data_notes.append(f"Zinsaufwand {interest / 1e9:,.1f} Mrd. > 15 % der Schulden: Tag-Fehler, Spread aus Standardrating"); interest = None
    own_b, _ = I.own_beta(t, asof)
    beta = combine_beta(own_b, pe.get("beta_median") or sec.get("beta_median"))    # peer = archetype
    if "beta1" in DIAG:
        beta = 1.0
    mcap = price * fs["shares_diluted"]
    crp, ctry, crp_basis = country_risk(t, asof)
    cap = wacc_fn(rf, beta, mcap, fs["total_debt"], fs["ebit_ttm"], interest, tax_m, erp=erp)
    if crp:
        ke = cap["cost_of_equity"] + crp; wd = cap["weight_debt"]
        cap.update(cost_of_equity=ke, wacc=(1 - wd) * ke + wd * cap["cost_of_debt_after_tax"],
                   cost_of_equity_mature=cap["cost_of_equity_mature"] + crp,
                   wacc_mature=(1 - wd) * (cap["cost_of_equity_mature"] + crp) + wd * cap["cost_of_debt_after_tax"])
    if (fs["ebit_ttm"] or 0) <= 0 and interest and fs["total_debt"] and fs["total_debt"] > 0:
        cpn = interest / fs["total_debt"]                                         # coupon: cover <= 0 makes the table meaningless
        kd_pre = rf + _clip(cpn - rf, *COUPON_BOUNDS) if cpn > rf else max(cpn, rf)
        wd = cap["weight_debt"]; kd = kd_pre * (1 - tax_m)
        cap.update(cost_of_debt_pre_tax=kd_pre, cost_of_debt_after_tax=kd, spread=kd_pre - rf, kd_basis="Kupon (Zinsaufwand/Schulden)",
                   wacc=(1 - wd) * cap["cost_of_equity"] + wd * kd, wacc_mature=(1 - wd) * cap["cost_of_equity_mature"] + wd * kd)
    # mega audit 9: terminal beta halfway between the firm's beta and its industry beta (not 1.0 for everyone)
    b_ind = sec.get("beta_median") or pe.get("beta_median") or 1.0
    b_T = 0.5 * beta + 0.5 * 1.0           # v5 (MEGA 5): mature beta drifts toward 1 (Damodaran), never away from it
    if "tb1" not in DIAG:
        wd = cap["weight_debt"]; ke_m = rf + b_T * erp + (crp or 0)
        cap.update(beta_terminal=b_T, cost_of_equity_mature=ke_m, wacc_mature=(1 - wd) * ke_m + wd * cap["cost_of_debt_after_tax"])
    cap.update(erp_month=e["month"], erp_basis=e["basis"], beta_regression_blume=own_b, beta_peer_median=pe.get("beta_median"),
               crp=crp, crp_country=ctry, crp_basis=crp_basis)
    lw = None if x["structural_break"] else long_window(t, asof, tax_m)

    # consensus: incomplete -> none; base-level mismatch -> keep growth RATES on the EDGAR base (no levels)
    if cons and any(y.get(k) is None for y in cons["years"][:2] for k in ("rev", "rev_growth", "rev_low", "rev_high")):
        cons = None
    cons_note = None
    rep_cur = fs.get("currency_reported") or "USD"
    level_ok = True
    if cons:
        y0 = cons["years"][0]; base_rev = y0["rev"] / (1 + y0["rev_growth"])
        if rep_cur != "USD":
            from .edgar_supp import _fx
            fxs = _fx(rep_cur, [pd.Timestamp(asof)]); base_rev = base_rev * float(fxs.iloc[0]) if fxs is not None else base_rev
        if not 0.67 <= base_rev / fs["revenue_ttm"] <= 1.5:
            level_ok = False
            cons_note = f"Konsensbasis {base_rev / fs['revenue_ttm']:.2f}x EDGAR -> nur Wachstumsraten genutzt"
    cons_pe = cons; v51_notes = []
    if cons and rep_cur != "USD":
        # v5.1 (c): consensus in the reporting currency (revenue level fits EDGAR only after FX) -> EPS to USD at the same
        # FX, kept only if the FX forward P/E is plausible (5-80); EPS already per USD-ADR (TSM) stays as is
        from .edgar_supp import _fx
        fxs = _fx(rep_cur, [pd.Timestamp(asof)]); fx = float(fxs.iloc[0]) if fxs is not None else None
        y0 = cons["years"][0]; braw = y0["rev"] / (1 + y0["rev_growth"]) / fs["revenue_ttm"]
        if fx and abs(math.log(braw * fx)) < abs(math.log(braw)):
            import copy
            c2 = copy.deepcopy(cons)
            for y_ in c2["years"]:
                for k_ in ("eps", "eps_low", "eps_high"):
                    if y_.get(k_) is not None: y_[k_] = y_[k_] * fx
            e1 = c2["years"][1].get("eps")
            if e1 and 5 <= price / e1 <= 80:
                cons_pe = c2; v51_notes.append(f"Konsens in {rep_cur}: Gewinn je Aktie zum Kurs {fx:.4f} in USD umgerechnet (KGV-Block)")
    gclip = HYPER_GROWTH_CLIP if arch in ("hyper", "buildout", "pre_revenue") else A.GROWTH_CLIP
    if cons and level_ok and rep_cur == "USD":
        # levels anchor years 1-2: year 1 = FY+1 consensus revenue (TTM already contains part of FY0 growth)
        # year 1 = the 12 months after the last reported quarter, time-weighted FY0/FY1 (audit G4)
        y = cons["years"]; r0 = fs["revenue_ttm"]; ml = months_left_fy0(t, fs["last_quarter_end"], cons)
        ntm = lambda k: (y[0][k] * ml + y[1][k] * (12 - ml)) / 12
        G = {"base": (ntm("rev") / r0 - 1, y[1]["rev_growth"]),
             "pessimistic": (ntm("rev_low") / r0 - 1, y[1]["rev_low"] / y[0]["rev_low"] - 1),
             "optimistic": (ntm("rev_high") / r0 - 1, y[1]["rev_high"] / y[0]["rev_high"] - 1)}
    elif cons:
        y = cons["years"]; rev_last = y[0]["rev"] / (1 + y[0]["rev_growth"])
        ml = months_left_fy0(t, fs["last_quarter_end"], cons)          # rates on the EDGAR base, same NTM weighting
        g0 = (1 + y[0]["rev_growth"]) ** ((ml) / 12) * (1 + y[1]["rev_growth"]) ** ((12 - ml) / 12) - 1 if ml < 12 else y[0]["rev_growth"]
        G = {"base": (g0, y[1]["rev_growth"]),
             "pessimistic": (y[0]["rev_low"] / rev_last - 1, y[1]["rev_low"] / y[0]["rev_low"] - 1),
             "optimistic": (y[0]["rev_high"] / rev_last - 1, y[1]["rev_high"] / y[0]["rev_high"] - 1)}
    else:
        g = growth if growth is not None else (fs["rev_cagr_3y"] if fs["rev_cagr_3y"] is not None else 0.03)
        g = _clip(g, *A.BACKTEST_G_CLIP)
        G = {"base": (g, g), "pessimistic": (g - 0.05, g - 0.05), "optimistic": (g + 0.05, g + 0.05)}
    # mega audit 7: scenario order. pess/opt year 2 = base year 2 -/+ the year-1 gap (no low1/low0 rebound artefact)
    b1, b2 = G["base"]
    for k in ("pessimistic", "optimistic"):
        k1 = G[k][0]
        G[k] = (k1, b2 + (k1 - b1))
    G["pessimistic"] = tuple(min(a, b) for a, b in zip(G["pessimistic"], G["base"]))
    G["optimistic"] = tuple(max(a, b) for a, b in zip(G["optimistic"], G["base"]))
    capx = V5.capital_ex_goodwill(t, asof, fs) if arch not in ("bank", "reit", "utility") else {}
    growth_note = None; perimeter = False
    if cons and arch not in ("hyper", "buildout", "pre_revenue"):
        r4 = (I.fund(t) if I.fund(t) is not None else pd.DataFrame())
        r4 = r4[r4.avail_date <= pd.Timestamp(asof)] if len(r4) else r4
        yoy = (fs["revenue_ttm"] / float(r4.revenue_ttm.iloc[-5]) - 1) if len(r4) >= 5 and r4.revenue_ttm.iloc[-5] else None
        g1b = G["base"][0]; c3 = fs.get("rev_cagr_3y")
        if abs(g1b) > PERIM_G and yoy is not None and abs(yoy) < PERIM_REV and not capx.get("deal_closed_1y") and g1b < 0:
            # MEGA 7: consensus on a new perimeter (spin-off announced/closed) applied to the old TTM base -> no levels
            perimeter = True; growth_note = f"Konsens Jahr 1 {g1b:+.0%} bei EDGAR-Umsatz {yoy:+.0%}: Perimeterwechsel – Konsens verworfen"
        elif g1b > max(ACQ_JUMP, 2 * (c3 or 0)) and not capx.get("deal_closed_1y"):
            # CYC X4: bought growth in consensus; an acquisition at a fair price is value-neutral -> organic growth only
            go = _clip(c3 if c3 is not None else 0.03, -0.05, ACQ_JUMP)
            growth_note = f"Konsens Jahr 1 {g1b:+.0%} > max(25 %, 2× 3J-CAGR) ohne Goodwill-Sprung: Zukauf zum Kaufpreis wertneutral, organisch {go:+.0%}"
            perimeter = False
            G = {k: (go + (v[0] - g1b), go + (v[1] - G['base'][1])) for k, v in G.items()}
        if perimeter:
            go = _clip(c3 if c3 is not None else 0.0, -0.05, 0.10)
            G = {"base": (go, go), "pessimistic": (go - 0.03, go - 0.03), "optimistic": (go + 0.03, go + 0.03)}
    g_stage = G["base"][1]
    from .engine_v3 import classify as v3c
    cl = v3c(t, typ, fs, lw, cap, g_stage, cons)
    if cl.get("fcf_to_ni") is None and cl.get("reinvester"):
        # v5.1: missing FCF (often 20-F filers) = not measurable, not 'reinvester' (same logic as 'moat not measurable')
        cl["reinvester"] = False; v51_notes.append("Free Cashflow fehlt: Reinvestierer nicht messbar -> KGV-Block erlaubt")
    cyc = arch == "cyclical"
    cl["cyclical"] = cyc

    # --- margins by archetype --------------------------------------------------------------------------
    cyc_long = cyc and lw and lw["long_enough"] and x.get("margin_quarters", 0) >= AR.CYC_MIN_Q
    own = lw["margin_median"] if cyc_long else fs["margin_3y_median"]
    if arch == "buildout":
        ref = peers.get("infra") or pe; ref_kind = "reife kapitalintensive Vergleichsfirmen (Investitionen ≥ 15 % vom Umsatz, profitabel)"
    elif arch in ("pre_revenue", "turnaround", "hyper", "scaler"):
        ref = ((peers.get("_mature_by_typ") or {}).get(typ) or (peers.get("_profitable_by_typ") or {}).get(typ) or sec)
        ref_kind = f"reife profitable Firmen desselben Sektors ({typ}, Wachstum < 15 %)"
    else:
        ref = pe; ref_kind = f"Vergleichsgruppe {pe_kind} ({AR.ARCH[arch][0]}{', ' + typ if pe_kind == 'Archetyp × Sektor' else ''})"
    smed = ref.get("margin_median"); smed = own if smed is None or not math.isfinite(smed) else smed
    p25 = ref.get("margin_p25", smed); p75 = ref.get("margin_p75", smed)
    moat_measured = cl.get("moat") != "none" or bool(lw and lw.get("long_enough"))
    # growth archetypes converge fully to the mature state (GROWTH 7); others by moat; 'not measurable' = half
    rev_share = 1.0 if arch in ("buildout", "pre_revenue", "turnaround", "hyper", "scaler") else (R.REVERSION[cl["moat"]] if moat_measured else 0.5)
    fq = I.fund(t); fq = fq[fq.avail_date <= pd.Timestamp(asof)].tail(4) if fq is not None else None
    proven = None
    if fq is not None and len(fq) == 4 and "operating_income_ttm" in fq and (fq.operating_income_ttm > 0).all() and arch not in ("cyclical", "buildout", "pre_revenue"):
        proven = float(fs["margin_ttm"])
    stable = V5.stable_margin(x) if arch not in ("cyclical", "buildout", "pre_revenue", "turnaround") and not x["structural_break"] else None
    gm = None
    if fq is not None and len(fq) and "gross_profit_ttm" in fq and pd.notna(fq.gross_profit_ttm.iloc[-1]):
        gm = float(fq.gross_profit_ttm.iloc[-1]) / fs["revenue_ttm"]
    low_margin_model = arch == "scaler" and ((x.get("margin_trend") is not None and x["margin_trend"] <= 0) or (gm is not None and gm < 0.15))
    ebita = V5.ebita_cycle(t, asof) if cyc_long else None
    if cyc_long and ebita and ebita["amort_now"] >= 0.01:
        # CYC C3: material acquisition amortisation (>= 1 % of revenue): cycle centre on EBITA; the explicit years carry
        # today's amortisation as a cost that runs off (start margin stays GAAP), terminal on EBITA
        own = ebita["median"]; x = dict(x, margin_p25=ebita["p25"], margin_p75=ebita["p75"])
    if cyc_long:
        rev_share = 0.0; base_t = own
        targets = {"base": own, "pessimistic": min(own, x.get("margin_p25") if x.get("margin_p25") is not None else own),
                   "optimistic": max(own, x.get("margin_p75") if x.get("margin_p75") is not None else own)}
        ref_kind = "eigene Zyklusmitte (≥ 20 Quartale; Szenarien Zyklus-p25/p75)" + (" auf EBITA (Akquisitions-Abschreibung ≥ 1 % Umsatz)" if ebita and ebita["amort_now"] >= 0.01 else "")
    elif arch == "defence":
        own3 = fs["margin_3y_median"]; rev_share = 0.0; base_t = own3
        targets = {"base": own3, "pessimistic": min(own3, fs["margin_ttm"]), "optimistic": max(own3, fs["margin_ttm"])}
        ref_kind = "eigene 3J-Marge (Rüstung: Cost-plus/Festpreis stabil)"
    elif stable is not None:
        # MEGA 3: a margin stable over >= 20 quarters is the moat itself -> no peer reversion
        # v5 fix (KO/SAP): keep proven margins -> base = max(long-run median, own 3y median); pessimistic = long-run median
        # (or p25 when the 3y level is not above it), optimistic = max(base, TTM)
        m3 = fs.get("margin_3y_median"); rev_share = 0.0
        base_t = max(stable, m3) if m3 is not None and m3 > 0 else stable
        if proven is not None and proven > base_t:
            base_t = base_t + 0.5 * (proven - base_t)   # proven TTM above history (SAP cloud step-up): half kept, same 0.5 as 'not measurable'
        targets = {"base": base_t, "pessimistic": stable if base_t > stable else min(stable, x.get("margin_p25") or stable),
                   "optimistic": max(base_t, fs["margin_ttm"])}
        ref_kind = f"eigene stabile Marge (max. Langfrist-Median {x.get('margin_quarters')} Q / 3J-Median; p10 ≥ 0,7 × Median)"
    elif low_margin_model:
        # GROWTH 8: low margin is the business model (wholesale, managed care) or no expansion shown -> own margin
        rev_share = 0.0; base_t = own
        targets = {"base": own, "pessimistic": min(own, fs["margin_ttm"]), "optimistic": max(own, fs["margin_ttm"])}
        ref_kind = "eigene Marge (Niedrigmargen-Modell: " + ("Bruttomarge < 15 %" if gm is not None and gm < 0.15 else "keine Margenausweitung") + ")"
    elif proven is not None and proven > smed:
        # keep proven margins (MEGA/GROWTH): base = proven; pessimistic toward the peer p75
        # fade toward the peer p75 by moat ('not measurable' = half); stable long-run margins were handled above
        floor = max(p75, smed); r_ = R.REVERSION[cl["moat"]] if moat_measured else 0.5
        base_t = max(floor, proven - r_ * (proven - floor)) if proven > floor else proven
        # v5 fix (NVDA): pessimistic goes half-way from base to the peer floor, not all the way (one fixed rule, any moat)
        targets = {"base": base_t, "pessimistic": base_t - 0.5 * (base_t - floor) if base_t > floor else base_t, "optimistic": max(base_t, proven)}
    else:
        base_t = own + rev_share * (smed - own)
        targets = {"base": base_t,
                   "pessimistic": (min(base_t, p25) if arch in ("buildout", "pre_revenue")
                                   else min(base_t, own, p25) if cl["moat"] == "none" else min(base_t, own)),
                   "optimistic": max(base_t, p75, fs["margin_ttm"] if not cyc else own)}
    if arch == "hyper" and x["margin_long"] is not None and x["cycle"]:
        targets["pessimistic"] = min(targets["pessimistic"], x["margin_long"])
    m0, norm_note = _normalised_start(t, asof, fs, x)
    m0_raw = fs["margin_ttm"]
    if stable is not None and not cyc_long and arch != "defence" and m0 > m0_raw and fs.get("margin_3y_max"):
        # v5 fix (KO/SAP): start and target on the same basis - if one-offs are stripped from the start margin, the GAAP
        # history (which contains them) may not pull the target below the cleaned level, capped at the own 3y maximum
        clean = min(m0, fs["margin_3y_max"])
        if clean > targets["base"]:
            targets = {"base": clean, "pessimistic": targets["base"], "optimistic": max(clean, targets["optimistic"])}; base_t = clean
            ref_kind += "; Ziel auf bereinigter Basis (wie Startmarge)"
    if arch not in ("cyclical", "buildout", "pre_revenue", "turnaround", "defence") and not cyc_long and proven is not None:
        # v5.1 (b): if the own sources expect a wider margin, the base target may not fall below today's margin.
        # consensus: EPS FY1 growth above revenue growth after the buyback effect; without consensus: rising own trend
        wid = False
        if cons and cons["years"][1].get("eps") and cons["years"][0].get("eps") and cons["years"][0]["eps"] > 0:
            eg = cons["years"][1]["eps"] / cons["years"][0]["eps"] - 1; rg_ = cons["years"][1].get("rev_growth") or 0
            wid = eg > rg_ - (x.get("dilution_3y") or 0)
        elif not cons:
            wid = (x.get("margin_trend") or 0) > 0
        today = min(m0, proven)
        if wid and today > targets["base"]:
            targets = {"base": today, "pessimistic": targets["pessimistic"], "optimistic": max(today, targets["optimistic"])}; base_t = today
            v51_notes.append(f"Margenausweitung erwartet ({'Konsens EPS > Umsatz' if cons else 'eigener Trend'}): Zielmarge nicht unter heutiger {today:.1%}")
    if arch == "defence":
        m0, norm_note = m0_raw, "Rüstung: GAAP-Start ohne Einmaleffekt-Bereinigung (pessimistische GAAP-Basis)"
    rev0 = fs["revenue_ttm"]; trend_note = None; cyc_trend = None
    if cyc_long:
        # CYC C2: normalised revenue (10y log trend) x cycle-centre margin; consensus peak/trough not extrapolated
        tr, sl = V5.revenue_trend(t, asof)
        if tr:
            sl = _clip(sl, -0.03, 0.10); cyc_trend = (tr, sl)
            trend_note = (f"Trendumsatz {tr / 1e9:,.1f} Mrd. (TTM {fs['revenue_ttm'] / 1e9:,.1f}), Trendwachstum {sl:.1%}: Jahre 1–2 Konsens/Trailing, "
                          f"bis Jahr 5 zurück auf den Trend; Marge von TTM zur Zyklusmitte")
    s2c_c, s2c_r = fs.get("sales_to_capital_cycle"), fs.get("sales_to_capital_raw")
    s2c_note = None
    if capx.get("s2c_organic") and not capx.get("acquisitive"):
        s2c_r = capx["s2c_organic"]; s2c_note = "S2C organisch (ΔIC ohne Goodwill)"
    elif capx.get("acquisitive"):
        s2c_note = "Zukäufe > 25 % von ΔIC: Akquisitionen zum Kaufpreis als Reinvestition (S2C inkl. Goodwill)"
    if arch == "buildout":
        s2c_base = (ref.get("s2c_median") or A.S2C_FALLBACK); cands = [s2c_base]
    elif arch == "turnaround":
        s2c_base = ref.get("s2c_median") or pe.get("s2c_median") or A.S2C_FALLBACK; cands = [s2c_base]
        s2c_note = "Turnaround: S2C reifer Sektor-Peers (nicht eigene Krisenhistorie)"
    else:
        cands = [v for v in (s2c_c, s2c_r, pe.get("s2c_median") or sec.get("s2c_median")) if v] or [A.S2C_FALLBACK]
        s2c_base = float(pd.Series(cands).median())
    ic = fs["invested_capital"] or 0
    # MEGA 1: one ROIC definition (ex goodwill where goodwill data exists) for moat AND terminal value
    roic_kind = "ROIC ohne Goodwill (Langfrist-Median)"
    roic_now = (lw or {}).get("roic_ex_goodwill_median")
    if roic_now is None and capx.get("roic_ex_ttm") is not None:
        roic_now, roic_kind = capx["roic_ex_ttm"], "ROIC ohne Goodwill (TTM)"
    if roic_now is None and (lw or {}).get("roic_median") is not None:
        roic_now, roic_kind = lw["roic_median"], "ROIC inkl. Goodwill (Goodwill fehlt)"
    if roic_now is None and ic > 0:
        roic_now, roic_kind = fs["ebit_ttm"] * (1 - tax_eff) / ic, "ROIC TTM"
    if roic_now is None:
        pr_ = V5.ppe_roic(t, asof, fs)
        roic_now, roic_kind = (pr_, "NOPAT / Sachanlagen (IC ≤ 0)") if pr_ is not None else (cap["wacc"], "kein ROIC messbar -> WACC")
    if arch == "cyclical" and typ == "Versorger" and capx.get("ic_ex") and capx["ic_ex"] > 0:
        # CYC U3 (IPP): price-driven growth needs no new plants -> S2C not below today's capital intensity
        s2c_base = max(s2c_base, fs["revenue_ttm"] / capx["ic_ex"]); s2c_note = "IPP: S2C ≥ Umsatz/investiertes Kapital"
    consist_note = None
    # consistency guard (MEGA 1); not for cyclicals (through-cycle S2C already own median, ROIC mixes cycle phases);
    # adjustment bounded to a factor 2 of the robust S2C so a single noisy ROIC cannot dominate
    if arch not in ("buildout", "pre_revenue", "turnaround", "cyclical") and roic_kind.startswith("ROIC") and roic_now and roic_now > 0 and targets["base"] > 0:
        impl = targets["base"] * (1 - tax_m) * s2c_base
        if not (1 - V5.ROIC_CONSIST) * roic_now <= impl <= (1 + V5.ROIC_CONSIST) * roic_now:
            new = _clip(_clip(roic_now / (targets["base"] * (1 - tax_m)), s2c_base / 2, 2 * s2c_base), *A.S2C_BOUNDS)
            consist_note = f"S2C {s2c_base:.2f} implizierte Grenz-ROIC {impl:.1%} vs. {roic_kind} {roic_now:.1%} -> S2C {new:.2f}"
            s2c_base = new
    S2C = {"base": s2c_base, "pessimistic": 0.75 * s2c_base, "optimistic": 1.25 * s2c_base}
    fade_note = None
    fade = R.TERMINAL_EXCESS_SHARE[cl["moat"]]
    if cl["moat"] == "none" and not moat_measured:
        fade = R.TERMINAL_EXCESS_SHARE["narrow"]; fade_note = "Burggraben nicht messbar (kurze Historie/Strukturbruch) ≠ kein Burggraben: Fade 0,25"
    w_dcf = R.DCF_WEIGHT[cl["stage"]]
    if arch == "mature":
        w_dcf = 0.5
    if cl["reinvester"] or not cons or not level_ok or perimeter or arch in ("buildout", "pre_revenue", "turnaround", "cyclical", "defence", "conglomerate"):
        w_dcf = 1.0      # v5: no sector P/E block for cyclicals (peak EPS) and defence (LM rule)
    model = "excess_returns" if (arch in ("bank", "utility") or eq_route) else "affo" if arch == "reit" else "fcff"
    cl["model"] = model
    mlt = months_left_fy0(t, asof, cons) if cons else 6
    notes = [n_ for n_ in (growth_note, trend_note, s2c_note, consist_note, fade_note, *data_notes, *v51_notes) if n_]
    flags = []
    if perimeter:
        flags.append("Perimeterwechsel – nicht belastbar (Konsens auf neuem Konzernkreis)")
    scen = {}; base_inputs = None; fin = {}; nav = None; sotp = None; implied_roic = None
    if model in ("excess_returns", "affo"):
        kind = "reit" if arch == "reit" else "utility" if arch == "utility" else (eq_route or ("insurer" if typ == "Versicherung" else "bank"))
        ke = cap["cost_of_equity"]
        if kind == "reit":
            b_r = min(beta or 1.0, 1.0); ke = rf + b_r * erp + (crp or 0); cap.update(cost_of_equity=ke, beta_reit_capped=b_r)
        q = equity_v5(t, asof, kind, price, dict(equity=fs.get("equity"), net_income=fs.get("net_income_ttm"), shares=fs["shares_diluted"],
                                                 revenue=fs["revenue_ttm"], rev_cagr_3y=fs.get("rev_cagr_3y")), ke, gT, tax_m, cons, rf)
        if q is None:
            if kind == "reit":
                return dict(ticker=t, status="REIT ohne FFO-Daten", classification=cl)
            return dict(ticker=t, status="Datenlücke: Eigenkapital/ROE-Historie für Eigenkapitalmodell fehlt", classification=cl)
        cl["equity_model_kind"] = kind
        for s_, (v, d) in q["scen"].items():
            scen[s_] = dict(fair_value=v, intrinsic=v, pe_value=None, model_detail=d, forward_pe=None, margin_target=None, growth=None)
        notes += q["notes"]; flags += q["flags"]; fin = q["fin"]; w_dcf = 1.0
        if kind == "reit":
            # CYC R3: NAV cross-check = NOI / cap rate - net debt; cap rate = ke - g_T (same Gordon logic), >= 4 %
            rr_ = I.fund_asof(t, asof)
            dna = float(rr_["dna_ttm"]) if rr_ is not None and "dna_ttm" in rr_.index and pd.notna(rr_["dna_ttm"]) else None
            if dna is not None:
                noi = fs["ebit_ttm"] + dna; cr = max(0.04, ke - gT)
                nav = dict(noi=noi, cap_rate=cr, nav_per_share=max(0.0, (noi / cr - fs["total_debt"] + fs["cash"]) / fs["shares_diluted"]))
                notes.append(f"NAV-Gegenprobe: NOI {noi / 1e9:,.2f} Mrd. / Cap-Rate {cr:.1%} − Nettoschulden = {nav['nav_per_share']:,.1f} je Aktie")
    else:
        eqm = C.instant(t, "eq_method", asof) or 0.0
        if eqm > 0:   # v5.1 (a): equity-method stakes earn outside EBIT -> non-operating asset at book value
            notes.append(f"At-equity-Beteiligungen {eqm / 1e9:,.2f} Mrd. als nicht-operatives Vermögen (Buchwert) addiert")
        nolv = C.instant(t, "nol", asof)
        nol0 = nolv / max(tax_m, 0.15) if nolv and nolv > 0 else None       # GROWTH 2: start NOL = deferred tax asset / rate
        if nol0:
            notes.append(f"Verlustvortrag {nol0 / 1e9:,.2f} Mrd. (latente Steuer {nolv / 1e9:,.2f} Mrd.) mindert spätere Steuer")
        intr, dets, pev, fps = {}, {}, {}, {}
        for s in ("pessimistic", "base", "optimistic"):
            g1, g2 = G[s]
            ex = dict(g_cap3=G_CAP3, rev_cap_cagr=REV_CAP_CAGR, nol0=nol0)
            if cyc_trend:
                tr, sl = cyc_trend; sl_s = sl + {"pessimistic": -0.02, "base": 0.0, "optimistic": 0.02}[s]
                r1 = rev0 * (1 + _clip(g1, *gclip)); r2 = r1 * (1 + _clip(g2, *gclip)); t5 = tr * (1 + sl_s) ** 5
                path = [r1, r2] + [math.exp(math.log(r2) + (math.log(t5) - math.log(r2)) * k / 3) for k in (1, 2, 3)]
                for k in range(6, R.EXPLICIT_YEARS + 1):
                    gk = sl_s + (gT - sl_s) * (k - 5) / (R.EXPLICIT_YEARS - 5); path.append(path[-1] * (1 + gk))
                ex["rev_path"] = path
            s2c_s = _clip(S2C[s], *A.S2C_BOUNDS); roic_s, fade_s = roic_now, fade
            if arch == "buildout":
                # GROWTH 1: capacity cohorts reach the mature margin in 3 years; value = bet on ROIC of new capacity
                rn = cap["wacc"] + {"pessimistic": -BUILDOUT_ROIC_BAND, "base": 0.0, "optimistic": BUILDOUT_ROIC_BAND}[s]
                mt = max(targets[s], 0.02)
                s2c_s = _clip(rn / (mt * (1 - tax_m)), *A.S2C_BOUNDS); roic_s, fade_s = rn, 1.0
                ex["margin_years"] = BUILDOUT_CONV_Y
            di = DCFInputs(revenue0=rev0, margin0=m0, margin_target=targets[s],
                           growth_y1=_clip(g1, *gclip), growth_y2=_clip(g2, *gclip), terminal_g=gT,
                           tax0=tax_eff, tax_marginal=tax_m, sales_to_capital=s2c_s, roic_now=roic_s,
                           wacc0=cap["wacc"], wacc_mature=cap["wacc_mature"], net_debt=fs["total_debt"] - fs["cash"] - eqm,
                           shares=fs["shares_diluted"], years=R.EXPLICIT_YEARS, roic_fade=fade_s, extra=ex)
            d = run_dcf(di, detail=detail or arch == "buildout"); v = d["value_per_share"]
            if fs.get("captive_equity"):
                v += CAPTIVE_PB * fs["captive_equity"] / fs["shares_diluted"]
            intr[s] = max(0.0, v); dets[s] = dict(d, sales_to_capital=s2c_s)
            if s == "base":
                base_inputs = di
            fp = pe_val = None
            if cons and w_dcf < 1.0:
                fp = forward_block(price, cons_pe["years"], mlt, cap["cost_of_equity"],
                                   _clip((fs["net_income_ttm"] or 0) / fs["equity"], 0.05, 0.40) if fs.get("equity") else 0.12, gT, scenario=s)
                ntm, eps_note = ntm_eps_clean(cons_pe, mlt, price, s)
                ind = ((peers.get("_pe_by_typ") or {}).get(typ) or {})
                if ntm and ind.get("n", 0) >= MIN_PEERS:
                    pe_val = ind["median"] * ntm
                    fp = dict(fp or {}, fair_price=pe_val, method=f"Branchen-Median-Forward-KGV {ind['median']:.1f}× ({typ}, n={ind['n']}) × NTM-EPS {ntm:.2f}",
                              industry_pe=ind["median"], ntm_eps_clean=ntm, eps_note=eps_note)
                elif ntm:
                    pe_val = fp["fair_price"]; fp["eps_note"] = eps_note
                else:
                    pe_val = None; fp = dict(fp or {}, fair_price=None, eps_note=eps_note)
            pev[s], fps[s] = pe_val, fp
        # v5 bug fix (CYC X2): blend weights and block availability identical in every scenario
        use_pe = w_dcf < 1.0 and all(pev[s] for s in pev)
        if w_dcf < 1.0 and not use_pe:
            notes.append("KGV-Block fehlt in mindestens einem Szenario -> in allen Szenarien nur DCF"); w_dcf = 1.0
        for s in ("pessimistic", "base", "optimistic"):
            fv = w_dcf * intr[s] + (1 - w_dcf) * (pev[s] if use_pe else intr[s])
            scen[s] = dict(fair_value=max(0.0, fv), intrinsic=intr[s], pe_value=pev[s] if use_pe else None, model_detail=dets[s],
                           forward_pe=fps[s], margin_target=targets.get(s), growth=G[s], sales_to_capital=dets[s]["sales_to_capital"])
        if arch == "buildout" and base_inputs is not None:
            def _val(rn):
                mt = max(targets["base"], 0.02)
                di_ = replace(base_inputs, sales_to_capital=_clip(rn / (mt * (1 - tax_m)), *A.S2C_BOUNDS), roic_now=rn, roic_fade=1.0)
                return run_dcf(di_, detail=False)["value_per_share"] + (fs.get("captive_equity") or 0) / fs["shares_diluted"] - price
            from .dcf import _bisect
            implied_roic = _bisect(_val, -0.05, 0.80)
            notes.append("Kapazitätsaufbau: Wert = Wette auf ROIC neuer Kapazität; Spanne ROIC_neu = WACC −3 pp / WACC / +3 pp; "
                         + (f"Kurs impliziert ROIC_neu ≈ {implied_roic:.1%} (WACC {cap['wacc']:.1%})" if implied_roic is not None else "Kurs impliziert ROIC_neu > 80 % oder nicht lösbar"))
        if arch == "conglomerate":
            # MEGA 8: SOTP from XBRL segments, each at its own margin and growth; central costs capitalised; net debt once
            evs, rows_ = 0.0, []
            for sg in seg["segments"]:
                if sg["other"]:
                    continue
                gs_ = _clip(sg["growth"] if sg["growth"] is not None else G["base"][0], -0.05, 0.30)
                di_ = replace(base_inputs, revenue0=sg["revenue"], margin0=sg["margin"], margin_target=sg["margin"], growth_y1=gs_, growth_y2=gs_,
                              net_debt=0.0, shares=1.0, extra=dict(g_cap3=G_CAP3, rev_cap_cagr=REV_CAP_CAGR))
                ev_ = run_dcf(di_, detail=False)["ev"]; evs += ev_
                rows_.append(dict(segment=sg["segment"], revenue=sg["revenue"], margin=sg["margin"], growth=gs_, ev=ev_))
            seg_ebit = sum(sg["ebit"] for sg in seg["segments"])
            central = fs["ebit_ttm"] - seg_ebit
            cv = central * (1 - tax_m) / max(cap["wacc_mature"] - gT, 0.02) if central < 0 else 0.0
            eq_ = evs + cv - (fs["total_debt"] - fs["cash"]) + (fs.get("captive_equity") or 0)
            v_ = max(0.0, eq_ / fs["shares_diluted"])
            sotp = dict(applied=True, segments=rows_, central_costs=central, central_value=cv, per_share=v_, fy_end=seg["fy_end"])
            b_ = scen["base"]["fair_value"] or 1e-9
            for s in scen:
                scen[s]["consolidated"] = scen[s]["fair_value"]; scen[s]["fair_value"] = v_ * (scen[s]["fair_value"] / b_) if b_ > 1e-9 else v_
            notes.append(f"Summe der Teile ({len(rows_)} Segmente, Zentralkosten {central / 1e9:,.2f} Mrd.): {v_:,.1f} je Aktie")
    # pre_revenue (GROWTH 3, bug fix): no DCF on < 50 Mio. revenue; value = cash floor after one year of burn
    burn = max(0.0, -(fs.get("fcf_ttm") or 0))
    if arch == "pre_revenue":
        floor = max(0.0, (fs["cash"] - fs["total_debt"] - burn) / fs["shares_diluted"])
        for k in ("pessimistic", "base"):
            scen[k]["dcf_info"] = scen[k]["fair_value"]; scen[k]["fair_value"] = floor; scen[k]["floor"] = "Netto-Cash nach 1 Jahr Mittelabfluss"
        scen["optimistic"]["fair_value"] = max(floor, scen["optimistic"]["fair_value"])
        flags.append(f"nicht modellierbar (keine Pipeline-/Marktdaten): nur Cash-Untergrenze {floor:,.2f}; Kurs bezahlt {max(0.0, price - floor):,.2f} je Aktie Optionswert")
    nc = (fs["cash"] - fs["total_debt"]) / fs["shares_diluted"]
    if nc > 0 and model == "fcff" and arch != "pre_revenue" and ((fs.get("fcf_ttm") or 0) > 0 or fs["cash"] > 3 * burn):
        for k in ("pessimistic", "base", "optimistic"):
            if scen[k]["fair_value"] < nc:
                scen[k]["fair_value"] = nc; scen[k]["floor"] = "Netto-Cash je Aktie"
    pdef = None
    if model == "fcff" and arch in ("turnaround", "buildout"):
        if arch == "turnaround":
            # MEGA 6: value = (1-p) x going concern + p x distress; p from synthetic rating on normalised EBIT
            ebn = max(fs["ebit_ttm"], (fs["margin_3y_median"] or 0) * fs["revenue_ttm"])
            pdef, cov = V5.default_probability(ebn, (fs.get("debt_info") or {}).get("interest") or interest, fs["total_debt"])
            ic_b = (capx.get("ic_ex") if capx.get("ic_ex") and capx["ic_ex"] > 0 else ic) or 0
            dist = max(0.0, (V5.DISTRESS_IC * max(ic_b, 0) + fs["cash"] - fs["total_debt"]) / fs["shares_diluted"])
            why_p = f"Ausfallwahrscheinlichkeit {pdef:.0%} (Zinsdeckung normalisiert {cov:.1f}×)" if cov is not None else "keine verzinslichen Schulden: Ausfall 0 %"
        else:
            ppe = C.instant(t, "ppe_net", asof) or 0.0
            runway = fs["cash"] / burn if burn > 0 else None
            pdef = 0.1 if burn <= 0 else 0.5 if runway < 1 else 0.35 if runway < 2 else 0.2
            dist = max(0.0, (ppe + fs["cash"] - fs["total_debt"]) / fs["shares_diluted"])
            why_p = f"Distress-Gewicht {pdef:.0%} aus Cash-Reichweite {('%.1f J' % runway) if runway else 'FCF ≥ 0'}"
        pdef = min(pdef, TURN_SHARE_CAP)
        for k in ("pessimistic", "base", "optimistic"):
            scen[k]["going_concern"] = scen[k]["fair_value"]
            scen[k]["fair_value"] = (1 - pdef) * scen[k]["fair_value"] + pdef * dist
        notes.append(f"{why_p}; Distress-Wert {dist:,.2f} je Aktie")
    if arch == "hyper" and (fs["margin_ttm"] or 0) < 0 and not scen["pessimistic"].get("floor"):
        scen["pessimistic"]["fair_value"] = 0.0; scen["pessimistic"]["floor"] = "Scheitern (Hyper mit Verlust, audit F6)"
    base = scen["pessimistic"] if arch == "defence" else scen["base"]     # LM rule restored: defence on the pessimistic GAAP basis
    base_fv = base["fair_value"]
    cl.update(consensus_note=cons_note, only_annual=fs.get("only_annual", False),
              stale=(pd.Timestamp(asof) - pd.Timestamp(fs["last_quarter_end"])).days > (STALE_HYPER_DAYS if (g_stage or 0) > 0.5 else R.STALE_DAYS),
              reporting_currency=rep_cur, structural_break=x["structural_break"], model_notes=notes, model_flags=flags,
              terminal_fade=fade, roic_basis=roic_kind, default_probability=pdef, implied_roic_new=implied_roic)
    if arch == "turnaround":
        cl["margin_of_safety"] = max(cl["margin_of_safety"] or 0, TURNAROUND_MOS)
    vals = [v["fair_value"] for k, v in scen.items() if k in ("pessimistic", "base", "optimistic")]
    if arch == "defence":
        vals = [min(vals), base_fv, max(vals)]
    raw_pess = min(vals)
    range_note = None
    if base_fv and base_fv > 0 and (max(vals) > RANGE_MAX * base_fv or min(vals) < base_fv / RANGE_MAX) and arch not in ("pre_revenue", "buildout"):
        range_note = f"Spanne nicht belastbar (pess {min(vals) / base_fv:.2f}× / opt {max(vals) / base_fv:.2f}× Basis) – auf 1/3–3× begrenzt"
        vals = [_clip(v, base_fv / RANGE_MAX, RANGE_MAX * base_fv) for v in vals]
    out = dict(ticker=t, status="ok", asof=str(pd.Timestamp(asof).date()), price=price, type=typ, classification=cl,
               archetype=dict(key=arch, raw=raw_arch, prev_quarter=prev, name=AR.ARCH[arch][0], rationale=AR.ARCH[arch][1], rule=why,
                              features={k: v for k, v in x.items()}, peer_n=pe.get("n"), peer_group=pe_kind,
                              margin_reference=ref_kind, scenario_weights=None),
               fair_value=base_fv, upside=base_fv / price - 1,
               range=dict(pessimistic=min(vals), base=base_fv, optimistic=max(vals)),
               weights=dict(dcf=w_dcf, forward_pe=1 - w_dcf), cost_of_capital=cap, terminal_growth=gT,
               months_left_fy0=mlt if cons else None,
               margin=dict(start=m0, start_reported=m0_raw, normalisation=norm_note, own_basis=own, own_basis_kind="Zyklusmedian bis 10J" if cyc and lw and lw["long_enough"] else "eigener 3J-Median",
                           sector_median=smed, reference=ref_kind, reversion_share=rev_share, targets=targets),
               long_window=lw, firm=fs if detail else None, scenarios=scen if detail else None,
               range_note=range_note, debt=fs.get("debt_info"), raw_pess=raw_pess, nav=nav, fin_history=fin or None,
               capital=dict(capx, roic_now=roic_now, roic_basis=roic_kind) if capx else None,
               sotp=sotp or dict(applied=False, reason="keine XBRL-Segmente mit ≥ 2 Geschäftsfeldern (≥ 15 % Umsatz, > 10 pp Margenabstand) -> konsolidiertes Modell"))
    out["buy_zone_below"] = base_fv * (1 - (cl["margin_of_safety"] if cl["margin_of_safety"] is not None else R.MOS_NO_ESTIMATES))
    if detail and model == "fcff" and base_inputs is not None:
        out["reverse_dcf"] = reverse_dcf(base_inputs, price)
        out["sensitivity"] = sensitivity(base_inputs, rf)
    _guards(out, price)
    return out


def _guards(out, price):
    rg = out["range"]; why = []
    if rg["optimistic"] <= rg["base"] * 1.0001 and out["archetype"]["key"] not in ("bank", "reit", "utility"):
        why.append("optimistisch nicht über Basis")
    if not rg["base"] or rg["base"] <= 0:
        why.append("Basiswert ≤ 0 (Eigenkapitalwert negativ)")
    else:
        r = rg["base"] / price
        if not UNRELIABLE[0] <= r <= UNRELIABLE[1]:
            why.append(f"fairer Wert {r:.2f}× Kurs (außerhalb {UNRELIABLE[0]}–{UNRELIABLE[1]}×)")
    if (out.get("firm") or {}).get("share_class_note"):
        why.append("Aktienzahl unklar: " + out["firm"]["share_class_note"])
    rp = out.get("raw_pess")
    if rp is not None and rg["base"] and rg["base"] > 0 and out["archetype"]["key"] != "pre_revenue" and rp / rg["base"] < 0.25:
        why.append(f"pessimistisch {rp / rg['base']:.2f}× Basis (< 0,25: Ausfallszenario dominiert)")
    fm = out.get("firm") or {}
    is_fcff = (out.get("classification") or {}).get("model") == "fcff"
    miss = [k for k in ("revenue_ttm", "ebit_ttm", "shares_diluted") if fm and is_fcff and fm.get(k) is None]
    if fm and (fm.get("invested_capital") is None or fm["invested_capital"] <= 0) and out["classification"].get("model") == "fcff":
        miss.append("investiertes Kapital ≤ 0/fehlt")
    if miss:
        why.append("Pflichtdaten fehlen: " + ", ".join(miss))
    di = out.get("debt") or {}
    for fl in (out.get("classification") or {}).get("model_flags") or []:
        why.append(fl)
    if out["archetype"]["key"] == "buildout":
        why.append("Kapazitätsaufbau: Wert = Wette auf ROIC neuer Kapazität (Spanne statt Punktwert)")
    if di.get("zero_debt_interest") and is_fcff:          # v5 bug fix (CYC X7): debt guard only where debt enters the model
        why.append(f"Schulden 0 bei Zinsaufwand {di['interest'] / 1e6:,.0f} Mio. – Schuldenangabe unvollständig")
    if (out.get("classification") or {}).get("stale"):
        why.append("Zahlen veraltet")
    # v5 (LM 22.10.): every range methodically bounded: pessimistic >= 0.5 x base, optimistic <= 2 x base (scenario inputs
    # are consensus low/high, own cycle p25/p75, S2C +-25 %: a wider spread means the inputs do not pin the value down)
    rg_ok = bool(rg["base"] and rg["base"] > 0 and rg["pessimistic"] >= RANGE_BOUND[0] * rg["base"] and rg["optimistic"] <= RANGE_BOUND[1] * rg["base"])
    if rg["base"] and rg["base"] > 0 and not rg_ok:
        why.append(f"Spanne außerhalb der Methodengrenzen (pess {rg['pessimistic'] / rg['base']:.2f}× / opt {rg['optimistic'] / rg['base']:.2f}× Basis; erlaubt {RANGE_BOUND[0]}–{RANGE_BOUND[1]}×)")
    hard = [w for w in why if w != "optimistisch nicht über Basis"]
    out["reliable"] = not hard
    out["unreliable_reasons"] = why
    # v5 display contract (new fields, existing ones unchanged): display_mode value | implied_return | nicht_belastbar
    cl_ = out.get("classification") or {}
    if out["archetype"]["key"] == "buildout":
        out["display_mode"] = "implied_return"
        out["implied_return"] = dict(kind="ROIC auf neue Kapazität", value=cl_.get("implied_roic_new"), wacc=(out.get("cost_of_capital") or {}).get("wacc"))
    else:
        out["display_mode"] = "value" if out["reliable"] else "nicht_belastbar"
        out["implied_return"] = None
    out["range_valid"] = bool(rg_ok and out["display_mode"] == "value")
    out["stress_loss_max"] = 1.0                       # loss capped at 100 % of stake (value floor 0)
