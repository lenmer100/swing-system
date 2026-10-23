import sys, math
from dataclasses import replace
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from valuation.dcf import DCFInputs, run_dcf, reverse_dcf, growth_path, margin_path, sensitivity
from valuation.forward_pe import ntm_eps, justified_pe
from valuation.capital import wacc, combine_beta
from valuation import assumptions as A


def base(**kw):
    d = dict(revenue0=100.0, margin0=0.20, margin_target=0.20, growth_y1=0.03, growth_y2=0.03, terminal_g=0.03,
             tax0=0.25, tax_marginal=0.25, sales_to_capital=2.0, roic_now=0.08, wacc0=0.08, wacc_mature=0.08,
             net_debt=0.0, shares=1.0)
    d.update(kw)
    return DCFInputs(**d)


def test_paths():
    g = growth_path(0.2, 0.1, 0.03, 10)
    assert g[0] == 0.2 and g[1] == 0.1 and math.isclose(g[-1], 0.03)
    m = margin_path(0.1, 0.3, 10, 5)
    assert math.isclose(m[4], 0.3) and math.isclose(m[-1], 0.3) and m[0] < m[1]


def test_roic_equal_wacc_growth_is_value_neutral():
    # Damodaran: if terminal ROIC = WACC, TV = NOPAT_T / WACC independent of g
    for g in (0.01, 0.03):
        r = run_dcf(base(terminal_g=g), detail=False)["terminal"]
        nopat = r["fcff"] / (1 - r["reinvestment_rate"])
        assert math.isclose(r["roic"], 0.08) and math.isclose(r["value"], nopat / 0.08, rel_tol=1e-9)


def test_net_debt_and_shares():
    a = run_dcf(base(), detail=False)
    b = run_dcf(base(net_debt=50.0, shares=2.0), detail=False)
    assert math.isclose(b["value_per_share"], (a["ev"] - 50) / 2)


def test_monotonic():
    v = lambda **k: run_dcf(base(**k), detail=False)["value_per_share"]
    assert v(margin_target=0.25) > v()
    assert v(wacc0=0.09, wacc_mature=0.09) < v()
    # growth with ROIC>WACC creates value
    assert v(growth_y1=0.15, growth_y2=0.12, roic_now=0.30, sales_to_capital=3.0) > v(roic_now=0.30, sales_to_capital=3.0)


def test_sbc_is_cost_via_margin():
    # margin input is GAAP EBIT (SBC expensed); adding SBC back would be a higher margin -> must be higher value
    assert run_dcf(base(margin0=0.25, margin_target=0.25), detail=False)["value_per_share"] > run_dcf(base(), detail=False)["value_per_share"]


def test_reverse_dcf_roundtrip():
    i = base(growth_y1=0.10, growth_y2=0.10, roic_now=0.2)
    p = run_dcf(i, detail=False)["value_per_share"]
    r = reverse_dcf(i, p)
    assert abs(r["implied_growth_y1_2"] - 0.10) < 1e-4
    assert abs(r["implied_margin_target"] - 0.20) < 1e-4


def test_sensitivity_terminal_g_capped_at_rf():
    s = sensitivity(base(terminal_g=0.03), rf=0.03)
    vals = s["wacc_x_terminal_g"]["values"]
    assert vals[2][2] == vals[2][3]  # +0.5pp would exceed rf -> capped


def test_ntm_weighting_and_normalisation():
    assert math.isclose(ntm_eps(10, 12, 6)["ntm_eps"], 11)
    n = ntm_eps(20, 15, 3, rev_g_fy1=0.2)
    assert n["normalised_fy0"] and math.isclose(n["eps_fy0_used"], 12.5)


def test_justified_pe_gordon_limit():
    j = justified_pe(ke=0.09, g1=0.03, roe=0.09, gT=0.03)
    # ROE = ke -> PE = 1/ke regardless of growth
    assert math.isclose(j["gordon_mature_pe"], 1 / 0.09, rel_tol=1e-9)
    assert math.isclose(j["justified_pe"], 1 / 0.09, rel_tol=1e-6)


def test_wacc_and_beta():
    c = wacc(0.04, 1.0, 900, 100, 50, 5, 0.25)
    assert math.isclose(c["cost_of_equity"], 0.04 + A.ERP)
    assert 0 < c["weight_debt"] < 0.11 and c["wacc"] < c["cost_of_equity"]
    assert combine_beta(None, None) == 1.0 and combine_beta(5, 5) == A.BETA_BOUNDS[1]


def test_terminal_g_never_above_rf_in_export():
    import json
    p = Path(__file__).resolve().parents[1] / "data" / "valuation_v2.json"
    if not p.exists():
        pytest.skip("export not run")
    for t, r in json.loads(p.read_text())["stocks"].items():
        if r.get("status") == "ok":
            assert r["terminal_growth"] <= r["cost_of_capital"]["rf"] + 1e-12
            if r["range"]["base"] > 0:   # negative equity values: ordering not meaningful
                assert r["range"]["pessimistic"] <= r["range"]["base"] <= r["range"]["optimistic"]
