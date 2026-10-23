"""Erzeugt data/stop_evidence.json: Testperiode 2016–19, Live-Regel R0, je Zelle Volatilität (ATR%-Terzil) × Lage zur SMA200. Validierung zum Vergleich."""
import pandas as pd, json
R = pd.read_parquet("studies/stop_results.parquet"); P = json.load(open("studies/stop_params.json"))
r0 = R[R.rule == "R0 live"]
def st(g): return dict(n=int(len(g)), stop=float(g.stop_hit.mean()), t1=float((g.how == "t1").mean()), ko=float(g.ko_hit.mean()), win=float((g.ret > 0).mean()),
                       er=float(g.R.clip(-3, 5).mean()), days_med=float(g.days.median()))
cells = {}
for (per, c), g in r0.groupby(["per", "cell"]): cells.setdefault(c, {})[per] = st(g)
out = dict(rule="Stopp = min(Zone, Wendetief) − 1 ATR (struktureller Versatz), KO = Stopp − 1 ATR, Ziel 1, Horizont 126 Handelstage", period="Test 2016–2019", val_period="Validierung 2020–2021",
           atr_terciles=P["atr_terciles"], cells=cells, all={per: st(g) for per, g in r0.groupby("per")})
json.dump(out, open("data/stop_evidence.json", "w"), indent=1); print(json.dumps(out["cells"]["volatil / über SMA200"]))
