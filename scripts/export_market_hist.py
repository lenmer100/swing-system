"""Lange Tagesreihen der Marktkacheln (gleiche Quelle wie market.json: market data store-Store) nach data/market_hist_<KEY>.parquet."""
import json
from pathlib import Path
import duckdb, pandas as pd
SRC = Path(__import__("os").environ.get("MARKET_ROOT", ".")); OUT = Path(__file__).resolve().parents[1] / "data"
ASOF = pd.Timestamp(json.load(open(OUT / "meta.json"))["asof"]) if (OUT / "meta.json").exists() else pd.Timestamp.today()
con = duckdb.connect(str(SRC / "data_store/market.duckdb"), read_only=True)
for key, kind in [("SPY", "etf"), ("QQQ", "etf"), ("VIX", "macro"), ("EURUSD", "macro"), ("TNX", "macro"), ("GOLD", "macro"), ("BRENT", "macro")]:
    if kind == "etf": s = pd.read_parquet(SRC / "data_store/prices" / f"{key}.parquet", columns=["date", "close"])
    else: s = con.execute("select date, value as close from macro where series=? and source='yfinance' order by date", [key]).df()
    s = s.assign(date=pd.to_datetime(s.date)).dropna(); s = s[(s.date <= ASOF) & (s.date >= ASOF - pd.DateOffset(years=5, days=10))]
    s.to_parquet(OUT / f"market_hist_{key}.parquet", index=False); print(key, len(s), s.date.min().date(), s.date.max().date())
