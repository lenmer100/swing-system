"""Zahlentermine für den ganzen Pool (Yahoo Finance über yfinance, frei): nächster Termin mit Uhrzeit
(vor/nach Börse), EPS- und Umsatz-Konsens. Schreibt data/earnings_cal.json. Läuft täglich (oder manuell)."""
import json, sys, time, datetime as dt
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pandas as pd, yfinance as yf

D = Path(__file__).resolve().parents[1] / "data"
cases = json.loads((D / "cases.json").read_text())
syms = list(cases)
today = pd.Timestamp.now(tz="America/New_York").normalize()

def one(s):
    for attempt in range(3):
        try:
            t = yf.Ticker(s); out = {"symbol": s}
            ed = t.get_earnings_dates(limit=6)
            if ed is not None and len(ed):
                past = ed[ed.index < today]
                if len(past):
                    lp = past.sort_index().iloc[-1]; out["last"] = past.index.max().strftime("%Y-%m-%d")
                    out["last_eps_est"] = None if pd.isna(lp.get("EPS Estimate")) else float(lp["EPS Estimate"])
                    out["last_eps_rep"] = None if pd.isna(lp.get("Reported EPS")) else float(lp["Reported EPS"])
                fut = ed[ed.index >= today].sort_index()
                if len(fut):
                    ts = fut.index[0]; out["date"] = ts.strftime("%Y-%m-%d")
                    loc = ts.tz_convert("America/New_York") if ts.tzinfo else ts
                    h = loc.hour + loc.minute / 60
                    out["time"] = "vor Börseneröffnung" if h < 9.5 else "nach Börsenschluss" if h >= 16 else None
                    v = fut.iloc[0].get("EPS Estimate"); out["eps_est"] = None if pd.isna(v) else float(v)
            cal = t.calendar or {}
            if cal.get("Earnings Date"):
                cd = str(cal["Earnings Date"][0])
                if "date" not in out and cd >= today.strftime("%Y-%m-%d"): out["date"] = cd
                if out.get("date") == cd:
                    for k, n in (("Earnings Average", "eps_avg"), ("Earnings Low", "eps_low"), ("Earnings High", "eps_high"),
                                 ("Revenue Average", "rev_avg"), ("Revenue Low", "rev_low"), ("Revenue High", "rev_high")):
                        v = cal.get(k); out[n] = None if v is None or pd.isna(v) else float(v)
            return out
        except Exception as e:
            time.sleep(2 + attempt * 3)
    return {"symbol": s, "error": True}

with ThreadPoolExecutor(6) as ex:
    rows = list(ex.map(one, syms))
ok = [r for r in rows if r.get("date")]
(D / "earnings_cal.json").write_text(json.dumps({"asof": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "source": "Yahoo Finance (yfinance)",
                                                 "n": len(syms), "n_dated": len(ok), "rows": {r["symbol"]: r for r in ok}}, ensure_ascii=False))
print("fertig", len(ok), "von", len(syms), "Fehler", sum(1 for r in rows if r.get("error")))
