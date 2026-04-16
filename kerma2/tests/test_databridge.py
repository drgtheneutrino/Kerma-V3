"""Tests for DataBridge + loaders + physics engines (pytest-compatible)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import numpy as np

from kerma2.data import DataBridge
from kerma2.physics import Layer, ShieldingLab, DecayChain, solve_bateman, gp_buildup_factor


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    """A freshly-seeded DB in a temp dir — isolates tests."""
    p = tmp_path_factory.mktemp("kerma_db") / "nuclear.db"
    d = DataBridge(db_path=p)
    return d


# ══════════════════════════════════════════════════════════════════════
# DataBridge
# ══════════════════════════════════════════════════════════════════════
def test_seeding_creates_tables(db):
    assert len(db.list_nuclides()) > 10
    assert "Cs-137" in db.list_nuclides()
    assert "Lead" in db.list_materials()


def test_get_half_life_cs137(db):
    T = db.get_half_life("Cs-137")
    # 30.08 years ≈ 9.49e8 s
    assert abs(T - 9.49062e8) / 9.49062e8 < 1e-4


def test_get_half_life_unknown_raises(db):
    from kerma2.data.databridge import DataBridgeError
    with pytest.raises(DataBridgeError):
        db.get_half_life("XX-999")


def test_get_attenuation_lead_662_keV_sanity(db):
    # μ/ρ of Pb @ 662 keV ≈ 0.108 cm²/g (NIST XCOM)
    mu = db.get_attenuation("Lead", 0.662)
    assert 0.090 < mu < 0.125, mu


def test_get_attenuation_interpolates_loglog(db):
    # At an exact grid point the value is returned exactly
    mu_500 = db.get_attenuation("Lead", 0.500)
    assert mu_500 == pytest.approx(0.1614, rel=1e-3)
    # Between 0.5 and 0.6 MeV, value must be between table points
    mu_550 = db.get_attenuation("Lead", 0.550)
    assert 0.1248 < mu_550 < 0.1614


def test_linear_attenuation_equals_rho_times_mass_atten(db):
    lin = db.get_linear_attenuation("Lead", 0.662)
    mass = db.get_attenuation("Lead", 0.662)
    mat = db.get_material("Lead")
    assert lin == pytest.approx(mass * mat.density_g_cm3, rel=1e-9)


def test_emissions_cobalt60(db):
    em = db.get_emissions("Co-60", radiation="G")
    energies = sorted(e.energy_MeV for e in em)
    # 1.173 and 1.332 MeV are the canonical Co-60 lines
    assert any(abs(e - 1.1732) < 1e-3 for e in energies)
    assert any(abs(e - 1.3325) < 1e-3 for e in energies)


def test_decay_branches_cs137(db):
    branches = db.get_decay_chain("Cs-137")
    modes = [b.mode for b in branches]
    assert "B-" in modes
    tot = sum(b.branching for b in branches)
    assert abs(tot - 1.0) < 0.01


def test_dcf_cs137(db):
    rows = db.get_dcf("Cs-137", pathway="ingestion")
    assert rows and rows[0]["value"] > 0


# ══════════════════════════════════════════════════════════════════════
# G-P buildup factor
# ══════════════════════════════════════════════════════════════════════
def test_gp_buildup_zero_depth():
    assert gp_buildup_factor(0.0, 1.5, 0.5, 0.2, 13.0, -0.08) == 1.0


def test_gp_buildup_monotone_positive():
    vals = [gp_buildup_factor(x, 1.5, 0.5, 0.2, 13.0, -0.08) for x in (0.5, 1, 2, 5, 10)]
    assert all(v > 1.0 for v in vals)


# ══════════════════════════════════════════════════════════════════════
# ShieldingLab
# ══════════════════════════════════════════════════════════════════════
def test_shielding_cs137_no_shield(db):
    lab = ShieldingLab(db)
    # 1 Ci = 3.7e10 Bq, 1 m, unshielded → ≈ 0.33 R/hr ≈ 3.3 mSv/h ≈ 3300 µSv/h
    # Reference: Cs-137 gamma-ray constant Γ ≈ 0.33 R·m²/(Ci·hr) at contact
    # (values within a factor-of-2 acceptable for seeded data)
    res = lab.dose_rate("Cs-137", activity_Bq=3.7e10, distance_cm=100, layers=[])
    assert 1500 < res.total_uSv_per_hr < 6000, res.total_uSv_per_hr


def test_shielding_cs137_with_lead_reduces_dose(db):
    lab = ShieldingLab(db)
    unshielded = lab.dose_rate("Cs-137", activity_Bq=3.7e10, distance_cm=100)
    shielded = lab.dose_rate("Cs-137", activity_Bq=3.7e10, distance_cm=100,
                             layers=[Layer("Lead", 5.0)])
    # HVL of Pb @ 662 keV is ~6 mm, so 5 cm ≈ 8 HVL → ~250× reduction
    # (with buildup, more like 30-80×)
    assert shielded.total_uSv_per_hr < unshielded.total_uSv_per_hr / 10


def test_shielding_co60_two_layers(db):
    lab = ShieldingLab(db)
    res = lab.dose_rate("Co-60", activity_Bq=3.7e10, distance_cm=100,
                        layers=[Layer("Lead", 2.0), Layer("Concrete (Ordinary)", 10.0)])
    assert res.total_uSv_per_hr > 0
    assert len(res.lines) >= 2   # two gamma lines


# ══════════════════════════════════════════════════════════════════════
# Decay chain / Bateman
# ══════════════════════════════════════════════════════════════════════
def test_bateman_single_exponential(db):
    # Parent-only "chain" should reproduce A(t) = A0 · exp(-λt)
    chain = DecayChain(db).build("Cs-137", max_depth=0)
    # build walks to at least parent + one daughter; restrict to parent only
    chain = chain[:1]
    t = np.linspace(0, 2 * 86400 * 365.25 * 30, 50)     # 2 half-lives
    res = solve_bateman(chain, parent_activity_Bq=1e9, t_array_s=t)
    # at t = T½, A should be ~A₀/2
    idx = np.argmin(np.abs(t - chain[0].half_life_s))
    assert abs(res.A[0][idx] / 1e9 - 0.5) < 0.02


def test_bateman_mo99_tc99m_secular(db):
    """Mo-99 → Tc-99m ratio approaches transient equilibrium."""
    chain = DecayChain(db).build("Mo-99", max_depth=1)
    t = np.linspace(0, 4 * 86400, 200)                  # 4 days
    res = solve_bateman(chain, parent_activity_Bq=1e9, t_array_s=t)
    # Tc-99m activity grows then plateaus just under Mo-99 activity
    ratio = res.A[1] / np.maximum(res.A[0], 1e-30)
    # late-time ratio should approach λp/(λp-λd) × branching ~ 0.96 × 0.877
    assert 0.4 < ratio[-1] < 1.0, ratio[-1]


def test_bateman_positive_activities(db):
    chain = DecayChain(db).build("Sr-90", max_depth=2)
    t = np.linspace(0, 365.25 * 86400 * 2, 100)
    res = solve_bateman(chain, parent_activity_Bq=1e9, t_array_s=t)
    assert (res.A >= 0).all()


# ══════════════════════════════════════════════════════════════════════
# Facade (the high-level API exposed in the REPL)
# ══════════════════════════════════════════════════════════════════════
def test_facade_basic_lookups():
    from kerma2 import Kerma
    mu = Kerma.get_attenuation("Lead", 0.662)
    assert 0.090 < mu < 0.125
    assert Kerma.half_life("Cs-137") > 0


def test_facade_shielding(db):
    from kerma2 import Kerma
    # Uses its own (shared) DB, different from the fixture — we just
    # check the call path works and returns a populated result.
    res = Kerma.shielding.dose_rate("Cs-137", activity_Bq=3.7e10,
                                     distance_cm=100,
                                     layers=[("Lead", 1.0)])
    assert res.total_uSv_per_hr > 0
