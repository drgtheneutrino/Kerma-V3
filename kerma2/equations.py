"""
Pre-loaded Health-Physics equations library.

Each equation is represented by an `Equation` object that carries:
  • name, short description, category
  • SymPy symbols and expression (for LaTeX rendering)
  • a callable `solve(**kwargs)` that returns a float (SI units)
  • `latex`   — compact LaTeX source for display
  • `snippet` — an insertable text block for the notebook / docx export

The library below is opinionated but covers most of the day-to-day HP needs:
activity/decay, exposure, inverse-square, attenuation, dose rate,
specific activity, half-value layers, and a couple of stat/geometry helpers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

try:
    import sympy as _sp
    _HAS_SYMPY = True
except ImportError:                                    # pragma: no cover
    _sp = None
    _HAS_SYMPY = False


# --------------------------------------------------------------------
@dataclass
class Equation:
    key: str
    name: str
    category: str
    description: str
    latex: str
    solve: Callable[..., Any]
    variables: Dict[str, str] = field(default_factory=dict)   # name → unit hint
    sympy_expr: Any = None
    snippet: str = ""

    def __repr__(self) -> str:
        return f"<Eq {self.key}: {self.name}>"


# ── Helpers ─────────────────────────────────────────────────────────
def _sym(*names):
    if _HAS_SYMPY:
        return _sp.symbols(" ".join(names), positive=True, real=True)
    return None


# ═══════════════════════════════════════════════════════════════════
# The library
# ═══════════════════════════════════════════════════════════════════
def _build_library() -> Dict[str, Equation]:
    L: Dict[str, Equation] = {}

    # ── Radioactive decay ──────────────────────────────────────────
    if _HAS_SYMPY:
        A0, lam, t, T12 = _sym("A_0", "lambda", "t", "T_{1/2}")
        expr_A   = A0 * _sp.exp(-lam * t)
        expr_lam = _sp.log(2) / T12
    else:
        expr_A = expr_lam = None

    L["activity"] = Equation(
        key="activity",
        name="Radioactive decay",
        category="Decay",
        description="Activity at time t given initial activity and λ.",
        latex=r"A(t) = A_{0}\, e^{-\lambda t}",
        solve=lambda A0, lam, t: A0 * math.exp(-lam * t),
        variables={"A0": "Bq", "lam": "1/s", "t": "s"},
        sympy_expr=expr_A,
        snippet="A(t) = A_0 * exp(-lam * t)",
    )

    L["decay_constant"] = Equation(
        key="decay_constant",
        name="Decay constant",
        category="Decay",
        description="Relation between λ and half-life.",
        latex=r"\lambda = \dfrac{\ln 2}{T_{1/2}}",
        solve=lambda T12: math.log(2.0) / T12,
        variables={"T12": "s"},
        sympy_expr=expr_lam,
        snippet="lam = ln(2) / T12",
    )

    L["half_life"] = Equation(
        key="half_life",
        name="Half-life from λ",
        category="Decay",
        description="T½ from decay constant.",
        latex=r"T_{1/2} = \dfrac{\ln 2}{\lambda}",
        solve=lambda lam: math.log(2.0) / lam,
        variables={"lam": "1/s"},
        snippet="T12 = ln(2) / lam",
    )

    L["mean_life"] = Equation(
        key="mean_life",
        name="Mean life",
        category="Decay",
        description="Mean life τ = 1/λ.",
        latex=r"\tau = \dfrac{1}{\lambda} = \dfrac{T_{1/2}}{\ln 2}",
        solve=lambda lam: 1.0 / lam,
        variables={"lam": "1/s"},
        snippet="tau = 1 / lam",
    )

    L["specific_activity"] = Equation(
        key="specific_activity",
        name="Specific activity",
        category="Decay",
        description="Activity per unit mass of a pure radionuclide.",
        latex=r"A_{s} = \dfrac{\ln 2 \cdot N_A}{T_{1/2}\,M}",
        solve=lambda T12, M_g_per_mol: math.log(2.0) * 6.02214076e23 / (T12 * M_g_per_mol),
        variables={"T12": "s", "M_g_per_mol": "g/mol"},
        snippet="A_s = ln(2) * N_A / (T12 * M)",
    )

    # ── Bateman (2-nuclide form; full chain via Kerma.decay.bateman) ──
    L["bateman_2"] = Equation(
        key="bateman_2",
        name="Bateman — two-member chain",
        category="Decay",
        description="Daughter activity when parent starts pure: A₂(t).",
        latex=(r"A_2(t) = \dfrac{\lambda_2}{\lambda_2 - \lambda_1}\,"
               r"A_{1,0}\bigl(e^{-\lambda_1 t} - e^{-\lambda_2 t}\bigr)"),
        solve=lambda A10, lam1, lam2, t: (
            lam2 / (lam2 - lam1) * A10 * (math.exp(-lam1 * t) - math.exp(-lam2 * t))
        ),
        variables={"A10": "Bq", "lam1": "1/s", "lam2": "1/s", "t": "s"},
        snippet="A2 = lam2/(lam2-lam1) * A10 * (exp(-lam1*t) - exp(-lam2*t))",
    )

    # ── Exposure / dose ────────────────────────────────────────────
    L["inverse_square"] = Equation(
        key="inverse_square",
        name="Inverse-square law",
        category="Exposure",
        description="Dose / fluence scaling with distance from a point source.",
        latex=r"\dfrac{\dot D_{2}}{\dot D_{1}} = \left(\dfrac{r_{1}}{r_{2}}\right)^{2}",
        solve=lambda D1, r1, r2: D1 * (r1 / r2) ** 2,
        variables={"D1": "any dose-rate", "r1": "cm", "r2": "cm"},
        snippet="D2 = D1 * (r1 / r2) ** 2",
    )

    L["gamma_dose_rate"] = Equation(
        key="gamma_dose_rate",
        name="Γ point-source dose rate",
        category="Exposure",
        description="Exposure rate at distance from a Ci-level γ source.",
        latex=r"\dot X = \dfrac{\Gamma \, A}{r^{2}}",
        solve=lambda gamma, A_Ci, r_m: gamma * A_Ci / (r_m ** 2),
        variables={"gamma": "R·m²/(Ci·h)", "A_Ci": "Ci", "r_m": "m"},
        snippet="X_dot = gamma * A / r**2  # R/hr",
    )

    L["photon_attenuation"] = Equation(
        key="photon_attenuation",
        name="Narrow-beam attenuation",
        category="Shielding",
        description="Exponential attenuation of a photon beam through a shield.",
        latex=r"I(x) = I_{0}\,e^{-\mu x}",
        solve=lambda I0, mu, x: I0 * math.exp(-mu * x),
        variables={"I0": "any intensity", "mu": "1/cm", "x": "cm"},
        snippet="I = I0 * exp(-mu * x)",
    )

    L["attenuation_buildup"] = Equation(
        key="attenuation_buildup",
        name="Broad-beam (with buildup)",
        category="Shielding",
        description="Buildup-corrected broad-beam attenuation.",
        latex=r"\dot D = \dot D_{0}\,B(\mu x)\,e^{-\mu x}",
        solve=lambda D0, B, mu, x: D0 * B * math.exp(-mu * x),
        variables={"D0": "dose rate", "B": "–", "mu": "1/cm", "x": "cm"},
        snippet="D = D0 * B * exp(-mu * x)",
    )

    L["hvl_from_mu"] = Equation(
        key="hvl_from_mu",
        name="Half-value layer",
        category="Shielding",
        description="HVL from the linear attenuation coefficient.",
        latex=r"\mathrm{HVL} = \dfrac{\ln 2}{\mu}",
        solve=lambda mu: math.log(2.0) / mu,
        variables={"mu": "1/cm"},
        snippet="HVL = ln(2) / mu",
    )

    L["tvl_from_mu"] = Equation(
        key="tvl_from_mu",
        name="Tenth-value layer",
        category="Shielding",
        description="TVL from μ.",
        latex=r"\mathrm{TVL} = \dfrac{\ln 10}{\mu}",
        solve=lambda mu: math.log(10.0) / mu,
        variables={"mu": "1/cm"},
        snippet="TVL = ln(10) / mu",
    )

    L["layers_for_reduction"] = Equation(
        key="layers_for_reduction",
        name="Shielding thickness for dose-rate reduction",
        category="Shielding",
        description="Required thickness x to cut dose by factor R (narrow-beam).",
        latex=r"x = \dfrac{\ln R}{\mu}",
        solve=lambda R, mu: math.log(R) / mu,
        variables={"R": "–", "mu": "1/cm"},
        snippet="x = ln(R) / mu",
    )

    L["kerma_from_fluence"] = Equation(
        key="kerma_from_fluence",
        name="Kerma from photon fluence",
        category="Dose",
        description="Energy-fluence × mass energy-transfer coefficient.",
        latex=r"K = \Phi\, E\,(\mu_{tr}/\rho)",
        solve=lambda phi, E_MeV, mu_tr_over_rho: phi * E_MeV * mu_tr_over_rho * 1.602176634e-10,
        variables={"phi": "1/cm²", "E_MeV": "MeV", "mu_tr_over_rho": "cm²/g"},
        snippet="K = phi * E * (mu_tr_over_rho)  # Gy-equivalent",
    )

    L["dose_from_fluence"] = Equation(
        key="dose_from_fluence",
        name="Absorbed dose from photon fluence",
        category="Dose",
        description="D ≈ Φ · E · (μen/ρ).",
        latex=r"D = \Phi\, E\,(\mu_{en}/\rho)",
        solve=lambda phi, E_MeV, mu_en_over_rho: phi * E_MeV * mu_en_over_rho * 1.602176634e-10,
        variables={"phi": "1/cm²", "E_MeV": "MeV", "mu_en_over_rho": "cm²/g"},
        snippet="D = phi * E * (mu_en_over_rho)",
    )

    # ── Exposure ↔ dose conversions ────────────────────────────────
    L["R_to_Gy_air"] = Equation(
        key="R_to_Gy_air",
        name="Roentgen → Gray (air)",
        category="Conversion",
        description="Free-air kerma: 1 R ≈ 8.76 mGy.",
        latex=r"K_{air}\,[\mathrm{Gy}] = 8.76\!\times\!10^{-3}\,X\,[\mathrm{R}]",
        solve=lambda X_R: X_R * 8.76e-3,
        variables={"X_R": "R"},
        snippet="K = X * 8.76e-3  # Gy in air",
    )

    L["Ci_to_Bq"] = Equation(
        key="Ci_to_Bq",
        name="Curie → Becquerel",
        category="Conversion",
        description="1 Ci = 3.7×10¹⁰ Bq.",
        latex=r"A\,[\mathrm{Bq}] = 3.7\!\times\!10^{10}\,A\,[\mathrm{Ci}]",
        solve=lambda A_Ci: A_Ci * 3.7e10,
        variables={"A_Ci": "Ci"},
        snippet="A_Bq = A_Ci * 3.7e10",
    )

    # ── Health-physics misc ────────────────────────────────────────
    L["effective_half_life"] = Equation(
        key="effective_half_life",
        name="Effective half-life",
        category="Biological",
        description="Combination of biological & physical half-lives.",
        latex=r"\dfrac{1}{T_{eff}} = \dfrac{1}{T_{p}} + \dfrac{1}{T_{b}}",
        solve=lambda T_phys, T_bio: 1.0 / (1.0 / T_phys + 1.0 / T_bio),
        variables={"T_phys": "s", "T_bio": "s"},
        snippet="T_eff = 1 / (1/T_phys + 1/T_bio)",
    )

    L["committed_dose"] = Equation(
        key="committed_dose",
        name="Committed effective dose",
        category="Biological",
        description="Committed dose from intake I (Bq) × DCF (Sv/Bq).",
        latex=r"E_{50} = I \cdot h_{E}",
        solve=lambda intake_Bq, dcf_Sv_per_Bq: intake_Bq * dcf_Sv_per_Bq,
        variables={"intake_Bq": "Bq", "dcf_Sv_per_Bq": "Sv/Bq"},
        snippet="E50 = intake * dcf",
    )

    L["working_level"] = Equation(
        key="working_level",
        name="Radon working level",
        category="Internal Dosimetry",
        description="1 WL = any combination of short-lived Rn-222 daughters that yields "
                    "1.3×10⁵ MeV of α per litre of air.",
        latex=r"1\,\mathrm{WL} = 1.3\!\times\!10^{5}\ \mathrm{MeV\,\alpha/L}",
        solve=lambda alpha_energy_MeV_per_L: alpha_energy_MeV_per_L / 1.3e5,
        variables={"alpha_energy_MeV_per_L": "MeV/L"},
        snippet="WL = alpha_energy_MeV_per_L / 1.3e5",
    )

    # ── Geometry / statistics ──────────────────────────────────────
    L["solid_angle_disk"] = Equation(
        key="solid_angle_disk",
        name="Solid angle — point to disk",
        category="Geometry",
        description="Ω for a point source to a circular detector of radius a at distance d.",
        latex=r"\Omega = 2\pi\left(1 - \dfrac{d}{\sqrt{d^{2}+a^{2}}}\right)",
        solve=lambda a, d: 2 * math.pi * (1 - d / math.sqrt(d * d + a * a)),
        variables={"a": "cm", "d": "cm"},
        snippet="Omega = 2*pi * (1 - d/sqrt(d**2 + a**2))",
    )

    L["counting_stats"] = Equation(
        key="counting_stats",
        name="Counting-statistic uncertainty",
        category="Statistics",
        description="Poisson standard error on a count N.",
        latex=r"\sigma_{N} = \sqrt{N}",
        solve=lambda N: math.sqrt(N),
        variables={"N": "counts"},
        snippet="sigma_N = sqrt(N)",
    )

    L["mda_currie"] = Equation(
        key="mda_currie",
        name="Currie MDA",
        category="Statistics",
        description="Minimum detectable activity (Currie 1968).",
        latex=r"\mathrm{MDA} = \dfrac{2.71 + 4.65\sqrt{B}}{\varepsilon\,Y\,t}",
        solve=lambda B, eps, Y, t: (2.71 + 4.65 * math.sqrt(B)) / (eps * Y * t),
        variables={"B": "background cts", "eps": "–", "Y": "–", "t": "s"},
        snippet="MDA = (2.71 + 4.65*sqrt(B)) / (eps * Y * t)",
    )

    # ── Miscellaneous ───────────────────────────────────────────────
    L["ppm_from_fraction"] = Equation(
        key="ppm_from_fraction",
        name="ppm ↔ mass fraction",
        category="Units",
        description="ppm = mass fraction × 10⁶.",
        latex=r"\mathrm{ppm} = w_{m}\cdot 10^{6}",
        solve=lambda w: w * 1e6,
        variables={"w": "mass fraction"},
        snippet="ppm = w * 1e6",
    )

    L["celsius_to_kelvin"] = Equation(
        key="celsius_to_kelvin",
        name="°C → K",
        category="Units",
        description="Absolute temperature.",
        latex=r"T_{K} = T_{C} + 273.15",
        solve=lambda C: C + 273.15,
        variables={"C": "°C"},
        snippet="T_K = T_C + 273.15",
    )

    # ══════════════════════════════════════════════════════════════
    # v3.0 additions — photon interactions, betas, neutrons, reactor
    # ══════════════════════════════════════════════════════════════
    # ── Photon interactions ───────────────────────────────────────
    _RE = 2.8179403262e-13   # classical electron radius [cm]
    _MeC2 = 0.5109989461     # electron rest energy [MeV]

    L["klein_nishina"] = Equation(
        key="klein_nishina",
        name="Klein–Nishina differential cross section",
        category="Photon Interactions",
        description="Compton scattering dσ/dΩ per electron (unpolarized).",
        latex=(r"\dfrac{d\sigma}{d\Omega} = \dfrac{r_e^2}{2}"
               r"\left(\dfrac{E'}{E}\right)^{2}"
               r"\left(\dfrac{E}{E'}+\dfrac{E'}{E}-\sin^{2}\theta\right)"),
        solve=lambda E_MeV, theta_rad: (
            (lambda a, mu: 0.5 * _RE*_RE *
             (1.0/(1.0 + a*(1.0-mu)))**2 *
             ((1.0/(1.0+a*(1.0-mu))) + (1.0+a*(1.0-mu))
              - (1.0 - mu*mu)))(E_MeV/_MeC2, math.cos(theta_rad))
        ),
        variables={"E_MeV": "MeV", "theta_rad": "rad"},
        snippet="dsigma_dOmega = (r_e**2/2)*(E'/E)**2 * (E/E' + E'/E - sin^2(theta))",
    )

    L["compton_scattered_energy"] = Equation(
        key="compton_scattered_energy",
        name="Compton scattered-photon energy",
        category="Photon Interactions",
        description="Energy of photon scattered through angle θ.",
        latex=r"E' = \dfrac{E}{1 + (E/m_e c^{2})(1 - \cos\theta)}",
        solve=lambda E_MeV, theta_rad: (
            E_MeV / (1.0 + (E_MeV / _MeC2) * (1.0 - math.cos(theta_rad)))
        ),
        variables={"E_MeV": "MeV", "theta_rad": "rad"},
        snippet="E_prime = E / (1 + (E/511keV)*(1 - cos(theta)))",
    )

    L["compton_edge"] = Equation(
        key="compton_edge",
        name="Compton edge energy",
        category="Photon Interactions",
        description="Maximum electron KE in Compton scattering (θ = π).",
        latex=r"T_{max} = \dfrac{2 E^{2}}{m_e c^{2} + 2 E}",
        solve=lambda E_MeV: 2.0 * E_MeV * E_MeV / (_MeC2 + 2.0 * E_MeV),
        variables={"E_MeV": "MeV"},
        snippet="T_max = 2*E**2 / (m_e*c**2 + 2*E)",
    )

    L["photoelectric_K"] = Equation(
        key="photoelectric_K",
        name="Photoelectric τ (Z,E) approximation",
        category="Photon Interactions",
        description="Empirical τ ∝ Z^n / E^{3.5} (n ≈ 4–5).",
        latex=r"\tau \propto \dfrac{Z^{n}}{E^{3.5}}",
        solve=lambda Z, E_MeV, n=4.5: (Z**n) / (E_MeV**3.5),
        variables={"Z": "–", "E_MeV": "MeV", "n": "–"},
        snippet="tau ≈ Z**n / E**3.5",
    )

    L["pair_threshold"] = Equation(
        key="pair_threshold",
        name="Pair-production threshold",
        category="Photon Interactions",
        description="Minimum photon energy for e⁺e⁻ pair production = 2 m_e c².",
        latex=r"E_{th} = 2 m_{e}c^{2} = 1.022\ \mathrm{MeV}",
        solve=lambda: 2.0 * _MeC2,
        variables={},
        snippet="E_threshold = 1.022  # MeV",
    )

    L["mu_linear_from_mass"] = Equation(
        key="mu_linear_from_mass",
        name="μ from μ/ρ",
        category="Shielding",
        description="Linear attenuation coefficient μ = (μ/ρ)·ρ.",
        latex=r"\mu = (\mu/\rho)\,\rho",
        solve=lambda mu_over_rho, rho: mu_over_rho * rho,
        variables={"mu_over_rho": "cm²/g", "rho": "g/cm³"},
        snippet="mu = mu_over_rho * rho",
    )

    L["mass_thickness"] = Equation(
        key="mass_thickness",
        name="Mass-thickness attenuation",
        category="Shielding",
        description="I = I₀·exp[−(μ/ρ)·ρx].",
        latex=r"I = I_{0}\,\exp\!\bigl[-(\mu/\rho)\,\rho x\bigr]",
        solve=lambda I0, mu_over_rho, rho_x: I0 * math.exp(-mu_over_rho * rho_x),
        variables={"I0": "any", "mu_over_rho": "cm²/g", "rho_x": "g/cm²"},
        snippet="I = I0 * exp(-mu_over_rho * rho*x)",
    )

    # ── Beta / bremsstrahlung ─────────────────────────────────────
    L["beta_range_katz_penfold"] = Equation(
        key="beta_range_katz_penfold",
        name="β range (Katz–Penfold)",
        category="Beta / Electrons",
        description="Maximum β range R (g/cm²) from E_max (MeV), 0.01–2.5 MeV.",
        latex=(r"R = 0.412\,E^{1.265-0.0954\ln E}"
               r"\quad(0.01\le E\le 2.5)"),
        solve=lambda E_MeV: (
            0.412 * E_MeV ** (1.265 - 0.0954 * math.log(E_MeV))
            if E_MeV <= 2.5 else 0.530 * E_MeV - 0.106
        ),
        variables={"E_MeV": "MeV"},
        snippet="R = 0.412 * E**(1.265 - 0.0954*ln(E))  # g/cm²",
    )

    L["bremsstrahlung_yield"] = Equation(
        key="bremsstrahlung_yield",
        name="Bremsstrahlung yield (thick target)",
        category="Beta / Electrons",
        description="Fraction of β energy converted to bremsstrahlung (Evans).",
        latex=r"f \approx 3.5\!\times\!10^{-4}\,Z\,E_{max}",
        solve=lambda Z, E_MeV: 3.5e-4 * Z * E_MeV,
        variables={"Z": "–", "E_MeV": "MeV"},
        snippet="f = 3.5e-4 * Z * E_max",
    )

    L["beta_stopping_power_approx"] = Equation(
        key="beta_stopping_power_approx",
        name="Electron mass collision stopping (approx.)",
        category="Beta / Electrons",
        description="Bethe–Bloch approximation for electrons in low-Z media.",
        latex=r"\dfrac{-dE}{\rho dx} \approx \dfrac{0.153\,Z}{A\beta^{2}}"
              r"\ln\!\left(\dfrac{T^{2}(T+2)}{I^{2}}\right)",
        solve=lambda T_MeV, Z, A, I_eV: (
            0.153 * Z / A / ((1 - 1/(1+T_MeV/_MeC2)**2) or 1e-12)
            * math.log((T_MeV*1e6)**2 * (T_MeV+2*_MeC2)*1e6 / (I_eV**2))
        ),
        variables={"T_MeV": "MeV", "Z": "–", "A": "–", "I_eV": "eV"},
        snippet="dE/rho_dx ≈ 0.153 * Z/A / beta**2 * ln(...)",
    )

    # ── Neutron physics ────────────────────────────────────────────
    L["neutron_activation"] = Equation(
        key="neutron_activation",
        name="Neutron activation — saturation",
        category="Neutron",
        description="Activity of target irradiated for time t_irr.",
        latex=r"A(t_{irr}) = N\,\sigma\,\phi\,\bigl(1-e^{-\lambda t_{irr}}\bigr)",
        solve=lambda N_atoms, sigma_cm2, phi, lam, t_irr: (
            N_atoms * sigma_cm2 * phi * (1 - math.exp(-lam * t_irr))
        ),
        variables={"N_atoms": "atoms", "sigma_cm2": "cm²",
                   "phi": "n/cm²·s", "lam": "1/s", "t_irr": "s"},
        snippet="A = N * sigma * phi * (1 - exp(-lam*t_irr))",
    )

    L["neutron_moderation_letharyg"] = Equation(
        key="neutron_moderation_letharyg",
        name="Neutron lethargy step",
        category="Neutron",
        description="Mean logarithmic energy decrement per collision.",
        latex=(r"\xi = 1 + \dfrac{(A-1)^{2}}{2A}"
               r"\ln\!\left(\dfrac{A-1}{A+1}\right)"),
        solve=lambda A: (1 + ((A-1)**2)/(2*A) * math.log((A-1)/(A+1))
                        if A > 1 else 1.0),
        variables={"A": "–"},
        snippet="xi = 1 + ((A-1)**2/(2A)) * ln((A-1)/(A+1))",
    )

    L["neutron_moderation_collisions"] = Equation(
        key="neutron_moderation_collisions",
        name="Collisions to thermalize",
        category="Neutron",
        description="Number of elastic collisions to slow from E1 to E2.",
        latex=r"n = \dfrac{\ln(E_{1}/E_{2})}{\xi}",
        solve=lambda E1, E2, xi: math.log(E1 / E2) / xi,
        variables={"E1": "MeV", "E2": "MeV", "xi": "–"},
        snippet="n = ln(E1/E2) / xi",
    )

    L["neutron_kerma_factor"] = Equation(
        key="neutron_kerma_factor",
        name="Neutron kerma factor",
        category="Neutron",
        description="Kerma from fluence and k-factor (pGy·cm²).",
        latex=r"K = \Phi\, k_{n}",
        solve=lambda phi, k_pGy_cm2: phi * k_pGy_cm2 * 1e-12,
        variables={"phi": "n/cm²", "k_pGy_cm2": "pGy·cm²"},
        snippet="K = phi * k_n  # Gy",
    )

    # ── Reactor kinetics ───────────────────────────────────────────
    L["reactor_reactivity"] = Equation(
        key="reactor_reactivity",
        name="Reactivity",
        category="Reactor",
        description="ρ = (k − 1)/k.",
        latex=r"\rho = \dfrac{k-1}{k}",
        solve=lambda k: (k - 1.0) / k,
        variables={"k": "–"},
        snippet="rho = (k - 1) / k",
    )

    L["reactor_inhour"] = Equation(
        key="reactor_inhour",
        name="Inhour (1-group)",
        category="Reactor",
        description="One delayed-group in-hour equation.",
        latex=(r"\rho = \dfrac{\ell \omega}{1+\ell\omega}"
               r" + \dfrac{\beta\omega}{\omega+\lambda}"),
        solve=lambda omega, ell, beta, lam: (
            ell*omega/(1+ell*omega) + beta*omega/(omega+lam)
        ),
        variables={"omega": "1/s", "ell": "s", "beta": "–", "lam": "1/s"},
        snippet="rho = l*w/(1+l*w) + beta*w/(w+lam)",
    )

    L["reactor_period"] = Equation(
        key="reactor_period",
        name="Asymptotic reactor period",
        category="Reactor",
        description="Stable period T from reactivity (prompt-jump).",
        latex=r"T \approx \dfrac{\beta-\rho}{\lambda\rho}",
        solve=lambda rho, beta, lam: (beta - rho) / (lam * rho),
        variables={"rho": "–", "beta": "–", "lam": "1/s"},
        snippet="T = (beta - rho) / (lam * rho)",
    )

    L["fission_power"] = Equation(
        key="fission_power",
        name="Fission power from rate",
        category="Reactor",
        description="P = ṅ_f · E_f · 1.602×10⁻¹³ (E_f MeV per fission).",
        latex=r"P = \dot n_{f}\cdot E_{f}",
        solve=lambda n_dot_fission, E_MeV: n_dot_fission * E_MeV * 1.602176634e-13,
        variables={"n_dot_fission": "1/s", "E_MeV": "MeV"},
        snippet="P = n_dot_fission * E_f * 1.602e-13  # W",
    )

    # ── Dose / health-physics extras ───────────────────────────────
    L["air_kerma_rate_constant"] = Equation(
        key="air_kerma_rate_constant",
        name="Air-kerma rate constant Γδ",
        category="Dose",
        description="K̇_air(d) = Γδ · A / d² for a point γ source.",
        latex=r"\dot K_{air} = \dfrac{\Gamma_{\delta}\,A}{d^{2}}",
        solve=lambda Gamma, A_Bq, d_m: Gamma * A_Bq / (d_m * d_m),
        variables={"Gamma": "µGy·m²/(GBq·h)", "A_Bq": "GBq", "d_m": "m"},
        snippet="K_dot = Gamma_delta * A / d**2",
    )

    L["equivalent_dose"] = Equation(
        key="equivalent_dose",
        name="Equivalent dose",
        category="Dose",
        description="H_T = Σ w_R · D_{T,R} (ICRP 103 radiation weights).",
        latex=r"H_{T} = \sum_{R} w_{R}\,D_{T,R}",
        solve=lambda D_Gy, w_R: D_Gy * w_R,
        variables={"D_Gy": "Gy", "w_R": "–"},
        snippet="H_T = w_R * D_T",
    )

    L["effective_dose"] = Equation(
        key="effective_dose",
        name="Effective dose",
        category="Dose",
        description="E = Σ w_T · H_T (ICRP 103 tissue weights).",
        latex=r"E = \sum_{T} w_{T}\,H_{T}",
        solve=lambda H_T, w_T: H_T * w_T,
        variables={"H_T": "Sv", "w_T": "–"},
        snippet="E = w_T * H_T",
    )

    L["dose_equivalent_Sv"] = Equation(
        key="dose_equivalent_Sv",
        name="Dose-equivalent (QF form)",
        category="Dose",
        description="Pre-1990 H = Q · D (Q replaced by w_R in ICRP 60/103).",
        latex=r"H = Q \cdot D",
        solve=lambda D_Gy, Q: D_Gy * Q,
        variables={"D_Gy": "Gy", "Q": "–"},
        snippet="H = Q * D",
    )

    # ── Skyshine / scatter shortcuts ──────────────────────────────
    L["skyshine_simple"] = Equation(
        key="skyshine_simple",
        name="NCRP-151 skyshine estimate",
        category="Shielding",
        description="Simplified skyshine dose-rate at distance d_i from the source (NCRP 151).",
        latex=r"\dot H_{s} \approx C\,\dot D_{0}\,B(d_{s})\,\dfrac{d_{i}^{-1.3}}{d_{s}^{2}}",
        solve=lambda D0, B, d_s, d_i, C=2.5e-2: (
            C * D0 * B * (d_i ** -1.3) / (d_s * d_s)
        ),
        variables={"D0": "dose rate",
                   "B": "–", "d_s": "m", "d_i": "m", "C": "–"},
        snippet="H_skyshine = C*D0*B*d_i**-1.3 / d_s**2",
    )

    # ── Internal-dosimetry and retention ──────────────────────────
    L["biological_retention_singlecomp"] = Equation(
        key="biological_retention_singlecomp",
        name="Single-compartment retention",
        category="Internal Dosimetry",
        description="Body-burden vs time after intake I at t=0.",
        latex=r"q(t) = I\,e^{-(\ln 2 / T_{eff})\,t}",
        solve=lambda I0, T_eff, t: I0 * math.exp(-math.log(2.0) * t / T_eff),
        variables={"I0": "Bq", "T_eff": "s", "t": "s"},
        snippet="q(t) = I0 * exp(-ln(2)*t/T_eff)",
    )

    L["number_atoms"] = Equation(
        key="number_atoms",
        name="Atom count from activity",
        category="Decay",
        description="N = A / λ = A · T½ / ln 2.",
        latex=r"N = A / \lambda",
        solve=lambda A_Bq, lam: A_Bq / lam,
        variables={"A_Bq": "Bq", "lam": "1/s"},
        snippet="N = A / lam",
    )

    L["mass_from_activity"] = Equation(
        key="mass_from_activity",
        name="Mass from activity",
        category="Decay",
        description="Mass (g) = A · T½ · M / (ln 2 · N_A).",
        latex=r"m = \dfrac{A\,T_{1/2}\,M}{\ln 2 \cdot N_A}",
        solve=lambda A_Bq, T12_s, M_g_per_mol: (
            A_Bq * T12_s * M_g_per_mol / (math.log(2.0) * 6.02214076e23)
        ),
        variables={"A_Bq": "Bq", "T12_s": "s", "M_g_per_mol": "g/mol"},
        snippet="m = A * T12 * M / (ln(2) * N_A)",
    )

    # ── Unit conversion extras ─────────────────────────────────────
    L["Sv_to_rem"] = Equation(
        key="Sv_to_rem",
        name="Sievert → rem",
        category="Conversion",
        description="1 Sv = 100 rem.",
        latex=r"H_{rem} = 100\,H_{Sv}",
        solve=lambda H_Sv: 100.0 * H_Sv,
        variables={"H_Sv": "Sv"},
        snippet="H_rem = 100 * H_Sv",
    )

    L["Gy_to_rad"] = Equation(
        key="Gy_to_rad",
        name="Gray → rad",
        category="Conversion",
        description="1 Gy = 100 rad.",
        latex=r"D_{rad} = 100\,D_{Gy}",
        solve=lambda D_Gy: 100.0 * D_Gy,
        variables={"D_Gy": "Gy"},
        snippet="D_rad = 100 * D_Gy",
    )

    L["eV_to_J"] = Equation(
        key="eV_to_J",
        name="eV → Joule",
        category="Conversion",
        description="1 eV = 1.602176634×10⁻¹⁹ J.",
        latex=r"E_{J} = 1.602\!\times\!10^{-19}\,E_{eV}",
        solve=lambda E_eV: E_eV * 1.602176634e-19,
        variables={"E_eV": "eV"},
        snippet="E_J = E_eV * 1.602e-19",
    )

    # ── Statistics extras (quick lookups; full module in kerma2.statistics) ─
    L["chi_squared_reduced"] = Equation(
        key="chi_squared_reduced",
        name="Reduced chi-squared",
        category="Statistics",
        description="χ²_ν = Σ (O−E)²/E ÷ (n−1).",
        latex=r"\chi^{2}_{\nu} = \dfrac{1}{\nu}\sum\dfrac{(O-E)^{2}}{E}",
        solve=lambda chi2, nu: chi2 / nu,
        variables={"chi2": "–", "nu": "–"},
        snippet="chi2_reduced = chi2 / (n-1)",
    )

    L["propagation_quadrature"] = Equation(
        key="propagation_quadrature",
        name="Quadrature uncertainty",
        category="Statistics",
        description="σ = √Σ σᵢ² for independent components.",
        latex=r"\sigma = \sqrt{\sum_{i}\sigma_{i}^{2}}",
        solve=lambda sigmas: math.sqrt(sum(s*s for s in sigmas)),
        variables={"sigmas": "list"},
        snippet="sigma = sqrt(sum(sig_i**2))",
    )

    L["counting_efficiency"] = Equation(
        key="counting_efficiency",
        name="Counting efficiency",
        category="Statistics",
        description="ε = (C − B) / (A · Y · t).",
        latex=r"\varepsilon = \dfrac{C-B}{A\,Y\,t}",
        solve=lambda C, B, A_Bq, Y, t_s: (C - B) / (A_Bq * Y * t_s),
        variables={"C": "counts", "B": "counts",
                   "A_Bq": "Bq", "Y": "–", "t_s": "s"},
        snippet="eps = (C - B) / (A * Y * t)",
    )

    L["dead_time_paralyzing"] = Equation(
        key="dead_time_paralyzing",
        name="Dead-time (paralysing)",
        category="Statistics",
        description="Observed rate for paralyzable detector: m = n·e^{−nτ}.",
        latex=r"m = n\,e^{-n\tau}",
        solve=lambda n, tau: n * math.exp(-n * tau),
        variables={"n": "cps", "tau": "s"},
        snippet="m = n * exp(-n*tau)",
    )

    L["dead_time_nonparalyzing"] = Equation(
        key="dead_time_nonparalyzing",
        name="Dead-time (non-paralysing)",
        category="Statistics",
        description="Observed rate non-paralyzable: m = n/(1+nτ).",
        latex=r"m = \dfrac{n}{1+n\tau}",
        solve=lambda n, tau: n / (1 + n * tau),
        variables={"n": "cps", "tau": "s"},
        snippet="m = n / (1 + n*tau)",
    )

    # ── Geometry extras ────────────────────────────────────────────
    L["solid_angle_rect"] = Equation(
        key="solid_angle_rect",
        name="Solid angle — rectangle on-axis",
        category="Geometry",
        description="Ω of a rectangular detector from an on-axis point source.",
        latex=(r"\Omega = 4\arctan\!\left(\dfrac{ab}{2d\sqrt{4d^{2}+a^{2}+b^{2}}}\right)"),
        solve=lambda a, b, d: 4.0 * math.atan(
            a * b / (2 * d * math.sqrt(4 * d * d + a * a + b * b))
        ),
        variables={"a": "cm", "b": "cm", "d": "cm"},
        snippet="Omega = 4*arctan(a*b / (2*d*sqrt(4*d**2 + a**2 + b**2)))",
    )

    return L


LIBRARY: Dict[str, Equation] = _build_library()


def list_equations(category: Optional[str] = None) -> List[Equation]:
    eqs = list(LIBRARY.values())
    if category:
        eqs = [e for e in eqs if e.category == category]
    return sorted(eqs, key=lambda e: (e.category, e.name))


def get(key: str) -> Equation:
    """Lookup by short key (case-insensitive)."""
    if key in LIBRARY:
        return LIBRARY[key]
    low = {k.lower(): v for k, v in LIBRARY.items()}
    if key.lower() in low:
        return low[key.lower()]
    raise KeyError(f"No equation named {key!r}; try list_equations()")


def categories() -> List[str]:
    return sorted({e.category for e in LIBRARY.values()})
