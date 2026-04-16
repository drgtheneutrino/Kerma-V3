"""Tests for kerma2.equations — every formula must be callable and sane."""

from __future__ import annotations

import math
import inspect

import pytest

from kerma2 import equations as eqlib


def test_library_nonempty():
    assert len(eqlib.LIBRARY) >= 50


def test_categories_present():
    cats = set(eqlib.categories())
    # must include core HP + v3.0 additions
    for c in ["Decay", "Shielding", "Dose", "Statistics",
              "Photon Interactions", "Reactor", "Neutron",
              "Beta / Electrons"]:
        assert c in cats, f"missing category: {c}"


def test_every_equation_has_latex_and_snippet():
    for key, eq in eqlib.LIBRARY.items():
        assert eq.latex, f"{key} missing latex"
        assert eq.snippet, f"{key} missing snippet"


def test_every_equation_is_callable():
    for key, eq in eqlib.LIBRARY.items():
        assert callable(eq.solve), f"{key} not callable"


def test_activity_decay_formula():
    eq = eqlib.get("activity")
    assert eq.solve(A0=100, lam=math.log(2), t=1) == pytest.approx(50.0, rel=1e-6)


def test_half_life_and_lambda_inverse():
    lam = eqlib.get("decay_constant").solve(T12=600)
    T12 = eqlib.get("half_life").solve(lam=lam)
    assert T12 == pytest.approx(600.0)


def test_hvl_tvl_ratio():
    hvl = eqlib.get("hvl_from_mu").solve(mu=1.0)
    tvl = eqlib.get("tvl_from_mu").solve(mu=1.0)
    assert tvl / hvl == pytest.approx(math.log(10) / math.log(2))


def test_photon_attenuation():
    I = eqlib.get("photon_attenuation").solve(I0=100, mu=1.0, x=math.log(2))
    assert I == pytest.approx(50.0)


def test_compton_edge_matches_661_keV_formula():
    # For Cs-137's 0.662 MeV γ the Compton edge is ~0.478 MeV
    T = eqlib.get("compton_edge").solve(E_MeV=0.662)
    assert 0.47 < T < 0.48


def test_compton_scattered_180deg():
    # Backscatter at θ=π of 0.662 MeV gives 0.184 MeV (Klein–Nishina limit)
    Ep = eqlib.get("compton_scattered_energy").solve(E_MeV=0.662, theta_rad=math.pi)
    assert 0.18 < Ep < 0.19


def test_pair_threshold_constant():
    thr = eqlib.get("pair_threshold").solve()
    assert thr == pytest.approx(1.022, rel=1e-3)


def test_beta_range_katz_penfold_sanity():
    r = eqlib.get("beta_range_katz_penfold").solve(E_MeV=1.0)
    assert 0.35 < r < 0.50     # ≈0.412 at 1 MeV


def test_bremsstrahlung_scales_with_Z():
    f_Al = eqlib.get("bremsstrahlung_yield").solve(Z=13, E_MeV=1.0)
    f_Pb = eqlib.get("bremsstrahlung_yield").solve(Z=82, E_MeV=1.0)
    assert f_Pb > f_Al


def test_reactor_reactivity_roundtrip():
    rho = eqlib.get("reactor_reactivity").solve(k=1.01)
    assert rho == pytest.approx(0.01 / 1.01)


def test_neutron_lethargy_H_vs_C():
    xi_H = eqlib.get("neutron_moderation_letharyg").solve(A=1.0)
    xi_C = eqlib.get("neutron_moderation_letharyg").solve(A=12.0)
    assert xi_H > xi_C


def test_neutron_moderation_collisions():
    xi = 1.0
    n = eqlib.get("neutron_moderation_collisions").solve(
        E1=2e6, E2=0.025, xi=xi
    )
    # ln(2e6/0.025) ≈ 18.2
    assert 17 < n < 19


def test_inverse_square():
    d2 = eqlib.get("inverse_square").solve(D1=100.0, r1=100, r2=200)
    assert d2 == pytest.approx(25.0)


def test_mass_thickness_attenuation():
    I = eqlib.get("mass_thickness").solve(I0=100, mu_over_rho=0.1, rho_x=10)
    assert I == pytest.approx(100 * math.exp(-1), rel=1e-9)


def test_Sv_to_rem_and_Gy_to_rad():
    assert eqlib.get("Sv_to_rem").solve(H_Sv=1.0) == 100.0
    assert eqlib.get("Gy_to_rad").solve(D_Gy=2.0) == 200.0


def test_dead_time_paralyzing():
    m = eqlib.get("dead_time_paralyzing").solve(n=1e4, tau=1e-6)
    assert 0 < m < 1e4


def test_dead_time_nonparalyzing_limit():
    m = eqlib.get("dead_time_nonparalyzing").solve(n=1e6, tau=1e-6)
    assert m < 1e6 / 2  # saturated


def test_solid_angle_disk_zero_at_infinity():
    Omega = eqlib.get("solid_angle_disk").solve(a=1, d=1e9)
    assert Omega < 1e-15


def test_solid_angle_rect_at_small_distance():
    Omega = eqlib.get("solid_angle_rect").solve(a=10, b=10, d=0.01)
    assert 1.5 < Omega < 4*math.pi   # near 2π at very close distance


def test_get_case_insensitive():
    assert eqlib.get("activity") is eqlib.get("ACTIVITY")


def test_list_by_category():
    phots = eqlib.list_equations("Photon Interactions")
    assert len(phots) >= 4


def test_unknown_key_raises():
    with pytest.raises(KeyError):
        eqlib.get("not_a_real_eq")
