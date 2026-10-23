"""Abendlauf-Schritt: Swing-Plan (swing_levels) für den ganzen Pool -> data/swing_plans.json."""
import json, sys; sys.path.insert(0, __import__("os").environ.get("APP_ROOT", "."))
from common import CASES
from swing_levels import analyse
from lib import D
from stop_evidence import lookup
out = {}
for s in CASES:
    try:
        an = analyse(s); p = an["plan"]
        if p: out[s] = {k: (float(v) if isinstance(v, float) else v) for k, v in p.items() if k != "zone"} | {"touches": p["zone"]["touches"], "conf": p["zone"]["conf"], "asof": an["asof"], "evidence": lookup(an)}
    except Exception as e: print(s, e)
(D / "swing_plans.json").write_text(json.dumps(out)); print(len(out), "von", len(CASES))
