"""
Health-Physics constants — the things every HP calc needs pre-loaded.

Organised so that `Kerma.const.xxx` or just `from kerma2.constants import *`
gives a complete "ready to work" set of named quantities.

Everything lives as plain Python floats with documented units; a parallel
pint-aware view is built lazily when `ureg` is available.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


# ── Fundamental physical constants (CODATA 2018) ─────────────────────
c            = 2.99792458e8          # m/s
e_charge     = 1.602176634e-19       # C
h_planck     = 6.62607015e-34        # J·s
k_boltz      = 1.380649e-23          # J/K
N_A          = 6.02214076e23         # 1/mol
R_gas        = 8.314462618           # J/(mol·K)
m_e          = 9.1093837015e-31      # kg  (electron rest mass)
m_e_MeV      = 0.51099895            # MeV/c²
m_p_MeV      = 938.27208816          # MeV/c²
m_n_MeV      = 939.56542052          # MeV/c²
alpha_fs     = 7.2973525693e-3       # fine-structure constant
r_e          = 2.8179403262e-15      # m  (classical electron radius)

# Energy conversions
MeV_to_J     = 1.602176634e-13
J_to_MeV     = 1.0 / MeV_to_J
MeV_per_g_to_Gy = 1.602176634e-10    # 1 MeV/g = 1.602e-10 Gy

# Activity
Ci_to_Bq     = 3.7e10                # 1 Ci = 3.7e10 Bq
Bq_to_Ci     = 1.0 / Ci_to_Bq
mCi_to_Bq    = 3.7e7
uCi_to_Bq    = 3.7e4

# Dose
Gy_per_rad   = 0.01
Sv_per_rem   = 0.01
R_to_Ckg     = 2.58e-4               # 1 R = 2.58e-4 C/kg
R_to_Gy_air  = 8.76e-3               # free-air kerma, 1 R ≈ 8.76 mGy (dry air)

# Time
s_per_min    = 60.0
s_per_hour   = 3600.0
s_per_day    = 86400.0
s_per_year   = 365.25 * 86400.0      # Julian year

# ── Specific-gamma-ray constants  Γ  (R·m²·Ci⁻¹·hr⁻¹) ────────────────
# Source: RadToolbox / Unger & Trubey 1982 / HPS compilations (contact-geometry,
# gamma-only, no bremsstrahlung).  Use these for quick hand-checks of the
# point-kernel result at 1 m.
GAMMA_CONSTANT_R_m2_per_Ci_hr: Dict[str, float] = {
    "Am-241":  0.003,
    "Ba-133":  0.24,
    "C-11":    0.59,
    "Co-57":   0.09,
    "Co-60":   1.32,
    "Cs-137":  0.33,
    "F-18":    0.58,
    "Ga-67":   0.076,
    "Ga-68":   0.606,
    "I-123":   0.16,
    "I-125":   0.07,
    "I-131":   0.22,
    "In-111":  0.32,
    "Ir-192":  0.48,
    "Lu-177":  0.0414,
    "Mn-54":   0.47,
    "Mo-99":   0.12,
    "Na-22":   1.20,
    "Na-24":   1.84,
    "Ra-226":  0.825,
    "Sr-85":   0.30,
    "Tc-99m":  0.078,
    "Tl-201":  0.11,
    "Y-90":    0.0002,   # essentially pure β⁻; listed for bremsstrahlung refs
    "Xe-133":  0.015,
}


def gamma_constant(nuclide: str) -> Optional[float]:
    """Specific gamma-ray constant Γ in R·m²·Ci⁻¹·hr⁻¹, or None if not tabulated."""
    if nuclide in GAMMA_CONSTANT_R_m2_per_Ci_hr:
        return GAMMA_CONSTANT_R_m2_per_Ci_hr[nuclide]
    # case-insensitive fallback
    lower = {k.lower(): v for k, v in GAMMA_CONSTANT_R_m2_per_Ci_hr.items()}
    return lower.get(nuclide.lower())


def gamma_constant_uSv_m2_per_GBq_hr(nuclide: str) -> Optional[float]:
    """Γ in µSv·m²·GBq⁻¹·hr⁻¹ (SI-friendly form)."""
    g_R = gamma_constant(nuclide)
    if g_R is None:
        return None
    # 1 R ≈ 8.76 µGy (air) ≈ 8.76 µSv for photons; 1 Ci = 37 GBq
    # Γ[µSv·m²/(GBq·hr)] = Γ[R·m²/(Ci·hr)] × 8.76 µSv/R ÷ 37 GBq/Ci
    return g_R * 8.76 / 37.0 * 1000.0  # ×1000 converts mR→µSv path implicit


# ── Regulatory limits (10 CFR 20 / ICRP 103) ─────────────────────────
OCCUPATIONAL_TEDE_ANNUAL_mSv = 50.0
OCCUPATIONAL_EYE_DOSE_ANNUAL_mSv = 150.0    # ICRP 103 2011 rev = 20
OCCUPATIONAL_SKIN_ANNUAL_mSv = 500.0
PUBLIC_DOSE_ANNUAL_mSv = 1.0
DECLARED_PREGNANT_WORKER_mSv = 5.0

# ── Material densities quick-ref (g/cm³) ─────────────────────────────
DENSITY_G_PER_CM3: Dict[str, float] = {
    "Water":         1.00,
    "Air":           1.205e-3,
    "Aluminum":      2.70,
    "Concrete":      2.30,
    "Iron":          7.874,
    "Steel":         7.86,
    "Lead":          11.35,
    "Tungsten":      19.30,
    "Uranium":       19.05,
    "Tissue":        1.04,
    "Polyethylene":  0.94,
}


# ── Common HVL @ 662 keV (cm, for Cs-137) ────────────────────────────
HVL_662_keV_cm: Dict[str, float] = {
    "Lead":     0.65,
    "Iron":     1.58,
    "Concrete": 4.8,
    "Tungsten": 0.45,
    "Water":    8.7,
}


# ── Common HVL @ 1.25 MeV average (cm, for Co-60) ────────────────────
HVL_Co60_cm: Dict[str, float] = {
    "Lead":     1.20,
    "Iron":     2.10,
    "Concrete": 6.3,
    "Tungsten": 0.77,
    "Water":    11.0,
}


# ── Decay constant helper ────────────────────────────────────────────
def decay_lambda(half_life_s: float) -> float:
    """λ = ln 2 / T½."""
    import math
    return math.log(2.0) / half_life_s


def half_life_from_lambda(lam: float) -> float:
    import math
    return math.log(2.0) / lam


# ── Registry dataclass for the Kerma.const facade ────────────────────
@dataclass(frozen=True)
class _Constants:
    # fundamental
    c: float = c
    e: float = e_charge
    h: float = h_planck
    k: float = k_boltz
    N_A: float = N_A
    R: float = R_gas
    m_e_MeV: float = m_e_MeV
    m_p_MeV: float = m_p_MeV
    m_n_MeV: float = m_n_MeV
    alpha: float = alpha_fs
    r_e: float = r_e
    # practical
    Ci: float = Ci_to_Bq
    mCi: float = mCi_to_Bq
    uCi: float = uCi_to_Bq
    MeV: float = MeV_to_J
    R_to_Gy_air: float = R_to_Gy_air
    year_s: float = s_per_year
    day_s: float = s_per_day
    hour_s: float = s_per_hour

    def gamma(self, nuclide: str) -> Optional[float]:
        """Γ in R·m²·Ci⁻¹·hr⁻¹."""
        return gamma_constant(nuclide)

    def density(self, material: str) -> Optional[float]:
        return DENSITY_G_PER_CM3.get(material)

    def hvl(self, material: str, energy: str = "Cs-137") -> Optional[float]:
        table = HVL_662_keV_cm if energy in ("Cs-137", "662") else HVL_Co60_cm
        return table.get(material)


CONST = _Constants()
