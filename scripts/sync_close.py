"""Sync all of data/ to one close date (default: previous trading day). Source per symbol: market data store prices
(read-only); if that lacks the date, yfinance daily bar (demo-local patch data/eu_close_patch.parquet).
Appends the bar to data/px_*.parquet and data/pxl_*.parquet, sets cases.json price/asof/mcap_bn and meta.json asof.
Symbols without a bar for the date keep their last close and are listed (not faked)."""
import json, sys
from pathlib import Path
import pandas as pd
D = Path(__file__).resolve().parents[1] / "data"; PX = Path(__import__("os").environ.get("MARKET_STORE", "data_store") + "/prices")
DATE = pd.Timestamp(sys.argv[1] if len(sys.argv) > 1 else "2026-10-20")
cases = json.loads((D / "cases.json").read_text()); meta = json.loads((D / "meta.json").read_text())
bars, missing = {}, []
for t in cases:
    p = PX / f"{t}.parquet"
    if p.exists():
        d = pd.read_parquet(p, columns=["date", "open", "high", "low", "close", "volume"]); d["date"] = pd.to_datetime(d.date)
        r = d[d.date == DATE]
        if len(r): bars[t] = r.iloc[0].to_dict(); continue
    missing.append(t)
patch = D / "eu_close_patch.parquet"
if missing:
    import yfinance as yf
    h = yf.download(missing, start=str(DATE.date()), end=str((DATE + pd.Timedelta(days=1)).date()), interval="1d",
                    auto_adjust=False, group_by="ticker", progress=False, threads=True)
    rows = []
    for t in missing:
        try:
            x = h[t] if len(missing) > 1 else h
            x = x.dropna(subset=["Close"]); x = x[pd.to_datetime(x.index).normalize() == DATE]
            if len(x):
                r = x.iloc[0]; rows.append(dict(symbol=t, date=DATE, open=float(r.Open), high=float(r.High), low=float(r.Low), close=float(r.Close), volume=float(r.Volume)))
        except Exception:
            pass
    pd.DataFrame(rows).to_parquet(patch)
    for r in rows: bars[r["symbol"]] = {k: r[k] for k in ("date", "open", "high", "low", "close", "volume")}
still = [t for t in cases if t not in bars]
for t, b in bars.items():
    for f in (D / f"px_{t.replace('.', '_')}.parquet", D / f"pxl_{t}.parquet"):
        if not f.exists(): continue
        d = pd.read_parquet(f); d["date"] = pd.to_datetime(d.date)
        d = d[d.date < DATE]; nb = pd.DataFrame([b]); nb["date"] = pd.to_datetime(nb.date)
        d = pd.concat([d, nb[d.columns]], ignore_index=True); d["date"] = d.date.astype(f"datetime64[ms]")
        d.to_parquet(f, index=False)
    c = cases[t]; old = c.get("price")
    if old and c.get("mcap_bn"): c["mcap_bn"] = c["mcap_bn"] * b["close"] / old
    c["price"] = float(b["close"]); c["asof"] = str(DATE.date())
meta["asof"] = str(DATE.date())
(D / "cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=1)); (D / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
print("synced", len(bars), "from yfinance", len(missing) - len(still), "without bar", still)
