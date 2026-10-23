"""v5: business segments from the latest annual XBRL instance (us-gaap:StatementBusinessSegmentsAxis):
revenue + operating income per reportable segment, latest fiscal year (and prior year for growth). Live only."""
import re
import pandas as pd
from . import xbrl_instance as X

REV = ("us-gaap:Revenues", "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
       "us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax", "us-gaap:SalesRevenueNet")
OI = ("us-gaap:OperatingIncomeLoss", "us-gaap:SegmentReportingInformationOperatingIncomeLoss")
SEG = "us-gaap:StatementBusinessSegmentsAxis="
CONG_SHARE = 0.15     # >= 2 segments with >= 15 % of revenue each ...
CONG_SPREAD = 0.10    # ... and a margin spread > 10 pp -> conglomerate (mega audit 8)
GEO = re.compile(r"NorthAmerica|International|Europe|EMEA|LatinAmerica|Asia|Pacific|Americas|UnitedStates|Domestic|Foreign|China|Japan|Africa|MiddleEast|Canada", re.I)
SKIP = re.compile(r"AllOther|Corporate|Elimination|Reconcil|Intersegment|Unallocated", re.I)


def _seg_only(dims):
    """Segment member if the fact carries only the business-segment axis (optionally with ConsolidationItems=OperatingSegments)."""
    parts = [p for p in dims.split(";") if p]
    segs = [p for p in parts if p.startswith(SEG)]
    rest = [p for p in parts if not p.startswith(SEG) and p != "srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember"]
    return segs[0][len(SEG):] if len(segs) == 1 and not rest else None


def segments(t, asof):
    d = X.load(t, annual=True)
    if d is None or not len(d) or pd.Timestamp(d.filed.iloc[0]) > pd.Timestamp(asof) or \
            (pd.Timestamp(asof) - pd.Timestamp(d.filed.iloc[0])).days > 456:
        return None
    d = d[d.start.notna() & d.dims.fillna("").str.contains("StatementBusinessSegmentsAxis")].copy()
    if not len(d):
        return None
    d["seg"] = d.dims.fillna("").map(_seg_only)
    d = d[d.seg.notna()]
    d["dur"] = (pd.to_datetime(d.end) - pd.to_datetime(d.start)).dt.days
    d = d[d.dur.between(330, 400)]
    if not len(d):
        return None
    ends = sorted(pd.to_datetime(d.end).unique())
    def year(e):
        x = d[pd.to_datetime(d.end) == e]
        rows = {}
        for seg, g in x.groupby("seg"):
            r = g[g.name.isin(REV)].value.max(); o = g[g.name.isin(OI)].value
            rows[seg] = dict(revenue=float(r) if pd.notna(r) else None, ebit=float(o.iloc[0]) if len(o) else None)
        return rows
    cur = year(ends[-1]); prev = year(ends[-2]) if len(ends) >= 2 else {}
    segs = []
    for k, v in cur.items():
        if not v["revenue"] or v["revenue"] <= 0 or v["ebit"] is None:
            continue
        p = prev.get(k, {}).get("revenue")
        segs.append(dict(segment=k.split(":")[-1].replace("Member", ""), revenue=v["revenue"], ebit=v["ebit"],
                         margin=v["ebit"] / v["revenue"], growth=(v["revenue"] / p - 1) if p else None,
                         other=bool(SKIP.search(k))))
    # regional segments of one business are one business: merged before the conglomerate test (KO, AMZN retail)
    geo = [s for s in segs if not s["other"] and GEO.search(s["segment"])]
    if len(geo) >= 2:
        r_ = sum(s["revenue"] for s in geo); e_ = sum(s["ebit"] for s in geo)
        segs = [s for s in segs if s not in geo] + [dict(segment="Regionen (" + "+".join(s["segment"][:12] for s in geo) + ")", revenue=r_, ebit=e_,
                                                         margin=e_ / r_, growth=None, other=False)]
    if len([s for s in segs if not s["other"]]) < 2:
        return None
    tot = sum(s["revenue"] for s in segs if not s["other"])
    for s in segs:
        s["share"] = s["revenue"] / tot if tot else None
    big = [s for s in segs if not s["other"] and s["share"] >= CONG_SHARE]
    spread = (max(s["margin"] for s in big) - min(s["margin"] for s in big)) if len(big) >= 2 else 0.0
    return dict(fy_end=str(pd.Timestamp(ends[-1]).date()), segments=segs, conglomerate=len(big) >= 2 and spread > CONG_SPREAD,
                margin_spread=spread)
