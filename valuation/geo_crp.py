"""Country risk premium by revenue geography (mega/growth audit E): revenue facts on srt:StatementGeographicalAxis
in the latest XBRL instance; members mapped to Damodaran countries (ISO code, country name in the member) or fixed
regions (median Damodaran CRP of the region's countries - unweighted, documented). Unmapped share ('Other',
'International') gets the domicile CRP. Revenue-weighted CRP."""
from __future__ import annotations
import re
import pandas as pd
from . import xbrl_instance as X

ISO = {"US": "United States", "CA": "Canada", "MX": "Mexico", "BR": "Brazil", "AR": "Argentina", "CL": "Chile", "CO": "Colombia",
       "PE": "Peru", "GB": "United Kingdom", "DE": "Germany", "FR": "France", "IT": "Italy", "ES": "Spain", "NL": "Netherlands",
       "CH": "Switzerland", "IE": "Ireland", "BE": "Belgium", "SE": "Sweden", "NO": "Norway", "DK": "Denmark", "FI": "Finland",
       "AT": "Austria", "PL": "Poland", "RU": "Russia", "TR": "Turkey", "IL": "Israel", "SA": "Saudi Arabia", "AE": "Abu Dhabi",
       "ZA": "South Africa", "EG": "Egypt", "NG": "Nigeria", "IN": "India", "CN": "China", "HK": "Hong Kong", "TW": "Taiwan",
       "JP": "Japan", "KR": "Korea", "SG": "Singapore", "MY": "Malaysia", "TH": "Thailand", "ID": "Indonesia", "PH": "Philippines",
       "VN": "Vietnam", "AU": "Australia", "NZ": "New Zealand", "LU": "Luxembourg", "PT": "Portugal", "GR": "Greece"}
REG = {"Europe": ["Germany", "France", "United Kingdom", "Italy", "Spain", "Netherlands", "Switzerland", "Sweden", "Belgium", "Poland", "Ireland", "Austria"],
       "LatinAmerica": ["Brazil", "Mexico", "Argentina", "Chile", "Colombia", "Peru"],
       "Asia": ["China", "Japan", "India", "Korea", "Taiwan", "Singapore", "Indonesia", "Thailand", "Malaysia", "Vietnam", "Philippines"],
       "MiddleEast": ["Saudi Arabia", "Israel", "Abu Dhabi", "Turkey", "Qatar", "Kuwait"],
       "Africa": ["South Africa", "Egypt", "Nigeria", "Morocco", "Kenya"]}
REG["AsiaPacific"] = REG["Asia"] + ["Australia", "New Zealand"]
REG["EMEA"] = REG["Europe"] + REG["MiddleEast"] + REG["Africa"]
REG["Americas"] = ["Canada"] + REG["LatinAmerica"]          # US-filers' 'Americas' usually excludes the US line
PAT = [("LatinAmerica|SouthAmerica|CentralAmerica", "LatinAmerica"), ("AsiaPacific|Apac|PacificRim", "AsiaPacific"),
       ("EuropeMiddleEastAndAfrica|Emea", "EMEA"), ("Europe", "Europe"), ("MiddleEast", "MiddleEast"), ("Africa", "Africa"),
       ("Asia", "Asia"), ("Americas(?!.*North)", "Americas")]
DOMESTIC = re.compile(r"(country:US$|UnitedStates|Domestic|NorthAmerica|US[A-Z]?Member$)")
REV = ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet")


def _member_crp(mem, crp):
    m = mem.split(":")[-1]
    if mem.startswith("country:"):
        c = ISO.get(m); return (crp.get(c, None), c) if c else (None, None)
    if DOMESTIC.search(mem):
        return 0.0, "United States"
    name = re.sub(r"Member$", "", m)
    words = re.sub(r"(?<!^)(?=[A-Z])", " ", name)
    if re.search(r"Excluding|RestOf|Other", name):
        for p, r in PAT + [("SoutheastAsia", "Asia")]:
            if re.search(p, name, re.I):
                v = [crp[c] for c in REG[r] if c in crp]
                return (float(pd.Series(v).median()) if v else None), f"Region {r}"
    for c in crp:
        cc = re.sub(r"\s*\(.*\)", "", c).strip()
        if len(cc) > 3 and cc.replace(" ", "").lower() in name.lower():
            return crp[c], cc
    for p, r in PAT:
        if re.search(p, name, re.I):
            v = [crp[c] for c in REG[r] if c in crp]
            return (float(pd.Series(v).median()) if v else None), f"Region {r}"
    return None, words


def revenue_crp(t, crp, domicile_crp):
    """-> (crp, detail) or (None, reason)."""
    d = X.load(t, annual=True)
    if d is None:
        d = X.load(t)
    if d is None:
        return None, "keine XBRL-Instanz"
    r = d[d.name.str.split(":").str[1].isin(REV) & d.dims.str.match(r"^srt:StatementGeographicalAxis=[^;]+$") & d.start.notna()]
    if not len(r):
        return None, "keine Umsatzaufteilung nach Regionen"
    r = r.assign(days=(r.end - r.start).dt.days)
    key = r.groupby(["start", "end"]).size().idxmax(); r = r[(r.start == key[0]) & (r.end == key[1])]
    r = r.assign(mem=r.dims.str.split("=").str[1]).groupby("mem").value.max()
    r = r[r > 0]
    if r.sum() <= 0:
        return None, "Regionenumsatz 0"
    tot, w, parts = r.sum(), 0.0, []
    for mem, v in r.items():
        c, lab = _member_crp(mem, crp)
        if c is None:
            c, lab = domicile_crp, f"{lab} (nicht zuordenbar -> Sitz)"
        w += v / tot * c; parts.append(f"{lab} {v / tot:.0%}")
    return float(w), "; ".join(parts)
