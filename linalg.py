"""
Kerma Vec / Mat
===============
Unit-aware vector and matrix types backed by numpy.

All values stored in SI internally, just like Quantity.
Dimensions propagate through arithmetic:
  - Vec(m/s) + Vec(m/s) → Vec(m/s)
  - Vec(m) * Scalar(s⁻¹) → Vec(m/s)
  - dot(Vec(N), Vec(m)) → Quantity(J)
  - Mat @ Vec propagates dimensions via multiplication rules
"""

from __future__ import annotations
import math
import numpy as np
from typing import Optional, Union

from units import Quantity, REGISTRY, DimensionError, DIMENSIONLESS, dim_add, dim_sub, dim_mul_scalar

DimVec = tuple


class Vec:
    """
    A unit-aware vector. Stores values in SI internally.

    Usage:
        v = Vec([1, 2, 3], dim=(1,0,0,0,0,0,0), unit_hint='m')
        v = Vec.from_quantities([Quantity(1, ...), Quantity(2, ...), ...])
    """
    __slots__ = ('_data', 'dim', '_unit_hint')

    def __init__(self, data, dim: DimVec = DIMENSIONLESS, unit_hint: str = None):
        if isinstance(data, np.ndarray):
            self._data = data.astype(float)
        else:
            self._data = np.array(data, dtype=float)
        self.dim = dim
        self._unit_hint = unit_hint

    @staticmethod
    def from_quantities(quantities: list[Quantity]) -> Vec:
        """Build a Vec from a list of Quantities, checking dimension compatibility."""
        if not quantities:
            return Vec(np.array([]), DIMENSIONLESS)
        dim = quantities[0].dim
        for i, q in enumerate(quantities[1:], 1):
            if q.dim != dim:
                raise DimensionError(
                    f"Vec element {i} has dim {q.dim}, expected {dim}")
        values = np.array([q.value for q in quantities])
        return Vec(values, dim, quantities[0]._unit_hint)

    @property
    def size(self) -> int:
        return len(self._data)

    @property
    def shape(self) -> tuple:
        return self._data.shape

    def __len__(self) -> int:
        return len(self._data)

    # ── Element access ───────────────────────────────────────────────────

    def __getitem__(self, idx) -> Quantity:
        if isinstance(idx, Quantity):
            idx = int(idx.value)
        return Quantity(self._data[idx], self.dim, self._unit_hint)

    def __setitem__(self, idx, value):
        if isinstance(idx, Quantity):
            idx = int(idx.value)
        if isinstance(value, Quantity):
            if value.dim != self.dim:
                raise DimensionError(f"Cannot assign {value.dim} to Vec with dim {self.dim}")
            self._data[idx] = value.value
        else:
            self._data[idx] = float(value)

    # ── Arithmetic ───────────────────────────────────────────────────────

    def __add__(self, other):
        if isinstance(other, Vec):
            if self.dim != other.dim:
                raise DimensionError(f"Cannot add Vec({self.dim}) and Vec({other.dim})")
            return Vec(self._data + other._data, self.dim, self._unit_hint)
        return NotImplemented

    def __sub__(self, other):
        if isinstance(other, Vec):
            if self.dim != other.dim:
                raise DimensionError(f"Cannot subtract Vec({other.dim}) from Vec({self.dim})")
            return Vec(self._data - other._data, self.dim, self._unit_hint)
        return NotImplemented

    def __mul__(self, other):
        if isinstance(other, Quantity):
            new_dim = dim_add(self.dim, other.dim)
            return Vec(self._data * other.value, new_dim)
        if isinstance(other, (int, float)):
            return Vec(self._data * other, self.dim, self._unit_hint)
        return NotImplemented

    def __rmul__(self, other):
        return self.__mul__(other)

    def __truediv__(self, other):
        if isinstance(other, Quantity):
            new_dim = dim_sub(self.dim, other.dim)
            return Vec(self._data / other.value, new_dim)
        if isinstance(other, (int, float)):
            return Vec(self._data / other, self.dim, self._unit_hint)
        return NotImplemented

    def __neg__(self):
        return Vec(-self._data, self.dim, self._unit_hint)

    def __pow__(self, n):
        if isinstance(n, Quantity):
            if n.dim != DIMENSIONLESS:
                raise DimensionError("Exponent must be dimensionless")
            n = n.value
        new_dim = dim_mul_scalar(self.dim, n)
        return Vec(self._data ** n, new_dim)

    # ── Vector operations ────────────────────────────────────────────────

    def dot(self, other: Vec) -> Quantity:
        """Dot product: result has combined dimensions."""
        if not isinstance(other, Vec):
            raise TypeError(f"dot requires Vec, got {type(other).__name__}")
        if self.size != other.size:
            raise ValueError(f"Vec sizes don't match: {self.size} vs {other.size}")
        new_dim = dim_add(self.dim, other.dim)
        return Quantity(float(np.dot(self._data, other._data)), new_dim)

    def cross(self, other: Vec) -> Vec:
        """Cross product (3D only): result has combined dimensions."""
        if not isinstance(other, Vec):
            raise TypeError(f"cross requires Vec, got {type(other).__name__}")
        if self.size != 3 or other.size != 3:
            raise ValueError("Cross product requires 3D vectors")
        new_dim = dim_add(self.dim, other.dim)
        return Vec(np.cross(self._data, other._data), new_dim)

    def norm(self) -> Quantity:
        """Euclidean norm: result has same dimensions as elements."""
        return Quantity(float(np.linalg.norm(self._data)), self.dim, self._unit_hint)

    def normalized(self) -> Vec:
        """Unit vector (dimensionless)."""
        n = np.linalg.norm(self._data)
        if n == 0:
            raise ValueError("Cannot normalize zero vector")
        return Vec(self._data / n, DIMENSIONLESS)

    # ── Comparison ───────────────────────────────────────────────────────

    def __eq__(self, other):
        if isinstance(other, Vec):
            return self.dim == other.dim and np.allclose(self._data, other._data)
        return NotImplemented

    # ── Display ──────────────────────────────────────────────────────────

    def __repr__(self):
        unit = self._best_unit_str()
        vals = ', '.join(f'{v:g}' for v in self._display_values())
        if unit:
            return f"[{vals}] {unit}"
        return f"[{vals}]"

    def _display_values(self) -> np.ndarray:
        if self._unit_hint:
            u = REGISTRY.get(self._unit_hint)
            if u and u.dim == self.dim:
                return self._data / u.to_si
        # Try to find a good unit
        if self.dim != DIMENSIONLESS:
            best = self._find_best_unit()
            if best:
                return self._data / best.to_si
        return self._data

    def _best_unit_str(self) -> str:
        if self._unit_hint:
            u = REGISTRY.get(self._unit_hint)
            if u and u.dim == self.dim:
                return u.symbol
        if self.dim != DIMENSIONLESS:
            best = self._find_best_unit()
            if best:
                return best.symbol
        return ""

    def _find_best_unit(self):
        max_val = float(np.max(np.abs(self._data))) if self._data.size > 0 else 0
        if max_val == 0:
            return None
        best = None
        best_score = float('inf')
        seen = set()
        for sym, u in REGISTRY._units.items():
            if u.dim != self.dim or u.symbol in seen:
                continue
            seen.add(u.symbol)
            disp = abs(max_val / u.to_si) if u.to_si != 0 else float('inf')
            score = abs(math.log10(max(disp, 1e-300)) - 1)
            if score < best_score:
                best_score = score
                best = u
        return best

    def tolist(self) -> list[Quantity]:
        return [Quantity(v, self.dim, self._unit_hint) for v in self._data]


class Mat:
    """
    A unit-aware matrix. Stores values in SI internally.

    Usage:
        m = Mat([[1,2],[3,4]], dim=(0,0,0,0,0,0,0))
        m = Mat.from_quantity_rows([[Q, Q], [Q, Q]])
    """
    __slots__ = ('_data', 'dim', '_unit_hint')

    def __init__(self, data, dim: DimVec = DIMENSIONLESS, unit_hint: str = None):
        if isinstance(data, np.ndarray):
            self._data = data.astype(float)
        else:
            self._data = np.array(data, dtype=float)
        if self._data.ndim != 2:
            raise ValueError(f"Mat requires 2D data, got {self._data.ndim}D")
        self.dim = dim
        self._unit_hint = unit_hint

    @staticmethod
    def from_quantity_rows(rows: list[list[Quantity]]) -> Mat:
        """Build a Mat from nested lists of Quantities."""
        if not rows or not rows[0]:
            return Mat(np.array([[]]), DIMENSIONLESS)
        dim = rows[0][0].dim
        for i, row in enumerate(rows):
            for j, q in enumerate(row):
                if q.dim != dim:
                    raise DimensionError(
                        f"Mat element [{i}][{j}] has dim {q.dim}, expected {dim}")
        values = np.array([[q.value for q in row] for row in rows])
        return Mat(values, dim, rows[0][0]._unit_hint)

    @property
    def shape(self) -> tuple:
        return self._data.shape

    @property
    def rows(self) -> int:
        return self._data.shape[0]

    @property
    def cols(self) -> int:
        return self._data.shape[1]

    def __len__(self) -> int:
        return self.rows

    # ── Element access ───────────────────────────────────────────────────

    def __getitem__(self, idx):
        if isinstance(idx, Quantity):
            idx = int(idx.value)
        result = self._data[idx]
        if isinstance(result, np.ndarray):
            if result.ndim == 1:
                return Vec(result, self.dim, self._unit_hint)
            return Mat(result, self.dim, self._unit_hint)
        return Quantity(float(result), self.dim, self._unit_hint)

    # ── Arithmetic ───────────────────────────────────────────────────────

    def __add__(self, other):
        if isinstance(other, Mat):
            if self.dim != other.dim:
                raise DimensionError(f"Cannot add Mat({self.dim}) and Mat({other.dim})")
            return Mat(self._data + other._data, self.dim, self._unit_hint)
        return NotImplemented

    def __sub__(self, other):
        if isinstance(other, Mat):
            if self.dim != other.dim:
                raise DimensionError(f"Cannot subtract Mat({other.dim}) from Mat({self.dim})")
            return Mat(self._data - other._data, self.dim, self._unit_hint)
        return NotImplemented

    def __mul__(self, other):
        """Element-wise scalar multiplication."""
        if isinstance(other, Quantity):
            new_dim = dim_add(self.dim, other.dim)
            return Mat(self._data * other.value, new_dim)
        if isinstance(other, (int, float)):
            return Mat(self._data * other, self.dim, self._unit_hint)
        return NotImplemented

    def __rmul__(self, other):
        return self.__mul__(other)

    def __truediv__(self, other):
        if isinstance(other, Quantity):
            new_dim = dim_sub(self.dim, other.dim)
            return Mat(self._data / other.value, new_dim)
        if isinstance(other, (int, float)):
            return Mat(self._data / other, self.dim, self._unit_hint)
        return NotImplemented

    def __neg__(self):
        return Mat(-self._data, self.dim, self._unit_hint)

    # ── Matrix operations ────────────────────────────────────────────────

    def matmul(self, other) -> Union[Mat, Vec]:
        """Matrix multiplication. Dimensions combine via multiplication."""
        if isinstance(other, Mat):
            if self.cols != other.rows:
                raise ValueError(
                    f"Mat shapes incompatible: {self.shape} @ {other.shape}")
            new_dim = dim_add(self.dim, other.dim)
            return Mat(self._data @ other._data, new_dim)
        if isinstance(other, Vec):
            if self.cols != other.size:
                raise ValueError(
                    f"Mat-Vec shapes incompatible: {self.shape} @ ({other.size},)")
            new_dim = dim_add(self.dim, other.dim)
            return Vec(self._data @ other._data, new_dim)
        raise TypeError(f"matmul requires Mat or Vec, got {type(other).__name__}")

    def transpose(self) -> Mat:
        return Mat(self._data.T, self.dim, self._unit_hint)

    def det(self) -> Quantity:
        """Determinant. For an NxN matrix with dim D, result has dim N*D."""
        if self.rows != self.cols:
            raise ValueError("Determinant requires a square matrix")
        n = self.rows
        result_dim = dim_mul_scalar(self.dim, n)
        return Quantity(float(np.linalg.det(self._data)), result_dim)

    def inv(self) -> Mat:
        """Inverse. Dimensions are negated (A⁻¹ has dim -D if A has dim D)."""
        if self.rows != self.cols:
            raise ValueError("Inverse requires a square matrix")
        neg_dim = dim_mul_scalar(self.dim, -1)
        return Mat(np.linalg.inv(self._data), neg_dim)

    def trace(self) -> Quantity:
        """Trace of a square matrix."""
        if self.rows != self.cols:
            raise ValueError("Trace requires a square matrix")
        return Quantity(float(np.trace(self._data)), self.dim, self._unit_hint)

    # ── Comparison ───────────────────────────────────────────────────────

    def __eq__(self, other):
        if isinstance(other, Mat):
            return self.dim == other.dim and np.allclose(self._data, other._data)
        return NotImplemented

    # ── Display ──────────────────────────────────────────────────────────

    def __repr__(self):
        unit = self._best_unit_str()
        rows = []
        disp = self._display_values()
        for row in disp:
            rows.append('[' + ', '.join(f'{v:g}' for v in row) + ']')
        inner = ', '.join(rows)
        if unit:
            return f"[{inner}] {unit}"
        return f"[{inner}]"

    def _display_values(self) -> np.ndarray:
        if self._unit_hint:
            u = REGISTRY.get(self._unit_hint)
            if u and u.dim == self.dim:
                return self._data / u.to_si
        return self._data

    def _best_unit_str(self) -> str:
        if self._unit_hint:
            u = REGISTRY.get(self._unit_hint)
            if u and u.dim == self.dim:
                return u.symbol
        return ""


# ─── Linear algebra functions ────────────────────────────────────────────────

def dot(a: Vec, b: Vec) -> Quantity:
    return a.dot(b)

def cross(a: Vec, b: Vec) -> Vec:
    return a.cross(b)

def norm(v: Vec) -> Quantity:
    return v.norm()

def transpose(m: Mat) -> Mat:
    return m.transpose()

def det(m: Mat) -> Quantity:
    return m.det()

def inv(m: Mat) -> Mat:
    return m.inv()

def solve(A: Mat, b: Vec) -> Vec:
    """Solve Ax = b. Result dims = b.dim - A.dim."""
    if not isinstance(A, Mat) or not isinstance(b, Vec):
        raise TypeError("solve requires Mat and Vec")
    if A.rows != A.cols:
        raise ValueError("solve requires a square matrix")
    if A.rows != b.size:
        raise ValueError(f"Dimensions mismatch: A is {A.shape}, b has {b.size} elements")
    result_dim = dim_sub(b.dim, A.dim)
    x = np.linalg.solve(A._data, b._data)
    return Vec(x, result_dim)

def eye(n: int, dim: DimVec = DIMENSIONLESS) -> Mat:
    """Identity matrix."""
    if isinstance(n, Quantity):
        n = int(n.value)
    return Mat(np.eye(n), dim)

def zeros_vec(n: int, dim: DimVec = DIMENSIONLESS) -> Vec:
    if isinstance(n, Quantity):
        n = int(n.value)
    return Vec(np.zeros(n), dim)

def zeros_mat(rows: int, cols: int, dim: DimVec = DIMENSIONLESS) -> Mat:
    if isinstance(rows, Quantity):
        rows = int(rows.value)
    if isinstance(cols, Quantity):
        cols = int(cols.value)
    return Mat(np.zeros((rows, cols)), dim)
