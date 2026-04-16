"""
Shielding Lab
=============

Multi-layer photon attenuation with ANSI/ANS-6.4.3 (Geometric-Progression)
buildup factors. Point-isotropic source geometry is assumed by default;
callers can switch to plane-parallel by ignoring 1/(4πr²).

The dose-rate formulation follows the standard point-kernel expression:

    Ḋ(μSv/h) = Σ_i ( 1.6·10⁻¹⁰ · A·f_i·E_i / (4π r²) ) · B_i(μd) · exp(-μd)
              × (μ_en/ρ)_air · 3600

where
    A     is activity in Bq
    f_i   emission yield per decay
    E_i   photon energy (MeV)
    r     distance (cm)   — here the attenuation depth d is in mean-free-paths
    (μ_en/ρ)_air  mass energy-absorption in air (cm²/g)

The implementation uses the DataBridge to look up μ/ρ, μ_en/ρ and the
G-P coefficients for each user-defined layer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from ..data.databridge import DataBridge


# MeV → J
_MEV_J = 1.602176634e-13
# kerma / fluence / gram (MeV cm²/g) → Gy conversion:
#   1 MeV/g = 1.602e-10 J/kg = 1.602e-10 Gy
_MEVG_TO_GY = 1.602176634e-10


@dataclass
class Layer:
    """A slab of shielding material."""
    material: str
    thickness_cm: float


@dataclass
class ShieldingResult:
    """Per-energy-line and aggregate dose-rate output."""
    lines: list       # list of LineResult
    total_uSv_per_hr: float
    distance_cm: float
    activity_Bq: float
    layers: List[Layer]

    def __str__(self) -> str:
        hdr = (f"Ḋ = {self.total_uSv_per_hr:.4g} µSv/h   "
               f"(A={self.activity_Bq:.3g} Bq, r={self.distance_cm:.3g} cm, "
               f"{len(self.layers)} layers)")
        parts = [hdr]
        for ln in self.lines:
            parts.append(f"  {ln.energy_MeV*1000:7.1f} keV  "
                         f"y={ln.yield_per_decay:.4f}  "
                         f"μd={ln.mu_d:.3f}  B={ln.buildup:.3f}  "
                         f"Ḋ={ln.dose_uSv_per_hr:.4g} µSv/h")
        return "\n".join(parts)


@dataclass
class LineResult:
    energy_MeV: float
    yield_per_decay: float
    mu_d: float                     # optical thickness through all layers
    buildup: float                  # aggregate buildup factor
    fluence_per_s: float            # photons/(cm²·s) at receptor (no buildup)
    dose_uSv_per_hr: float


# ======================================================================
# G-P buildup factor  B(μd) = 1 + (b-1)(K^μd - 1)/(K - 1)    if K ≠ 1
#                             1 + (b-1) μd                   if K == 1
# where K(E, μd) = c·(μd)^a + d·[tanh(μd/X_k - 2) - tanh(-2)] / [1 - tanh(-2)]
# (ANS-6.4.3-1991 / Harima et al.)
# ======================================================================
def gp_buildup_factor(mu_d: float, b: float, c: float, a: float,
                      X_k: float, d: float) -> float:
    if mu_d <= 0:
        return 1.0
    tanh_m2 = math.tanh(-2.0)
    K = (c * mu_d ** a
         + d * (math.tanh(mu_d / X_k - 2.0) - tanh_m2) / (1.0 - tanh_m2))
    if abs(K - 1.0) < 1e-9:
        return 1.0 + (b - 1.0) * mu_d
    return 1.0 + (b - 1.0) * (K ** mu_d - 1.0) / (K - 1.0)


class ShieldingLab:
    """
    High-level calculator. Workflow:

        lab = ShieldingLab(db)
        layers = [Layer("Lead", 2.0), Layer("Concrete (Ordinary)", 5.0)]
        res = lab.dose_rate("Cs-137", activity_Bq=3.7e10, distance_cm=100,
                            layers=layers)
        print(res)
    """

    def __init__(self, db: Optional[DataBridge] = None):
        self.db = db or DataBridge()

    # ------------------------------------------------------------------
    def attenuation_per_layer(self, energy_MeV: float,
                              layers: Sequence[Layer]) -> List[Tuple[float, float]]:
        """Return [(μ_i, t_i), ...] in mean-free-paths per layer."""
        out = []
        for L in layers:
            mu = self.db.get_linear_attenuation(L.material, energy_MeV)   # 1/cm
            out.append((mu, L.thickness_cm))
        return out

    def total_mu_d(self, energy_MeV: float, layers: Sequence[Layer]) -> float:
        return sum(mu * t for mu, t in self.attenuation_per_layer(energy_MeV, layers))

    def dose_rate(self,
                  source: str,
                  *,
                  activity_Bq: float,
                  distance_cm: float,
                  layers: Sequence[Layer] = (),
                  min_energy_MeV: float = 0.015) -> ShieldingResult:
        """
        Point-isotropic photon source dose-rate through stacked layers.
        Returns total µSv/h at the receptor and a per-line breakdown.
        """
        if distance_cm <= 0:
            raise ValueError("distance must be > 0")

        emissions = [e for e in self.db.get_emissions(source, radiation="G")
                     if e.energy_MeV >= min_energy_MeV]
        if not emissions:
            raise ValueError(f"No photon lines ≥ {min_energy_MeV} MeV for {source}")

        line_results: list[LineResult] = []
        total_dose_Gy_per_s_air = 0.0

        inv_r2 = 1.0 / (4.0 * math.pi * distance_cm * distance_cm)   # 1/cm²

        for em in emissions:
            # optical thickness across the stack
            mu_d = self.total_mu_d(em.energy_MeV, layers)

            # aggregate buildup factor — use "effective-layer" approximation:
            # evaluate G-P for the highest-Z material in the stack, or the
            # single material if only one layer. For multi-layer, we use
            # Broder's method: B_total ≈ B_last(μd_total).
            if layers:
                effective = _dominant_material(layers, self.db, em.energy_MeV)
                try:
                    b, c, a, X_k, d = self.db.get_gp_coefficients(effective, em.energy_MeV)
                    B = gp_buildup_factor(mu_d, b, c, a, X_k, d)
                except Exception:
                    B = 1.0
            else:
                B = 1.0

            # attenuation
            atten = math.exp(-mu_d) if mu_d < 700 else 0.0   # avoid underflow
            # photon fluence rate at receptor  φ = A·f/(4πr²)
            fluence = activity_Bq * em.yield_per_decay * inv_r2      # γ /(cm²·s)
            fluence_with_buildup = fluence * B * atten

            # (μ_en/ρ) in air  — cm²/g
            try:
                mu_en_air = self.db.get_attenuation("Air, Dry (NTP)", em.energy_MeV,
                                                     kind="mu_en_over_rho")
            except Exception:
                mu_en_air = self.db.get_attenuation("Air, Dry (NTP)", em.energy_MeV)

            # Dose rate in air  Ḋ = φ · E · (μ_en/ρ)   →   MeV/(g·s) → Gy/s
            d_air_gy_s = fluence_with_buildup * em.energy_MeV * mu_en_air * _MEVG_TO_GY
            total_dose_Gy_per_s_air += d_air_gy_s

            # convert to µSv/h (assume w_R = 1 for photons, tissue≈air)
            d_uSv_hr = d_air_gy_s * 1e6 * 3600.0
            line_results.append(LineResult(
                energy_MeV=em.energy_MeV, yield_per_decay=em.yield_per_decay,
                mu_d=mu_d, buildup=B, fluence_per_s=fluence_with_buildup,
                dose_uSv_per_hr=d_uSv_hr,
            ))

        total_uSv_hr = total_dose_Gy_per_s_air * 1e6 * 3600.0
        return ShieldingResult(
            lines=line_results, total_uSv_per_hr=total_uSv_hr,
            distance_cm=distance_cm, activity_Bq=activity_Bq,
            layers=list(layers),
        )


# --------------------------------------------------------------------
def _dominant_material(layers: Sequence[Layer], db: DataBridge,
                       energy_MeV: float) -> str:
    """Choose the layer that contributes most optical thickness — used
    to select G-P coefficients for the whole stack in Broder's approx."""
    best = (-1.0, layers[0].material)
    for L in layers:
        try:
            mu_d = db.get_linear_attenuation(L.material, energy_MeV) * L.thickness_cm
        except Exception:
            continue
        if mu_d > best[0]:
            best = (mu_d, L.material)
    return best[1]
