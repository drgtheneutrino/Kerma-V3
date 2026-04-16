"""
Kerma Unit System
=================
Units stored as 7-element dimension vectors over SI base dimensions:
    (length, mass, time, current, temperature, amount, luminosity)

Quantity = (float value in SI base, dimension vector, optional display hint)
"""

from __future__ import annotations
import math
from typing import Dict, Tuple, Optional

# ── Dimension vectors ──────────────────────────────────────────────────
DIM_LABELS = ("L", "M", "T", "I", "Θ", "N", "J")
DIMENSIONLESS = (0, 0, 0, 0, 0, 0, 0)
DimVec = Tuple[int, ...]


def dim_mul(a: DimVec, b: DimVec) -> DimVec:
    return tuple(x + y for x, y in zip(a, b))


def dim_div(a: DimVec, b: DimVec) -> DimVec:
    return tuple(x - y for x, y in zip(a, b))


def dim_pow(a: DimVec, n) -> DimVec:
    result = tuple(x * n for x in a)
    rounded = tuple(round(x) for x in result)
    if not all(abs(x - r) < 1e-9 for x, r in zip(result, rounded)):
        raise ValueError(f"Fractional dimensions not supported: {result}")
    return rounded

# Aliases for clarity in linalg module
dim_add = dim_mul       # multiplying quantities adds dimension exponents
dim_sub = dim_div       # dividing quantities subtracts dimension exponents
dim_mul_scalar = dim_pow  # raising to power n multiplies exponents by n


def dim_str(d: DimVec) -> str:
    parts = []
    for exp, label in zip(d, DIM_LABELS):
        if exp == 1:
            parts.append(label)
        elif exp != 0:
            parts.append(f"{label}^{exp}")
    return "·".join(parts) if parts else "dimensionless"


# ── Unit & Registry ────────────────────────────────────────────────────
class Unit:
    __slots__ = ("name", "symbol", "dim", "to_si")

    def __init__(self, name: str, symbol: str, dim: DimVec, to_si: float):
        self.name = name
        self.symbol = symbol
        self.dim = dim
        self.to_si = to_si

    def __repr__(self):
        return f"Unit({self.symbol})"


class UnitRegistry:
    SI_PREFIXES = {
        "Y": 1e24, "Z": 1e21, "E": 1e18, "P": 1e15, "T": 1e12,
        "G": 1e9, "M": 1e6, "k": 1e3, "h": 1e2, "da": 1e1,
        "d": 1e-1, "c": 1e-2, "m": 1e-3, "u": 1e-6, "μ": 1e-6,
        "n": 1e-9, "p": 1e-12, "f": 1e-15, "a": 1e-18,
    }

    def __init__(self):
        self._units: Dict[str, Unit] = {}
        self._register_base()
        self._register_derived()
        self._register_nuclear()
        self._register_prefixed()

    def _reg(self, name: str, symbol: str, dim: DimVec, to_si: float):
        u = Unit(name, symbol, dim, to_si)
        self._units[symbol] = u
        if name != symbol:
            self._units[name] = u

    def get(self, symbol: str) -> Optional[Unit]:
        return self._units.get(symbol)

    def __contains__(self, symbol: str) -> bool:
        return symbol in self._units

    def _register_base(self):
        self._reg("meter", "m", (1,0,0,0,0,0,0), 1.0)
        self._reg("kilogram", "kg", (0,1,0,0,0,0,0), 1.0)
        self._reg("second", "s", (0,0,1,0,0,0,0), 1.0)
        self._reg("ampere", "A", (0,0,0,1,0,0,0), 1.0)
        self._reg("kelvin", "K", (0,0,0,0,1,0,0), 1.0)
        self._reg("mole", "mol", (0,0,0,0,0,1,0), 1.0)
        self._reg("candela", "cd", (0,0,0,0,0,0,1), 1.0)
        self._reg("gram", "g", (0,1,0,0,0,0,0), 1e-3)

    def _register_derived(self):
        self._reg("newton", "N", (1,1,-2,0,0,0,0), 1.0)
        self._reg("pascal", "Pa", (-1,1,-2,0,0,0,0), 1.0)
        self._reg("joule", "J", (2,1,-2,0,0,0,0), 1.0)
        self._reg("watt", "W", (2,1,-3,0,0,0,0), 1.0)
        self._reg("hertz", "Hz", (0,0,-1,0,0,0,0), 1.0)
        self._reg("coulomb", "C", (0,0,1,1,0,0,0), 1.0)
        self._reg("volt", "V", (2,1,-3,-1,0,0,0), 1.0)
        self._reg("ohm", "Ω", (2,1,-3,-2,0,0,0), 1.0)
        self._reg("farad", "F", (-2,-1,4,2,0,0,0), 1.0)
        self._reg("weber", "Wb", (2,1,-2,-1,0,0,0), 1.0)
        self._reg("centimeter", "cm", (1,0,0,0,0,0,0), 1e-2)
        self._reg("millimeter", "mm", (1,0,0,0,0,0,0), 1e-3)
        self._reg("kilometer", "km", (1,0,0,0,0,0,0), 1e3)
        self._reg("angstrom", "Å", (1,0,0,0,0,0,0), 1e-10)
        self._reg("fermi", "fm", (1,0,0,0,0,0,0), 1e-15)
        self._reg("minute", "min", (0,0,1,0,0,0,0), 60.0)
        self._reg("hour", "hr", (0,0,1,0,0,0,0), 3600.0)
        self._reg("day", "day", (0,0,1,0,0,0,0), 86400.0)
        self._reg("year", "yr", (0,0,1,0,0,0,0), 3.15576e7)
        self._reg("microsecond", "μs_unit", (0,0,1,0,0,0,0), 1e-6)
        self._reg("nanosecond", "ns_time", (0,0,1,0,0,0,0), 1e-9)
        self._reg("liter", "L", (3,0,0,0,0,0,0), 1e-3)

    def _register_nuclear(self):
        eV = 1.602176634e-19
        self._reg("electronvolt", "eV", (2,1,-2,0,0,0,0), eV)
        self._reg("kiloelectronvolt", "keV", (2,1,-2,0,0,0,0), eV*1e3)
        self._reg("megaelectronvolt", "MeV", (2,1,-2,0,0,0,0), eV*1e6)
        self._reg("gigaelectronvolt", "GeV", (2,1,-2,0,0,0,0), eV*1e9)
        self._reg("barn", "barn", (2,0,0,0,0,0,0), 1e-28)
        self._reg("millibarn", "mb", (2,0,0,0,0,0,0), 1e-31)
        self._reg("becquerel", "Bq", (0,0,-1,0,0,0,0), 1.0)
        self._reg("curie", "Ci", (0,0,-1,0,0,0,0), 3.7e10)
        self._reg("gray_unit", "Gy", (2,0,-2,0,0,0,0), 1.0)
        self._reg("sievert", "Sv", (2,0,-2,0,0,0,0), 1.0)
        self._reg("rad_unit", "rad", (2,0,-2,0,0,0,0), 0.01)
        self._reg("rem", "rem", (2,0,-2,0,0,0,0), 0.01)
        self._reg("roentgen", "R", (0,-1,1,1,0,0,0), 2.58e-4)
        self._reg("per_cm", "cm⁻¹", (-1,0,0,0,0,0,0), 100.0)
        self._reg("per_m", "m⁻¹", (-1,0,0,0,0,0,0), 1.0)

    def _register_prefixed(self):
        prefixable = ["g","s","A","K","mol","J","W","N","Pa","Hz","V","Bq","Gy","Sv","L"]
        skip = set(self._units.keys())
        for base_sym in prefixable:
            base = self._units.get(base_sym)
            if base is None:
                continue
            for prefix, factor in self.SI_PREFIXES.items():
                new_sym = prefix + base_sym
                if new_sym in skip:
                    continue
                self._reg(new_sym, new_sym, base.dim, base.to_si * factor)


REGISTRY = UnitRegistry()


# ── Quantity ───────────────────────────────────────────────────────────
class DimensionError(Exception):
    pass


class Quantity:
    __slots__ = ("value", "dim", "_unit_hint")

    def __init__(self, value: float, dim: DimVec = DIMENSIONLESS, unit_hint: Optional[str] = None):
        self.value = value
        self.dim = dim
        self._unit_hint = unit_hint

    @classmethod
    def from_unit(cls, value: float, unit_symbol: str) -> Quantity:
        u = REGISTRY.get(unit_symbol)
        if u is None:
            raise ValueError(f"Unknown unit: {unit_symbol}")
        return cls(value * u.to_si, u.dim, unit_hint=unit_symbol)

    def _check_compat(self, other: Quantity):
        if self.dim != other.dim:
            raise DimensionError(f"Cannot combine {dim_str(self.dim)} and {dim_str(other.dim)}")

    def __add__(self, other):
        if isinstance(other, (int, float)):
            other = Quantity(float(other))
        self._check_compat(other)
        return Quantity(self.value + other.value, self.dim, self._unit_hint or other._unit_hint)

    def __radd__(self, other):
        return self.__add__(other)

    def __sub__(self, other):
        if isinstance(other, (int, float)):
            other = Quantity(float(other))
        self._check_compat(other)
        return Quantity(self.value - other.value, self.dim, self._unit_hint or other._unit_hint)

    def __rsub__(self, other):
        if isinstance(other, (int, float)):
            other = Quantity(float(other))
        other._check_compat(self)
        return Quantity(other.value - self.value, self.dim, self._unit_hint or other._unit_hint)

    def __mul__(self, other):
        if isinstance(other, (int, float)):
            return Quantity(self.value * other, self.dim, self._unit_hint)
        if isinstance(other, Quantity):
            return Quantity(self.value * other.value, dim_mul(self.dim, other.dim))
        return NotImplemented

    def __rmul__(self, other):
        if isinstance(other, (int, float)):
            return Quantity(other * self.value, self.dim, self._unit_hint)
        return NotImplemented

    def __truediv__(self, other):
        if isinstance(other, (int, float)):
            return Quantity(self.value / other, self.dim, self._unit_hint)
        if isinstance(other, Quantity):
            return Quantity(self.value / other.value, dim_div(self.dim, other.dim))
        return NotImplemented

    def __rtruediv__(self, other):
        if isinstance(other, (int, float)):
            return Quantity(other / self.value, dim_pow(self.dim, -1))
        return NotImplemented

    def __pow__(self, n):
        if isinstance(n, (int, float)):
            return Quantity(self.value ** n, dim_pow(self.dim, n))
        return NotImplemented

    def __neg__(self):
        return Quantity(-self.value, self.dim, self._unit_hint)

    def __abs__(self):
        return Quantity(abs(self.value), self.dim, self._unit_hint)

    def __eq__(self, other):
        if isinstance(other, Quantity):
            return self.dim == other.dim and math.isclose(self.value, other.value, rel_tol=1e-9)
        if isinstance(other, (int, float)) and self.dim == DIMENSIONLESS:
            return math.isclose(self.value, other, rel_tol=1e-9)
        return NotImplemented

    def __lt__(self, other):
        if isinstance(other, Quantity):
            self._check_compat(other)
            return self.value < other.value
        return NotImplemented

    def __le__(self, other):
        if isinstance(other, Quantity):
            self._check_compat(other)
            return self.value <= other.value
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, Quantity):
            self._check_compat(other)
            return self.value > other.value
        return NotImplemented

    def __ge__(self, other):
        if isinstance(other, Quantity):
            self._check_compat(other)
            return self.value >= other.value
        return NotImplemented

    def to(self, unit_symbol: str) -> Quantity:
        u = REGISTRY.get(unit_symbol)
        if u is None:
            raise ValueError(f"Unknown unit: {unit_symbol}")
        if u.dim != self.dim:
            raise DimensionError(f"Cannot convert {dim_str(self.dim)} to {unit_symbol} ({dim_str(u.dim)})")
        # Keep value in SI — just change the display hint
        return Quantity(self.value, self.dim, unit_hint=unit_symbol)

    def in_si(self) -> Quantity:
        return Quantity(self.value, self.dim)

    @property
    def is_dimensionless(self) -> bool:
        return self.dim == DIMENSIONLESS

    def _best_unit(self) -> Optional[Unit]:
        if self._unit_hint:
            u = REGISTRY.get(self._unit_hint)
            if u and u.dim == self.dim:
                return u
        best = None
        best_score = float("inf")
        seen = set()
        for sym, u in REGISTRY._units.items():
            if u.dim != self.dim or u.symbol in seen:
                continue
            seen.add(u.symbol)
            display_val = abs(self.value / u.to_si) if u.to_si != 0 else float("inf")
            if display_val == 0:
                score = 0
            elif display_val > 0:
                score = abs(math.log10(display_val) - 1)
            else:
                score = float("inf")
            if score < best_score:
                best_score = score
                best = u
        return best

    def __repr__(self):
        u = self._best_unit()
        if u:
            display_val = self.value / u.to_si
            return f"{display_val:g} {u.symbol}"
        if self.dim == DIMENSIONLESS:
            return f"{self.value:g}"
        return f"{self.value:g} [{dim_str(self.dim)}]"

    def __str__(self):
        return self.__repr__()


# ── Unit-aware math ────────────────────────────────────────────────────
def _require_dimensionless(q: Quantity, func_name: str) -> float:
    if not q.is_dimensionless:
        raise DimensionError(f"{func_name}() requires dimensionless argument, got {dim_str(q.dim)}")
    return q.value


def sqrt(q) -> Quantity:
    if isinstance(q, (int, float)):
        return Quantity(math.sqrt(q))
    return Quantity(math.sqrt(q.value), dim_pow(q.dim, 0.5))


def exp(q) -> Quantity:
    if isinstance(q, (int, float)):
        return Quantity(math.exp(q))
    return Quantity(math.exp(_require_dimensionless(q, "exp")))


def log(q) -> Quantity:
    if isinstance(q, (int, float)):
        return Quantity(math.log(q))
    return Quantity(math.log(_require_dimensionless(q, "log")))


def sin(q) -> Quantity:
    if isinstance(q, (int, float)):
        return Quantity(math.sin(q))
    return Quantity(math.sin(_require_dimensionless(q, "sin")))


def cos(q) -> Quantity:
    if isinstance(q, (int, float)):
        return Quantity(math.cos(q))
    return Quantity(math.cos(_require_dimensionless(q, "cos")))


def tan(q) -> Quantity:
    if isinstance(q, (int, float)):
        return Quantity(math.tan(q))
    return Quantity(math.tan(_require_dimensionless(q, "tan")))


def atan2(y, x) -> Quantity:
    if isinstance(y, Quantity) and isinstance(x, Quantity):
        y._check_compat(x)
        return Quantity(math.atan2(y.value, x.value))
    return Quantity(math.atan2(
        y.value if isinstance(y, Quantity) else y,
        x.value if isinstance(x, Quantity) else x,
    ))


# ── Physical constants ─────────────────────────────────────────────────
class Constants:
    c     = Quantity(299792458.0,       (1,0,-1,0,0,0,0),  "m/s")
    h     = Quantity(6.62607015e-34,    (2,1,-1,0,0,0,0),  "J·s")
    hbar  = Quantity(1.054571817e-34,   (2,1,-1,0,0,0,0),  "J·s")
    k_B   = Quantity(1.380649e-23,      (2,1,-2,0,-1,0,0), "J/K")
    N_A   = Quantity(6.02214076e23,     (0,0,0,0,0,-1,0),  "mol⁻¹")
    e     = Quantity(1.602176634e-19,   (0,0,1,1,0,0,0),   "C")
    m_e   = Quantity(9.1093837015e-31,  (0,1,0,0,0,0,0),   "kg")
    m_p   = Quantity(1.67262192369e-27, (0,1,0,0,0,0,0),   "kg")
    m_n   = Quantity(1.67492749804e-27, (0,1,0,0,0,0,0),   "kg")
    sigma = Quantity(5.670374419e-8,    (0,1,-3,0,-4,0,0),  "W·m⁻²·K⁻⁴")
    eps_0 = Quantity(8.8541878128e-12,  (-3,-1,4,2,0,0,0),  "F/m")
    mu_0  = Quantity(1.25663706212e-6,  (1,1,-2,-2,0,0,0),  "H/m")
