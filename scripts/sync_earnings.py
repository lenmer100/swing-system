"""Zahlentermine nach sync_close nachziehen: cases.next_earnings aus earnings_cal (falls veraltet) und
gemeldete Quartale aus earnings_cal.last in earnings.json-Historie (Reaktion = Schluss am Tag danach ÷ Schluss am Berichtstag, falls Kurs vorhanden)."""
import json, sys
from pathlib import Path
import pandas as pd
D = Path(__file__).resolve().parents[1] / "data"; ASOF = sys.argv[1]
cases = json.loads((D / "cases.json").read_text()); cal = json.loads((D / "earnings_cal.json").read_text())["rows"]
ern = json.loads((D / "earnings.json").read_text()); n1 = n2 = 0
for s, c in cases.items():
    r = cal.get(s) or {}
    if r.get("date") and (c.get("next_earnings") or "") <= ASOF and r["date"] > ASOF: c["next_earnings"] = r["date"]; n1 += 1
    e = ern.get(s)
    if not (e and r.get("last") and r["last"] <= ASOF): continue
    h = e.setdefault("history", [])
    if h and h[0]["date"] >= r["last"]: continue
    est, rep = r.get("last_eps_est"), r.get("last_eps_rep")
    px = pd.read_parquet(D / f"pxl_{s}.parquet"); px["date"] = pd.to_datetime(px.date); px = px.set_index("date").close
    a, b = px[px.index <= r["last"]], px[px.index > r["last"]]
    h.insert(0, {"date": r["last"], "eps_est": est, "eps_rep": rep, "surprise": (rep / est - 1) if est and rep is not None else None,
                 "reaction": float(b.iloc[0] / a.iloc[-1] - 1) if len(a) and len(b) else None}); n2 += 1
(D / "cases.json").write_text(json.dumps(cases, ensure_ascii=False)); (D / "earnings.json").write_text(json.dumps(ern, ensure_ascii=False))
print("next_earnings aktualisiert", n1, "Quartale ergänzt", n2)
