"""Tests for kerma2.statistics — the v3.0 statistics toolkit."""

from __future__ import annotations

import math

import pytest

from kerma2 import statistics as st


# ── Basic descriptive summary ──────────────────────────────────────
def test_summary_basic():
    s = st.summary([10, 12, 11, 9, 13])
    assert s["n"] == 5
    assert s["mean"] == pytest.approx(11.0)
    assert s["min"] == 9
    assert s["max"] == 13
    assert s["ci95"].contains(11.0)


# ── Poisson CI ──────────────────────────────────────────────────────
def test_poisson_ci_zero_counts():
    ci = st.poisson_ci(0, level=0.95)
    assert ci.low == 0.0
    assert 3.6 < ci.high < 3.8          # classical 3.69

def test_poisson_ci_mid_counts():
    ci = st.poisson_ci(100, level=0.95)
    assert ci.contains(100)
    # exact Garwood bounds for 100 are approx (81.4, 121.6)
    assert 78 < ci.low < 85
    assert 118 < ci.high < 125


def test_poisson_test_detects_anomaly():
    res = st.poisson_test(observed=40, expected=10.0,
                          alternative="greater")
    assert res.p_value < 1e-6
    assert res.reject_null


def test_poisson_test_consistent():
    res = st.poisson_test(observed=10, expected=10.0)
    assert res.p_value > 0.5
    assert not res.reject_null


# ── Binomial CI ─────────────────────────────────────────────────────
def test_binomial_wilson():
    ci = st.binomial_ci(5, 20, level=0.95)
    assert 0.0 <= ci.low <= 0.25 <= ci.high <= 1.0


def test_binomial_clopper():
    ci = st.binomial_ci(0, 10, level=0.95, method="clopper-pearson")
    assert ci.low == 0.0
    assert 0.25 < ci.high < 0.35


# ── Currie, MDA, ISO ────────────────────────────────────────────────
def test_currie_limits_shape():
    lim = st.currie_limits(100)
    assert lim.L_C > 0
    assert lim.L_D > lim.L_C
    assert lim.L_Q > lim.L_D


def test_mda_scales_with_background():
    m1 = st.mda(10, 1)
    m2 = st.mda(40, 1)
    assert m2 > m1  # higher bkg → larger MDA


def test_iso11929_threshold():
    thr = st.iso11929_decision_threshold(100)
    assert thr > 0
    # k=1.645 · sqrt(200) ≈ 23.3
    assert 22 < thr < 25


# ── Chi-squared ─────────────────────────────────────────────────────
def test_chi2_gof_uniform():
    # draws around their mean shouldn't fail
    data = [100, 98, 102, 99, 101, 100, 103, 97, 100, 100]
    r = st.chi2_gof(data)
    assert r.p_value > 0.05
    assert not r.reject_null


def test_chi2_gof_blow_up():
    # obvious mismatch
    r = st.chi2_gof([10, 10, 10, 10, 200])
    assert r.reject_null


# ── t-tests ─────────────────────────────────────────────────────────
def test_one_sample_t_identity():
    data = [5.0, 5.1, 4.9, 5.0, 5.05]
    r = st.one_sample_t(data, mu0=5.0)
    assert r.p_value > 0.2


def test_two_sample_t_welch():
    a = [10.1, 9.9, 10.2, 10.0, 10.05]
    b = [12.1, 11.9, 12.0, 11.95, 12.1]
    r = st.two_sample_t(a, b, equal_var=False)
    assert r.reject_null


def test_paired_t_shape():
    before = [100, 102, 98, 105, 99]
    after  = [104, 105, 101, 108, 103]
    r = st.paired_t(before, after)
    assert isinstance(r.p_value, float)


def test_mean_ci_matches_formula():
    # 95 % CI of a known sample ≈ mean ± t·s/√n
    data = [2.0, 2.5, 3.0, 2.8, 2.2]
    ci = st.mean_ci(data)
    assert ci.low < sum(data)/len(data) < ci.high


# ── Propagation of uncertainty ──────────────────────────────────────
def test_combine_quadrature():
    assert st.combine_uncertainty(3, 4) == pytest.approx(5.0)


def test_combine_linear():
    assert st.combine_uncertainty(1, 2, 3, method="linear") == 6.0


def test_propagate_ratio():
    r, u = st.propagate_ratio(100, 5, 10, 0.5)
    assert r == pytest.approx(10.0)
    # dimensional: relative σ ≈ √(.05² + .05²) → u ≈ .71
    assert 0.65 < u < 0.75


def test_propagate_product_relative():
    u = st.propagate_product([0.01, 0.02, 0.02])
    assert 0.028 < u < 0.031


# ── Control limits ──────────────────────────────────────────────────
def test_shewhart():
    d = [100, 101, 99, 100, 102, 98, 100, 101]
    L = st.shewhart_limits(d)
    assert L.action_lo < L.warning_lo < L.centre < L.warning_hi < L.action_hi


def test_poisson_limits():
    L = st.poisson_limits(100)
    assert L.warning_lo == pytest.approx(80.0)
    assert L.action_hi == pytest.approx(130.0)


# ── Linear fit ──────────────────────────────────────────────────────
def test_linear_fit_exact():
    x = [0, 1, 2, 3, 4]
    y = [1, 3, 5, 7, 9]
    fit = st.linear_fit(x, y)
    assert fit.slope == pytest.approx(2.0)
    assert fit.intercept == pytest.approx(1.0)
    assert fit.r_squared == pytest.approx(1.0)
    assert fit.predict(10) == pytest.approx(21.0)
    assert fit.inverse(21) == pytest.approx(10.0)


def test_linear_fit_noisy():
    x = list(range(10))
    y = [2*i + 1 + (0.1 if i % 2 else -0.1) for i in x]
    fit = st.linear_fit(x, y)
    assert 1.95 < fit.slope < 2.05
    assert fit.r_squared > 0.99


# ── Bayes factor ────────────────────────────────────────────────────
def test_bayes_factor_monotone():
    b_low  = st.bayes_factor_source(gross=5, background=100)
    b_high = st.bayes_factor_source(gross=200, background=100)
    assert b_high > b_low


# ── Error conditions ────────────────────────────────────────────────
def test_poisson_ci_negative_counts_raises():
    with pytest.raises(ValueError):
        st.poisson_ci(-1)


def test_binomial_bad_inputs():
    with pytest.raises(ValueError):
        st.binomial_ci(11, 10)


def test_t_requires_two_samples():
    with pytest.raises(ValueError):
        st.mean_ci([5.0])
