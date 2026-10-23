"""Earnings history with one consistent EPS basis.
Source of the UI statement '24 Quartale, 19 Beats': data/swing.json stocks[*].reactions, built by
scripts/export_swing.py from market data store/data_store/derived/yf_earnings/<T>.parquet (Yahoo earnings dates,
2020-10 onward). data/earnings.json (8 rows) is a different, shorter Yahoo extract.
Rule: each reported EPS is matched against EDGAR diluted GAAP EPS of the same quarter (split-adjusted).
equals_gaap if |reported - EDGAR| <= max(0.02, 2 %). Consensus estimates are street (adjusted) numbers and
Yahoo's reported EPS is meant to be on the same street basis; where a firm has no adjustments street = GAAP.
A quarter whose reported EPS equals GAAP AND misses/beats by > 50 % is treated as GAAP incl. one-off items
(gains on equity stakes, tax charges) that the consensus excludes -> basis mismatch, excluded and listed.
The beat rate is shown only if <= 25 % of quarters had to be excluded (otherwise 'Basis gemischt', hidden)."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, pandas as pd

DS = Path(__import__("os").environ.get("MARKET_STORE", "data_store") + "")
OUT = Path(__file__).resolve().parents[1] / "data" / "earnings_v3.json"
OUTLIER = 0.50


def edgar_quarterly_eps(t):
    d = pd.read_parquet(DS / f"fundamentals/{t}.parquet")
    x = d[d.key == "eps_diluted"].copy(); x["days"] = (x.end - x.start).dt.days
    x = x.sort_values("filed").drop_duplicates(["start", "end"], keep="first")
    q = x[(x.days > 80) & (x.days < 100)][["end", "val"]]
    fy = x[x.days > 350]; n9 = x[(x.days > 260) & (x.days < 285)]
    q4 = []
    for r in fy.itertuples():
        m = n9[(n9.start == r.start)]
        if len(m) and not (q.end == r.end).any():
            q4.append(dict(end=r.end, val=r.val - m.val.iloc[0]))
    q = pd.concat([q, pd.DataFrame(q4)]).sort_values("end").drop_duplicates("end")
    return q.reset_index(drop=True)


def split_factor(t, after):
    px = pd.read_parquet(DS / f"bt/prices/{t}.parquet") if (DS / f"bt/prices/{t}.parquet").exists() else None
    if px is None or "splits" not in px:
        return 1.0
    s = px[(px.splits.fillna(0) > 0) & (px.date > after)]
    return float(np.prod(s.splits)) if len(s) else 1.0


def build(t):
    e = pd.read_parquet(DS / f"derived/yf_earnings/{t}.parquet").rename(columns={"EPS Estimate": "est", "Reported EPS": "rep", "Surprise(%)": "sur"})
    e["date"] = pd.to_datetime(e.date).dt.tz_localize(None).dt.normalize()
    e = e[e.rep.notna() & e.est.notna()].sort_values("date")
    q = edgar_quarterly_eps(t)
    rows = []
    for r in e.itertuples():
        cand = q[(q.end < r.date) & (q.end >= r.date - pd.Timedelta(days=100))]
        g = None
        if len(cand):
            qe = cand.end.iloc[-1]; g = float(cand.val.iloc[-1]) / split_factor(t, qe)
        basis = None if g is None else ("GAAP" if abs(r.rep - g) <= max(0.02, 0.02 * abs(g)) else "bereinigt")
        sur = (r.rep - r.est) / abs(r.est) if r.est else None
        excl = bool(basis == "GAAP" and sur is not None and abs(sur) > OUTLIER)
        rows.append(dict(date=str(r.date.date()), eps_est=float(r.est), eps_rep=float(r.rep), eps_gaap_edgar=g, basis=basis,
                         surprise=sur, excluded_one_off=excl))
    use = [x for x in rows if x["basis"] and not x["excluded_one_off"]]
    consistent = len(rows) > 0 and (len(rows) - len(use)) / len(rows) <= 0.25
    bases = ["Konsensbasis (bereinigt, ohne Sondereffekte)"]
    beats = sum(1 for x in use if x["surprise"] > 0)
    dup = [x["date"] for a, x in zip(rows, rows[1:]) if a["eps_rep"] == x["eps_rep"]]
    return dict(rows=rows, n_total=len(rows), n_usable=len(use), basis=bases[0] if consistent else "gemischt (Beat-Rate ausgeblendet)",
                show_beat_rate=consistent and len(use) >= 8, beats=beats if consistent else None,
                beat_rate=beats / len(use) if consistent and use else None,
                excluded=[x["date"] for x in rows if x["excluded_one_off"]], equal_consecutive_rep=dup)


if __name__ == "__main__":
    ts = sys.argv[1:] or ["META", "MELI", "GOOGL", "AMZN", "NVDA"]
    if ts == ["--all"]:
        ts = sorted(json.loads((Path(__file__).resolve().parents[1] / "data" / "cases.json").read_text()))
    out = {}
    for t in ts:
        try:
            out[t] = build(t)
        except Exception as ex:
            out[t] = dict(n_total=0, n_usable=0, basis=f"keine Daten ({type(ex).__name__})", show_beat_rate=False, beats=None, beat_rate=None, rows=[])
    OUT.write_text(json.dumps(dict(note=__doc__, stocks=out), indent=1, default=float))
    for t, r in list(out.items())[:5] if len(out) > 5 else out.items():
        print(t, r["n_total"], r["n_usable"], r["basis"], r["beats"], r["beat_rate"], "excl", r["excluded"], "dup", r["equal_consecutive_rep"],
              {b: sum(1 for x in r["rows"] if x["basis"] == b) for b in ("GAAP", "bereinigt", None)})
