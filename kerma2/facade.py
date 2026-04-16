"""
Kerma — high-level facade exposed at the REPL (`Kerma.xxx`, `K.xxx`)
and as the single import target for third-party scripts.

Short, memorable command names for the health-physicist:

    K.mu("Pb", 0.662)        # mu/rho for Lead at 662 keV
    K.t12("Cs-137")          # half-life  (s)
    K.lam("Cs-137")          # decay constant
    K.A(A0=1e9, t=3600, T12=K.t12("Tc-99m"))   # activity after 1 h
    K.dose(...)              # shorthand for Kerma.shielding.dose_rate
    K.gamma("Cs-137")        # specific gamma-ray constant
    K.hvl("Lead")            # half-value layer @ Cs-137
    K.eq("activity")         # look up a pre-built equation
    K.eqs("Shielding")       # list equations in a category
    K.const.c                # speed of light
"""

from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple, Union

from .constants import CONST, gamma_constant, HVL_662_keV_cm, HVL_Co60_cm
from .data.databridge import DataBridge, Emission, Material, Nuclide
from .physics.shielding import Layer, ShieldingLab, ShieldingResult
from .physics.decay import DecayChain, BatemanResult, ChainNode, solve_bateman
from .physics.dosimetry import Dosimetry
from . import equations as _eq_module


LayerSpec = Union[Layer, Tuple[str, float]]

_MATERIAL_ALIASES = {
    "Pb":  "Lead",
    "Fe":  "Iron",
    "Al":  "Aluminum",
    "W":   "Tungsten",
    "Cu":  "Copper",
    "U":   "Uranium",
    "H2O": "Water",
    "Conc": "Concrete (Ordinary)",
    "Concrete": "Concrete (Ordinary)",
    "SS":  "Steel (Stainless 304)",
    "Steel": "Steel (Stainless 304)",
    "PE":  "Polyethylene",
}


def _canon_material(name: str) -> str:
    return _MATERIAL_ALIASES.get(name, name)


def _coerce_layer(x: LayerSpec) -> Layer:
    if isinstance(x, Layer):
        return Layer(_canon_material(x.material), x.thickness_cm)
    if isinstance(x, tuple) and len(x) == 2:
        return Layer(material=_canon_material(x[0]), thickness_cm=float(x[1]))
    raise TypeError(f"Unsupported layer spec: {x!r}")


# --------------------------------------------------------------------
class _ShieldingFacade:
    def __init__(self, db: DataBridge):
        self._lab = ShieldingLab(db)

    def dose_rate(self, source: str, *, activity_Bq: float, distance_cm: float,
                  layers: Sequence[LayerSpec] = (),
                  min_energy_MeV: float = 0.015) -> ShieldingResult:
        return self._lab.dose_rate(
            source, activity_Bq=activity_Bq, distance_cm=distance_cm,
            layers=[_coerce_layer(L) for L in layers],
            min_energy_MeV=min_energy_MeV,
        )

    def mu_d(self, energy_MeV: float, layers: Sequence[LayerSpec]) -> float:
        return self._lab.total_mu_d(energy_MeV,
                                    [_coerce_layer(L) for L in layers])


class _DecayFacade:
    def __init__(self, db: DataBridge):
        self._db = db
        self._engine = DecayChain(db)

    def chain(self, parent: str, *, max_depth: int = 5) -> List[ChainNode]:
        return self._engine.build(parent, max_depth=max_depth)

    def bateman(self, parent: str, *, parent_activity_Bq: float,
                t_array_s, max_depth: int = 5) -> BatemanResult:
        ch = self._engine.build(parent, max_depth=max_depth)
        return solve_bateman(ch, parent_activity_Bq=parent_activity_Bq,
                             t_array_s=t_array_s)


# --------------------------------------------------------------------
class _Kerma:
    """Facade singleton."""
    _db: Optional[DataBridge] = None
    _shielding: Optional[_ShieldingFacade] = None
    _decay: Optional[_DecayFacade] = None
    _dosimetry: Optional[Dosimetry] = None

    @property
    def db(self) -> DataBridge:
        if self._db is None:
            self._db = DataBridge()
        return self._db

    @property
    def shielding(self) -> _ShieldingFacade:
        if self._shielding is None:
            self._shielding = _ShieldingFacade(self.db)
        return self._shielding

    @property
    def decay(self) -> _DecayFacade:
        if self._decay is None:
            self._decay = _DecayFacade(self.db)
        return self._decay

    @property
    def dosimetry(self) -> Dosimetry:
        if self._dosimetry is None:
            self._dosimetry = Dosimetry(self.db)
        return self._dosimetry

    const = CONST

    # ═══ Short commands ════════════════════════════════════════════
    def mu(self, material: str, energy_MeV: float) -> float:
        return self.db.get_attenuation(_canon_material(material), energy_MeV)

    def mu_en(self, material: str, energy_MeV: float) -> float:
        return self.db.get_attenuation(_canon_material(material), energy_MeV,
                                        kind="mu_en_over_rho")

    def mu_lin(self, material: str, energy_MeV: float) -> float:
        return self.db.get_linear_attenuation(_canon_material(material), energy_MeV)

    def t12(self, nuclide: str) -> float:
        return self.db.get_half_life(nuclide)

    def lam(self, nuclide: str) -> float:
        return self.db.get_decay_constant(nuclide)

    def A(self, *, A0: float, t: float,
          T12: Optional[float] = None,
          lam: Optional[float] = None,
          nuclide: Optional[str] = None) -> float:
        if nuclide is not None:
            lam = self.db.get_decay_constant(nuclide)
        elif T12 is not None:
            lam = math.log(2.0) / T12
        elif lam is None:
            raise ValueError("Supply T12, lam, or nuclide")
        return A0 * math.exp(-lam * t)

    def emissions(self, nuclide: str, *, radiation: Optional[str] = None):
        return self.db.get_emissions(nuclide, radiation=radiation)

    def nuclide(self, symbol: str):
        return self.db.get_nuclide(symbol)

    def branches(self, nuclide: str):
        return self.db.get_decay_chain(nuclide)

    def material(self, name: str):
        return self.db.get_material(_canon_material(name))

    def rho(self, material: str) -> float:
        m = self.db.get_material(_canon_material(material))
        if m is None:
            raise KeyError(f"Unknown material: {material}")
        return m.density_g_cm3

    def hvl(self, material: str, *, energy_MeV: float = 0.662) -> float:
        mat = _canon_material(material)
        if abs(energy_MeV - 0.662) < 1e-6 and mat in HVL_662_keV_cm:
            return HVL_662_keV_cm[mat]
        if abs(energy_MeV - 1.25) < 1e-6 and mat in HVL_Co60_cm:
            return HVL_Co60_cm[mat]
        return math.log(2.0) / self.mu_lin(mat, energy_MeV)

    def tvl(self, material: str, *, energy_MeV: float = 0.662) -> float:
        return math.log(10.0) / self.mu_lin(material, energy_MeV)

    def gamma(self, nuclide: str):
        return gamma_constant(nuclide)

    def gamma_dose(self, nuclide: str, *, activity_Ci: float, distance_m: float = 1.0) -> float:
        g = gamma_constant(nuclide)
        if g is None:
            raise KeyError(f"No tabulated gamma for {nuclide}")
        return g * activity_Ci / (distance_m ** 2)

    def dose(self, nuclide: str, *, activity_Bq: float, distance_cm: float,
             layers: Sequence[LayerSpec] = ()) -> ShieldingResult:
        return self.shielding.dose_rate(
            nuclide, activity_Bq=activity_Bq, distance_cm=distance_cm, layers=layers)

    def eq(self, key: str):
        return _eq_module.get(key)

    def eqs(self, category: Optional[str] = None):
        return _eq_module.list_equations(category)

    def eq_categories(self):
        return _eq_module.categories()

    # Long aliases (back-compat)
    def get_attenuation(self, material: str, energy_MeV: float, *,
                        kind: str = "mu_over_rho") -> float:
        return self.db.get_attenuation(_canon_material(material),
                                        energy_MeV, kind=kind)

    def half_life(self, nuclide: str) -> float:
        return self.t12(nuclide)

    def decay_constant(self, nuclide: str) -> float:
        return self.lam(nuclide)

    def list_nuclides(self) -> List[str]:
        return self.db.list_nuclides()

    def list_materials(self) -> List[str]:
        return self.db.list_materials()

    def __repr__(self) -> str:
        return "<Kerma - Health Physics facade>"


Kerma = _Kerma()
