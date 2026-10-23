"""Gemessene Wahrscheinlichkeiten der Live-Stoppregel je Gruppe (Volatilität × 200-Tage-Linie), aus data/stop_evidence.json."""
import json
from functools import lru_cache
from pathlib import Path
F = Path(__file__).parent / "data" / "stop_evidence.json"

@lru_cache(maxsize=1)
def table():
    return json.loads(F.read_text()) if F.exists() else None

def cell(atr_pct, price, sma200):
    t = table()
    if not t or sma200 is None or atr_pct is None: return None
    a, b = t["atr_terciles"]
    vol = "ruhig" if atr_pct <= a else "mittel" if atr_pct <= b else "volatil"
    return f'{vol} / {"über" if price > sma200 else "unter"} SMA200'

def lookup(an):
    t = table(); ma = (an.get("mas") or {}).get(200)
    c = cell(an.get("atr_pct"), an.get("price"), ma["v"] if ma else None)
    if not c or c not in t["cells"]: return None
    return dict(cell=c, test=t["cells"][c].get("test"), val=t["cells"][c].get("val"))
