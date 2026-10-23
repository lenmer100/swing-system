"""v4 archetype classifier: purely point-in-time numbers (filings available at `asof`, consensus snapshot if live).
Rules are fixed a priori from economic reasoning (design_ref/VALUATION_V4.md) and checked - not fitted - on 2012-19.
First matching rule wins; every result carries the features and the rule text that fired."""
from __future__ import annotations
import math
import functools, json
from pathlib import Path
import numpy as np
import pandas as pd
from . import inputs as I

# --- fixed thresholds (economic rationale in VALUATION_V4.md; not optimised) -----------------------------
PRE_REVENUE_USD = 50e6          # < 50 Mio. USD TTM revenue: value is an option on a business that does not exist yet
BUILDOUT_CAPEX_REV = 0.40       # capex >= 40 % of revenue ...
BUILDOUT_G = 0.20               # ... while growing >= 20 % ...
                                 # ... and FCF < 0: the asset base is being built ahead of revenue (funding need)
CYC_REV_DROP = -0.10            # cyclical: revenue fell >= 10 % y/y at least once in <= 10y ...
CYC_MARGIN_HALF = 0.5           # ... and op. margin fell to <= 50 % of its 10y median (or median <= 0): demand AND
CYC_MIN_Q = 20                  #     operating leverage swing together (checked on 2012-19 only, see VALUATION_V4.md)
CYC_SPREAD = 0.10               # p90-p10 margin spread: only used to add cycle risk to a hyper-grower's bear case
HYPER_G = 0.25                  # forward (FY+2) or trailing 3y revenue growth >= 25 %
MEGA_MCAP = 500e9               # market value >= 500 Mrd. USD ...
MEGA_MARGIN = 0.20              # ... with >= 20 % op. margin and positive FCF: scale + pricing power
QUALITY_G = 0.08                # >= 8 % growth ...
QUALITY_MARGIN = 0.15           # ... with >= 15 % 3y-median op. margin and positive FCF
BANK_LOANS_SHARE = 0.10        # bank model only with loans >= 10 % of total assets (lender balance sheet), insurers by type
SPIN_REV_DROP = -0.25     # v4.2: revenue -25 % y/y ...
SPIN_SHARES = 0.10        # ... with < 10 % share-count change and intact margin = spin-off/divestiture
BREAK_RATIO = 3.0               # revenue 3y ago > 3x today (divestiture/spin-off/currency switch) -> structural break

ARCH = {
    "bank": ("Bank/Versicherer", "Bilanz ist das Geschäft: Wert = Eigenkapital + Übergewinn auf Eigenkapital."),
    "reit": ("REIT", "Ausschüttungspflichtiger Immobilienbestand: Wert aus FFO/AFFO."),
    "utility": ("Versorger", "Regulierte Kapitalrendite: Wert = Eigenkapital + Übergewinn auf erlaubte Eigenkapitalrendite."),
    "pre_revenue": ("Frühphase (kaum Umsatz)", f"Umsatz < {PRE_REVENUE_USD / 1e6:.0f} Mio. USD: Wert ist eine Option; Szenarien inkl. Scheitern (Wert 0), fest gewichtet."),
    "buildout": ("Kapazitätsaufbau (Infrastruktur)", f"Investitionen ≥ {BUILDOUT_CAPEX_REV:.0%} vom Umsatz bei ≥ {BUILDOUT_G:.0%} Wachstum und negativem Free Cashflow: Anlagen werden vor dem Umsatz gebaut; Zielmarge von reifen kapitalintensiven Vergleichsfirmen, Finanzierungslücke verwässert."),
    "turnaround": ("Verlust/Turnaround", "Operativer Verlust bei relevantem Umsatz: Wert hängt an der Rückkehr zur Branchenmarge; pessimistisch Abwicklung zum Wert 0."),
    "cyclical": ("Zykliker", "Umsatz fiel in den letzten bis zu 10 Jahren um ≥ 10 % und die Marge halbierte sich zeitweise (oder Zyklusbranche): Bewertung mit Zyklusmitte-Marge statt aktueller Marge."),
    "hyper": ("Hyperwachstum-Plattform", f"Umsatzwachstum ≥ {HYPER_G:.0%}: Konsens Jahr 1–2 ungekappt, Marge konvergiert zu Vergleichsfirmen desselben Typs."),
    "mega": ("Mega-Cap-Compounder", f"Börsenwert ≥ {MEGA_MCAP / 1e9:.0f} Mrd. USD, Marge ≥ {MEGA_MARGIN:.0%}, positiver FCF: Skalen- und Preissetzungsmacht, Überrendite fällt langsam."),
    "quality": ("Qualitätswachstum", f"Wachstum ≥ {QUALITY_G:.0%} und Marge ≥ {QUALITY_MARGIN:.0%} mit positivem FCF."),
    "scaler": ("Wachstum mit Marge im Aufbau", f"Wachstum ≥ {QUALITY_G:.0%}, Marge noch < {QUALITY_MARGIN:.0%}: Wert hängt an der Margenausweitung."),
    "mature": ("Reif/Value", f"Wachstum < {QUALITY_G:.0%}, profitabel: Wert aus aktuellem Cashflow, KGV-Block gleichgewichtet."),
    "conglomerate": ("Mischkonzern", "≥ 2 Segmente mit je ≥ 15 % Umsatz und > 10 pp Margenabstand (XBRL-Segmente): Summe der Teile."),
    "defence": ("Rüstung", "Rüstungskonzern (Liste/SIC): Auftragsbestand trägt den Umsatz, Marge = eigene 3J-Marge; Basis = pessimistisches GAAP-Szenario (LM-Regel), kein Branchen-KGV."),
}
BANK_TYPES = {"Bank", "Finanzen", "Versicherung"}
CYC_SIC_PREFIX = ("3711", "3713", "3714", "4512", "4522", "281", "282", "286", "287", "289", "331", "332", "333", "334",
                  "152", "153", "3531", "3532", "3533", "3523", "441", "442", "444")   # audit F4: autos, airlines, chemicals, metals, homebuilders, machinery, shipping
HYST = dict(hyper=0.20, quality_g=0.06, quality_m=0.12, mega_mcap=400e9, mega_m=0.16, scaler_g=0.06, mature_g=0.10, turn_m=0.0)
# audit F10: leave a class only beyond a ~20 % relative band around its entry threshold (entry 25 % / 8 % / 15 % / 500 Mrd.)
CYC_TYPES = {"Halbleiter", "Rohstoffe", "Energie", "Speicher", "Solar", "Hausbau"}


def _f(x):
    try:
        x = float(x)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def features(t, asof, fs, price, cons=None, typ=None):
    f = I.fund(t)
    f = f[f.avail_date <= pd.Timestamp(asof)] if f is not None else None
    r = f.iloc[-1] if f is not None and len(f) else None
    g = lambda k, row=r: _f(row.get(k)) if row is not None and k in row.index else None
    rev = fs.get("revenue_ttm") if fs else None
    capex = g("capex_ttm"); ocf = g("op_cash_flow_ttm")
    sh_now = fs.get("shares_diluted") if fs else None
    sh3 = None
    if f is not None and len(f) >= 13:
        r3 = f.iloc[-13]; sh3 = _f(r3.get("shares_best")) or _f(r3.get("shares_dil"))
    dil = None
    if f is not None and len(f) >= 13 and sh_now:
        # split-adjusted: a quarter-on-quarter jump >= 1.9x (or <= 1/1.9) in the share count is a split, not issuance (audit G9)
        ss = [(_f(r_.get("shares_best")) or _f(r_.get("shares_dil"))) for _, r_ in f.tail(13).iterrows()]
        ss = [v for v in ss if v]
        if len(ss) >= 2:
            adj = 1.0
            for a_, b_ in zip(ss[:-1], ss[1:]):
                q = b_ / a_
                if q >= 1.9 or q <= 1 / 1.9:
                    adj *= q
            dil = ((ss[-1] / adj) / ss[0]) ** (1 / 3) - 1 if ss[0] > 0 else None
    m_long = None; spread = None; nq = 0; m_p10 = None; rev_dd = None; m_p25 = m_p75 = None; last_spin = None
    if f is not None and len(f):
        h = f.tail(40)
        if "operating_income_ttm" in h:
            m = (h.operating_income_ttm / h.revenue_ttm).replace([np.inf, -np.inf], np.nan).dropna()
            nq = int(len(m))
            if nq >= CYC_MIN_Q:
                spread = float(m.quantile(0.9) - m.quantile(0.1)); m_long = float(m.median()); m_p10 = float(m.quantile(0.1))
                rv = h.revenue_ttm.values; ends = pd.to_datetime(h.last_quarter_end).values
                yy = [(rv[i] / rv[i - 4] - 1, pd.Timestamp(ends[i]).year) for i in range(4, len(rv)) if rv[i - 4] and rv[i - 4] > 0]
                dy = _disc_years(t, asof)
                # v4.2 spin-off rule: revenue -25 % y/y with share count change < 10 % and no margin collapse
                # (margin >= 50 % of the prior median) = divestiture/spin-off, not a cycle; same for disc-ops years
                sh = h.shares_best.values if "shares_best" in h else [None] * len(rv)
                mm_ = (h.operating_income_ttm / h.revenue_ttm).values
                spins = set()
                for i in range(4, len(rv)):
                    if rv[i - 4] and rv[i - 4] > 0 and rv[i] / rv[i - 4] - 1 <= SPIN_REV_DROP and sh[i] and sh[i - 4] \
                            and abs(sh[i] / sh[i - 4] - 1) < SPIN_SHARES and np.isfinite(mm_[i]) \
                            and mm_[i] >= 0.5 * float(np.nanmedian(mm_[max(0, i - 12):i - 3])):
                        spins.add(pd.Timestamp(ends[i]).year)
                last_spin = max(spins | {y for y in dy if y <= pd.Timestamp(asof).year}) if (spins or dy) else None
                drops = [(v, y) for v, y in yy if v <= CYC_REV_DROP and y not in dy and y not in spins]
                # audit H/C3: a single drop in 2020-21 (pandemic, spin-offs) is not a cycle; >= 2 separate drops or one outside 2020-21 is
                episodes = sorted({y for _, y in drops})
                out_pand = [v for v, y in drops if y not in (2020, 2021)]
                rev_dd = min(out_pand) if out_pand else (min(v for v, _ in drops) if len(episodes) >= 2 and max(episodes) - min(episodes) >= 2 else None)
                m_p25 = float(m.quantile(0.25)); m_p75 = float(m.quantile(0.75))
    g_fwd = None
    if cons and len(cons.get("years", [])) >= 2:
        g_fwd = _f(cons["years"][1].get("rev_growth"))
    g_tr = fs.get("rev_cagr_3y") if fs else None
    brk = bool(fs and fs.get("revenue_ttm_3y_ago") and rev and fs["revenue_ttm_3y_ago"] / rev > BREAK_RATIO)
    spin_recent = bool(last_spin is not None and pd.Timestamp(asof).year - last_spin <= 2 and last_spin not in (2020, 2021))
    brk = brk or spin_recent
    if brk:
        g_tr = None
    mcap = price * sh_now if price and sh_now else None
    fcf = fs.get("fcf_ttm") if fs else None
    return dict(revenue=rev, capex_rev=abs(capex) / rev if capex is not None and rev else None,
                growth_fwd=g_fwd, growth_trailing=g_tr, growth=g_fwd if g_fwd is not None else g_tr,
                margin=fs.get("margin_ttm") if fs else None, margin_3y=fs.get("margin_3y_median") if fs else None,
                margin_trend=(fs["margin_ttm"] - fs["margin_3y_median"]) if fs and fs.get("margin_3y_median") is not None else None,
                margin_long=m_long, margin_spread=spread, margin_p10=m_p10, margin_p25=m_p25, margin_p75=m_p75, loans_share=_loans_share(t, asof) if typ in BANK_TYPES else None, rev_drawdown=rev_dd, cycle=bool(rev_dd is not None and rev_dd <= CYC_REV_DROP and m_long is not None and (m_long <= 0 or m_p10 <= CYC_MARGIN_HALF * m_long)), margin_quarters=nq,
                fcf=fcf, fcf_yield=fcf / mcap if fcf is not None and mcap else None, mcap=mcap,
                dilution_3y=dil, sbc_rev=fs["sbc_ttm"] / rev if fs and fs.get("sbc_ttm") and rev else None,
                ocf=ocf, ocf_rev=ocf / rev if ocf is not None and rev else None, structural_break=brk,
                ebitda_3y=_ebitda3(f), ebitda_ttm=_ebitda3(f.tail(1)) if f is not None and len(f) else None, regulated=_regulated(t, asof) if typ == "Versorger" else None,
                cyc_sic=cyc_sic(t)[0], sic=cyc_sic(t)[1], defence=_defence(t))


def _defence(t):
    from . import assumptions as A
    v = _sic().get(t)
    return bool(t in A.DEFENCE or (v and v[0] and str(v[0]).startswith(A.DEFENCE_SIC)))


@functools.lru_cache(maxsize=1)
def _sic():
    p = Path(__import__("os").environ.get("MARKET_STORE", "data_store") + "/derived/v34_sic.json")
    return json.loads(p.read_text()) if p.exists() else {}


def cyc_sic(t):
    v = _sic().get(t)
    return bool(v and v[0] and str(v[0]).startswith(CYC_SIC_PREFIX)), (v[1] if v else None)


def _disc_years(t, asof):
    """Years with material discontinued operations (|disc_ops| >= 2 % of revenue): spin-off/divestiture, not a cycle (audit F3)."""
    d = I.raw(t)
    if d is None or not (d.key == "disc_ops").any():
        return set()
    d = d[(d.filed <= pd.Timestamp(asof))]
    do = d[d.key == "disc_ops"].copy(); rv = d[d.key == "revenue"]
    if "start" in do:
        do = do[(do.end - do.start).dt.days > 330]; rv = rv[(rv.end - rv.start).dt.days > 330]
    r = rv.groupby(rv.end.dt.year).val.last()
    out = set()
    for e, v in do.groupby(do.end.dt.year).val.apply(lambda z: z.abs().max()).items():     # max over filings (restatements shrink it)
        if e in r.index and r[e] and abs(v) >= 0.02 * abs(r[e]):
            out |= {e, e + 1}
    return out


def _ebitda3(f):
    """3y median EBITDA margin (op. income + D&A over revenue, TTM rows): scale/pricing power through a capex wave."""
    if f is None or len(f) < 1 or "dna_ttm" not in f:
        return None
    h = f.tail(12)
    m = ((h.operating_income_ttm + h.dna_ttm.fillna(0)) / h.revenue_ttm).replace([np.inf, -np.inf], np.nan).dropna()
    return float(m.median()) if len(m) else None


def _regulated(t, asof):
    """Regulated-utility evidence: regulatory assets >= 3 % of total assets in the latest XBRL instance (filed <= asof).
    None = no instance (backtest) -> the cycle pattern alone decides."""
    from . import xbrl_instance as X
    d = X.load(t)
    if d is None or not len(d) or pd.Timestamp(d.filed.iloc[0]) > pd.Timestamp(asof):
        return None
    e = d[d.start.isna()].end.value_counts().idxmax(); x = d[(d.end == e) & (d.dims == "")]
    # v5 (CYC U2): regulatory assets (any RegulatoryAsset* tag) >= 3 % of assets OR utility plant (PublicUtilities PP&E net)
    # >= 30 % of assets: a rate base exists (SO tags 'OtherRegulatoryAssets*' and utility plant only)
    ra = x[x.name.str.contains(r"us-gaap:\w*RegulatoryAsset", regex=True) & ~x.name.str.contains("Liabilit")].groupby("name").value.max().sum()
    up = x[x.name == "us-gaap:PublicUtilitiesPropertyPlantAndEquipmentNet"].value.max()
    ta = x[x.name == "us-gaap:Assets"].value.max()
    if not ta or not ta > 0:
        return False
    return bool(ra / ta >= 0.03 or (pd.notna(up) and up / ta >= 0.30))


def _loans_share(t, asof):
    """Bank balance-sheet evidence (audit F): loans receivable / total assets from EDGAR raw facts at asof."""
    d = I.raw(t)
    if d is None:
        return None
    d = d[d.filed <= pd.Timestamp(asof)]
    g = lambda k: d[d.key == k].sort_values("end").val.iloc[-1] if (d.key == k).any() else None
    ln, ta = g("loans_receivable"), g("total_assets")
    return float(ln / ta) if ln and ta else None


HARD = ("bank", "reit", "utility", "pre_revenue", "buildout", "defence")


def classify(typ, x, prev=None, raw_prev=None):
    """Hysteresis chain (audit F10). prev = final class last quarter, raw_prev = unfiltered class last quarter.
    Keep prev while its relaxed stay-condition holds; otherwise switch only if the new class also held last quarter."""
    k, why = _classify(typ, x)
    if not prev or prev == k or k in HARD or prev in HARD:
        return k, why
    if _stay(prev, typ, x):
        return prev, f"bleibt {prev} (Hysterese-Band; neu wäre {k}: {why})"
    # v5 hysteresis cap (mega audit 12): an unconfirmed switch keeps prev only if prev still held raw last quarter
    if raw_prev is not None and raw_prev != k and raw_prev == prev and _stay(prev, typ, x, wide=True):
        return prev, f"bleibt {prev} (Wechsel zu {k} noch nicht im Vorquartal bestätigt: {why})"
    return k, why


def raw_class(typ, x):
    return _classify(typ, x)[0]


def _stay(a, typ, x, wide=False):
    """wide=True: thresholds relaxed by one more band width (hysteresis cap: features far outside the band leave at once)."""
    H = HYST if not wide else dict(hyper=0.15, quality_g=0.04, quality_m=0.09, mega_mcap=300e9, mega_m=0.12, scaler_g=0.04, mature_g=0.12, turn_m=0.02)
    g, m, m3 = x.get("growth") or 0, x.get("margin") or 0, x.get("margin_3y") or 0
    cf = x["fcf"] if x.get("fcf") is not None else x.get("ocf")
    pos = cf is None or cf > 0 or (x.get("ocf") or 0) > 0
    return {"hyper": g >= H["hyper"], "scaler": g >= H["scaler_g"] and m >= -0.0,
            "quality": g >= H["quality_g"] and m3 >= H["quality_m"] and pos,
            "mega": (x.get("mcap") or 0) >= H["mega_mcap"] and max(m3, x.get("ebitda_3y") or 0) >= H["mega_m"] and pos,
            "mature": g < H["mature_g"] and m >= 0, "turnaround": m < H["turn_m"],
            "cyclical": bool(x.get("cycle") or ((typ in CYC_TYPES or x.get("cyc_sic")) and ((x.get("margin_quarters") or 0) < CYC_MIN_Q
                             or (x.get("margin_p10") is not None and x["margin_p10"] <= 0))))}.get(a, False)


def _classify(typ, x):
    """-> (key, rule text). typ = scanner balance-sheet type (only used for financial/regulated balance sheets
    and the cyclical-industry list)."""
    if typ == "Versicherung":
        return "bank", "Bilanztyp Versicherer"
    if typ in BANK_TYPES and (x.get("loans_share") or 0) >= BANK_LOANS_SHARE and (x.get("capex_rev") is None or x["capex_rev"] < 0.15):
        return "bank", f"Bilanztyp Bank: Kredite {x['loans_share']:.0%} der Bilanzsumme"
    if typ == "REIT":
        return "reit", "Bilanztyp REIT"
    if typ == "Versorger" and x.get("regulated") is False:
        return "cyclical", "Versorger ohne regulatorische Vermögenswerte (< 3 % der Bilanz): Erzeuger zu Marktpreisen"
    if typ == "Versorger" and not x.get("cycle"):
        # merchant generator = revenue drop >= 10 % AND margin halving (the cyclical pattern); a wide margin spread alone
        # (hedge marks of a regulated holding, e.g. NEE) is not enough -> reguliert
        return "utility", "Bilanztyp Versorger ohne Zyklusmuster (reguliert)"
    if typ == "Versorger":
        return "cyclical", "Versorger mit schwankender Marge: Erzeuger mit Großhandelspreisen (IPP), kein reguliertes Modell"
    rev, g, m = x["revenue"], x["growth"], x["margin"]
    if x.get("defence") and rev and rev >= PRE_REVENUE_USD:
        return "defence", "Rüstungskonzern (Liste A.DEFENCE / SIC 3795, 3761, 348x)"
    if rev is None or rev < PRE_REVENUE_USD:
        return "pre_revenue", f"Umsatz {0 if rev is None else rev / 1e6:,.0f} Mio. USD < {PRE_REVENUE_USD / 1e6:.0f} Mio."
    if x["capex_rev"] is not None and x["capex_rev"] >= BUILDOUT_CAPEX_REV and (g or 0) >= BUILDOUT_G and (x["fcf"] if x["fcf"] is not None else -1) < 0:
        return "buildout", f"Investitionen {x['capex_rev']:.0%} vom Umsatz, Wachstum {g:.0%}, FCF negativ"
    m3 = x.get("margin_3y")
    # v4.2: a cyclical has a positive cycle centre; a firm whose 3y or 10y median margin is a loss is a turnaround (BA)
    neg_centre = (m3 is not None and m3 < 0) or (x.get("margin_long") is not None and x["margin_long"] <= 0
                                                  and (x.get("margin_quarters") or 0) >= CYC_MIN_Q and (m3 is None or m3 <= 0.02))
    if m is not None and (neg_centre or (m < 0 and (m3 is None or m3 < 0.05))):
        return "turnaround", f"operative Marge {m:.1%}, 3J-Median {(m3 if m3 is not None else m):.1%} (Turnaround vor Zyklusbranche)"
    cf = x["fcf"] if x["fcf"] is not None else x["ocf"]
    pos_fcf = cf is None or cf > 0          # unknown cash flow (IFRS tag gaps) does not disqualify
    # audit F2: a capex wave must not demote a compounder: FCF > 0 OR OCF > 0; op. margin OR OCF margin >= 20 %
    # v4.2: margin test on 3y medians (op. margin or EBITDA margin; a capex wave does not touch EBITDA: AMZN), and a firm
    # whose cycle trough was an operating loss (p10 <= 0 with >= 20 quarters: memory, commodities) is cyclical, not mega (MU)
    trough_loss = (x.get("margin_p10") is not None and x["margin_p10"] <= 0 and (x.get("margin_quarters") or 0) >= CYC_MIN_Q
                   and (typ in CYC_TYPES or x.get("cyc_sic") or x.get("cycle")))
    # v5 (CYC C4): commodity types (energy, materials, memory) are cyclical before the mega test (XOM, MU)
    if typ in ("Energie", "Rohstoffe", "Speicher"):
        return "cyclical", f"Rohstoff-/Speicherzyklus ({typ}) vor Mega-Regel"
    mq = max(x.get("margin_3y") or 0, x.get("ebitda_3y") or 0, x.get("ebitda_ttm") or 0)   # entry on TTM or 3y; stay band on 3y
    if x["mcap"] and x["mcap"] >= MEGA_MCAP and mq >= MEGA_MARGIN and (pos_fcf or (x.get("ocf") or 0) > 0) and not trough_loss:
        return "mega", f"Börsenwert {x['mcap'] / 1e9:,.0f} Mrd., 3J-Marge {(x.get('margin_3y') or 0):.0%} / 3J-EBITDA-Marge {(x.get('ebitda_3y') or 0):.0%}, Cashflow positiv"
    # v5 (CYC C3): the industry label makes a cyclical only with a measured pattern (cycle or trough loss) once
    # >= 20 quarters exist; without enough history the label decides
    measured = (x.get("margin_quarters") or 0) >= CYC_MIN_Q
    if (typ in CYC_TYPES or x.get("cyc_sic")) and (not measured or x.get("cycle") or trough_loss or (g or 0) < HYPER_G):
        return "cyclical", f"Zyklusbranche ({typ if typ in CYC_TYPES else 'SIC ' + str(x.get('sic'))})" + (f", Konsenswachstum {g:.0%}" if g is not None else "")
    if g is not None and g >= HYPER_G:
        return "hyper", f"Wachstum {g:.0%} ≥ {HYPER_G:.0%}" + (" (Zyklusrisiko im pessimistischen Szenario)" if x["cycle"] else "")
    if typ in CYC_TYPES or x["cycle"]:
        why = f"Zyklusbranche ({typ})" if typ in CYC_TYPES else f"Umsatz fiel {x['rev_drawdown']:.0%} ggü. Vorjahr, Marge zeitweise {x['margin_p10']:.1%} vs. Median {x['margin_long']:.1%}"
        return "cyclical", why
    if m is not None and m < 0:
        return "turnaround", f"operative Marge {m:.1%} < 0"
    if (g or 0) >= QUALITY_G and (x["margin_3y"] or 0) >= QUALITY_MARGIN and pos_fcf:
        return "quality", f"Wachstum {g:.0%}, 3J-Marge {x['margin_3y']:.0%}, FCF positiv"
    if (g or 0) >= QUALITY_G:
        return "scaler", f"Wachstum {g:.0%}, 3J-Marge {(x['margin_3y'] or 0):.0%}" + (f" < {QUALITY_MARGIN:.0%}" if (x['margin_3y'] or 0) < QUALITY_MARGIN else ", FCF nicht positiv")
    return "mature", f"Wachstum {(g or 0):.0%} < {QUALITY_G:.0%}"
