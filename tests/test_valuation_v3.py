import json, math
from pathlib import Path
import pytest
from valuation import rules_v3 as R
from valuation.engine_v3 import excess_returns, affo_model, classify

ROOT = Path(__file__).resolve().parents[1]


def test_erp_point_in_time():
    a = R.erp_asof("2026-10-19"); assert abs(a["erp"] - 0.042) < 1e-6 and abs(a["rf"] - 0.0529) < 1e-6
    b = R.erp_asof("2014-06-15"); assert b["month"].startswith("2014-06")
    with pytest.raises(ValueError):
        R.erp_asof("2007-01-01")


def test_erp_table_numeric():
    d = R.erp_table(); assert d.erp.between(0.02, 0.09).all() and d.tbond.between(0.0, 0.08).all()


def test_stage_moat_uncertainty():
    assert R.stage(0.4) == "hyper" and R.stage(0.2) == "high" and R.stage(0.05) == "mature"
    assert R.moat(0.15, 0.3) == "wide" and R.moat(0.15, 0.1) == "narrow" and R.moat(0.01, 0.5) == "none" and R.moat(None, 1) == "none"
    assert R.uncertainty(0.1) == ("niedrig", 0.2) and R.uncertainty(None)[1] == 0.5
    mos = [R.uncertainty(x)[1] for x in (0.1, 0.3, 0.5, 2)]; assert mos == sorted(mos) and min(mos) >= .2 and max(mos) <= .5


def test_excess_returns_book_when_roe_eq_ke():
    d = excess_returns(100, 0.1, 0.1, 0.05, 0.04, 0.03, 0.5); assert abs(d["equity"] - 100) < 1e-6
    assert excess_returns(100, 0.2, 0.1, 0.05, 0.04, 0.03, 0.5)["equity"] > 100


def test_affo_positive_and_monotone_in_ke():
    lo, hi = affo_model(10, 100, 0.10, .03, .03, .02)["equity"], affo_model(10, 100, 0.07, .03, .03, .02)["equity"]
    assert 0 < lo < hi


def test_reinvester_rule_drops_pe():
    cap = dict(wacc=0.09)
    c = classify("X", "Software", dict(net_income_ttm=100, fcf_ttm=30), dict(roic_median=0.3, margin_median=0.3), cap, 0.2)
    assert c["reinvester"] and c["moat"] == "wide" and c["model"] == "fcff"
    c2 = classify("X", "Software", dict(net_income_ttm=100, fcf_ttm=90), None, cap, 0.05)
    assert not c2["reinvester"] and c2["moat"] == "none" and c2["stage"] == "mature"
    assert classify("X", "Finanzen", {}, None, cap, 0.05)["model"] == "excess_returns"
    assert classify("X", "Halbleiter", {}, None, cap, 0.05)["cyclical"]


def test_output_file():
    p = ROOT / "data" / "valuation_v3.json"
    if not p.exists():
        pytest.skip("export not run")
    d = json.loads(p.read_text())
    for s in d["stocks"].values():
        if s.get("status") != "ok" or s["range"]["base"] <= 0:   # non-positive equity value: hidden in UI (fairvalue.raw)
            continue
        r = s["range"]; assert r["pessimistic"] <= r["base"] <= r["optimistic"]
        assert s["buy_zone_below"] < r["base"]


def test_earnings_basis_consistent():
    p = ROOT / "data" / "earnings_v3.json"
    if not p.exists():
        pytest.skip()
    d = json.loads(p.read_text())["stocks"]
    assert not d["AMZN"]["show_beat_rate"]
    assert d["META"]["beats"] == 19 and d["META"]["n_usable"] == 24
