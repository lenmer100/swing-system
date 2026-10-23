import pandas as pd, numpy as np, json
R = pd.read_parquet("studies/stop_results.parquet"); D = pd.read_parquet("studies/stop_setups_flat.parquet")
def agg(g):
    return pd.Series(dict(n=len(g), stop=g.stop_hit.mean(), ko=g.ko_hit.mean(), ziel=(g.how == "t1").mean(), win=(g.ret > 0).mean(),
                          ER=g.R.mean(), Epct=g.ret.mean(), stop_atr=g.stop_atr.median(), risk=g.risk_pct.median(), L=g.L.median(), turbo=g.turbo.mean(), tage=g.days.mean()))
f = lambda x: x.to_markdown(floatfmt=".3f")
out = {}
r0 = R[R.rule == "R0 live"]
out["overview"] = f(r0.groupby("per").apply(agg))
for gcol in ("vol", "beta_t", "sma200", "d200_b", "trend", "zone", "cell"):
    out[gcol] = f(r0[r0.per == "test"].groupby(gcol, observed=True).apply(agg))
# MAE
def mae(g):
    s = g[g.success]
    return pd.Series(dict(n=len(g), erfolg=g.success.mean(), mae_p50=s.mae_pre_atr.median(), mae_p80=s.mae_pre_atr.quantile(.8), mae_p90=s.mae_pre_atr.quantile(.9),
                          mae_pct_p80=s.mae_pre_pct.quantile(.8), mae1m_p80=g.mae1m_atr.quantile(.8), mae3m_p80=g.mae3m_atr.quantile(.8), mae6m_p80=g.mae6m_atr.quantile(.8),
                          live_stop_atr=(g.e - g.stop0).div(g.A).median()))
Dt = D[D.per == "test"]
out["mae_cell"] = f(Dt.groupby("cell").apply(mae)); out["mae_vol"] = f(Dt.groupby("vol", observed=True).apply(mae)); out["mae_trend"] = f(Dt.groupby("trend").apply(mae)); out["mae_zone"] = f(Dt.groupby("zone").apply(mae))
out["rules"] = f(R.groupby(["per", "rule"]).apply(agg))
out["rules_vol_val"] = f(R[R.per == "val"].groupby(["vol", "rule"], observed=True).apply(agg)[["n", "stop", "ko", "win", "ER", "Epct", "turbo", "L"]])
out["rules_cell_test"] = f(R[R.per == "test"].pivot_table(index="cell", columns="rule", values="R", aggfunc="mean"))
out["rules_cell_val"] = f(R[R.per == "val"].pivot_table(index="cell", columns="rule", values="R", aggfunc="mean"))
out["rules_stop_cell_val"] = f(R[R.per == "val"].pivot_table(index="cell", columns="rule", values="stop_hit", aggfunc="mean"))
# Jahres-Stabilität
R["yr"] = R.date.dt.year
out["rules_year"] = f(R.pivot_table(index="yr", columns="rule", values="R", aggfunc="mean"))
open("studies/stop_tables.json", "w").write(json.dumps(out))
for k, v in out.items(): print("##", k); print(v)
