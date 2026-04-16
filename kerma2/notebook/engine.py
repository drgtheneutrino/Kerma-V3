"""
Notebook engine — evaluates cells in a shared namespace.

Math-cell syntax (MathCad-ish):
    name := expr           assignment
    expr                   shows LaTeX + numeric value
    name = expr            alias for assignment-and-show
    # comment              rest of line ignored

Implementation sketch:
    • Each cell's source is split into logical lines.
    • Assignment lines go through `exec`.
    • The last non-assignment expression (if any) is `eval`'d, the value
      becomes the cell's numeric output, and its SymPy latex (if we can
      parse it) becomes the rendered math.
    • The namespace is shared across cells in run order, just like Jupyter
      or MathCad — define it once, use it everywhere below.
"""
from __future__ import annotations

import ast
import json
import math
import re
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .cell import Cell, CellKind


# --------------------------------------------------------------------
_ASSIGN_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:=\s*(.+)$")


def _build_default_ns() -> Dict[str, Any]:
    """Pre-load everything a health-physicist would expect in scope."""
    ns: Dict[str, Any] = {}

    # math / numpy
    import math as _m
    ns.update({k: getattr(_m, k) for k in
               ("pi", "e", "sqrt", "exp", "log", "log10", "sin", "cos", "tan",
                "asin", "acos", "atan", "sinh", "cosh", "tanh")})
    ns["ln"] = _m.log                # alias — HP convention

    try:
        import numpy as _np
        ns["np"] = _np
    except ImportError:
        pass

    # sympy
    try:
        import sympy as _sp
        ns["sp"] = _sp
    except ImportError:
        _sp = None

    # pint — unit awareness
    try:
        import pint as _pint
        ureg = _pint.UnitRegistry()
        # define extras HP cares about
        for defn in ("roentgen = 2.58e-4 C/kg = R",
                     "rem = 1e-2 Sv",
                     "curie = 3.7e10 becquerel = Ci"):
            try:
                ureg.define(defn)
            except Exception:
                pass
        ns["ureg"] = ureg
        ns["Q_"] = ureg.Quantity
        # expose unit symbols directly: Bq, MBq, GBq, Sv, mSv, uSv, Gy, m, cm, s, hr, year, eV, MeV, g, kg
        for u in ("Bq", "kBq", "MBq", "GBq", "Ci", "mCi", "uCi",
                  "Sv", "mSv", "uSv", "Gy", "mGy", "uGy", "rad", "rem",
                  "eV", "keV", "MeV", "GeV",
                  "m", "cm", "mm", "km", "inch",
                  "s", "minute", "hour", "day", "year",
                  "g", "kg", "mg", "mol"):
            try:
                ns[u] = ureg(u).units
            except Exception:
                pass
        # handy shortnames
        ns["hr"] = ns.get("hour")
        ns["yr"] = ns.get("year")
    except ImportError:
        pass

    # Kerma facade — the big deal
    try:
        from ..facade import Kerma
        ns["Kerma"] = Kerma
        ns["K"] = Kerma
        # common shortcuts
        ns["mu"] = Kerma.mu
        ns["t12"] = Kerma.t12
        ns["lam"] = Kerma.lam
        ns["activity"] = Kerma.A
        ns["hvl"] = Kerma.hvl
        ns["rho"] = Kerma.rho
    except Exception:
        pass

    # constants
    try:
        from .. import constants as _c
        for name in ("c", "N_A", "m_e_MeV", "alpha_fs", "r_e",
                     "Ci_to_Bq", "MeV_to_J", "R_to_Gy_air",
                     "s_per_hour", "s_per_day", "s_per_year"):
            ns[name] = getattr(_c, name)
    except Exception:
        pass

    return ns


# --------------------------------------------------------------------
class EvalResult:
    __slots__ = ("cell", "ok", "value", "error", "output", "latex")

    def __init__(self, cell: Cell, ok: bool, value: Any = None,
                 error: Optional[str] = None,
                 output: Optional[str] = None,
                 latex: Optional[str] = None):
        self.cell, self.ok, self.value = cell, ok, value
        self.error, self.output, self.latex = error, output, latex


# --------------------------------------------------------------------
class Notebook:
    """Ordered list of cells with a shared evaluation namespace."""

    def __init__(self):
        self.cells: List[Cell] = []
        self.ns: Dict[str, Any] = _build_default_ns()
        self.variables: Dict[str, Any] = {}     # user-defined only

    # ---- mutation ------------------------------------------------------
    def add(self, kind: CellKind, source: str = "") -> Cell:
        c = Cell(kind=kind, source=source)
        self.cells.append(c)
        return c

    def add_math(self, source: str) -> Cell:
        return self.add(CellKind.MATH, source)

    def add_python(self, source: str) -> Cell:
        return self.add(CellKind.PYTHON, source)

    def add_text(self, source: str) -> Cell:
        return self.add(CellKind.TEXT, source)

    def remove(self, cell_id: str) -> None:
        self.cells = [c for c in self.cells if c.id != cell_id]

    def move(self, cell_id: str, delta: int) -> None:
        for i, c in enumerate(self.cells):
            if c.id == cell_id:
                j = max(0, min(len(self.cells) - 1, i + delta))
                self.cells.insert(j, self.cells.pop(i))
                return

    # ---- evaluation ----------------------------------------------------
    def reset_namespace(self) -> None:
        self.ns = _build_default_ns()
        self.variables = {}

    def run_all(self) -> List[EvalResult]:
        self.reset_namespace()
        results = []
        for c in self.cells:
            results.append(self._eval_cell(c))
        return results

    def _eval_cell(self, c: Cell) -> EvalResult:
        c.output = c.latex = c.error = None
        c.value = None
        try:
            if c.kind == CellKind.TEXT:
                return EvalResult(c, True, None, None, None, None)

            if c.kind == CellKind.PYTHON:
                return self._eval_python(c)

            if c.kind == CellKind.MATH:
                return self._eval_math(c)

        except Exception:
            tb = traceback.format_exc(limit=2)
            c.error = tb
            return EvalResult(c, False, None, tb, None, None)

    # ---- python cell ---------------------------------------------------
    def _eval_python(self, c: Cell) -> EvalResult:
        source = c.source.strip()
        if not source:
            return EvalResult(c, True)
        # try last line as expression; rest as exec
        try:
            tree = ast.parse(source, mode="exec")
        except SyntaxError as e:
            c.error = f"SyntaxError: {e.msg} (line {e.lineno})"
            return EvalResult(c, False, error=c.error)

        last = tree.body[-1] if tree.body else None
        if isinstance(last, ast.Expr):
            # run everything except last, then eval last
            exec_body = ast.Module(body=tree.body[:-1], type_ignores=[])
            exec(compile(exec_body, "<cell>", "exec"), self.ns)
            val = eval(compile(ast.Expression(last.value), "<cell>", "eval"), self.ns)
            c.value = val
            c.output = _format(val)
            self._update_vars()
            return EvalResult(c, True, val, output=c.output)
        else:
            exec(compile(tree, "<cell>", "exec"), self.ns)
            self._update_vars()
            return EvalResult(c, True)

    # ---- math cell -----------------------------------------------------
    def _eval_math(self, c: Cell) -> EvalResult:
        lines = [ln for ln in c.source.splitlines()
                 if ln.strip() and not ln.strip().startswith("#")]
        if not lines:
            return EvalResult(c, True)

        last_value = None
        last_output = None
        last_latex = None

        for line in lines:
            m = _ASSIGN_RE.match(line)
            if m:
                name, rhs = m.group(1), m.group(2).strip()
                val = eval(rhs, self.ns)
                self.ns[name] = val
                self.variables[name] = val
                last_value = val
                last_output = f"{name} = {_format(val)}"
                last_latex = _try_latex(f"{name} = {rhs}", self.ns)
            else:
                # show: `expr` or `name = expr`
                show_m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$", line)
                if show_m:
                    name, rhs = show_m.group(1), show_m.group(2).strip()
                    val = eval(rhs, self.ns)
                    self.ns[name] = val
                    self.variables[name] = val
                    last_value = val
                    last_output = f"{name} = {_format(val)}"
                    last_latex = _try_latex(f"{name} = {rhs}", self.ns)
                else:
                    val = eval(line, self.ns)
                    last_value = val
                    last_output = _format(val)
                    last_latex = _try_latex(line.strip(), self.ns)

        c.value = last_value
        c.output = last_output
        c.latex = last_latex
        self._update_vars()
        return EvalResult(c, True, last_value, output=last_output, latex=last_latex)

    # ---- variable snapshot --------------------------------------------
    def _update_vars(self) -> None:
        defaults = set(_build_default_ns().keys())
        self.variables = {k: v for k, v in self.ns.items()
                          if not k.startswith("_") and k not in defaults
                          and not callable(v)}

    # ---- persistence ---------------------------------------------------
    def to_dict(self) -> dict:
        return {"version": 1, "cells": [c.to_dict() for c in self.cells]}

    @classmethod
    def from_dict(cls, d: dict) -> "Notebook":
        nb = cls()
        for cd in d.get("cells", []):
            nb.cells.append(Cell.from_dict(cd))
        return nb

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "Notebook":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(d)


# --------------------------------------------------------------------
def _format(v: Any) -> str:
    """Pretty-print a numeric value. Preserves pint units if present."""
    if v is None:
        return ""
    try:
        mag = getattr(v, "magnitude", None)
        if mag is not None:
            return f"{_fmt_num(mag)} {v.units:~P}"
    except Exception:
        pass
    if isinstance(v, (int,)):
        return str(v)
    if isinstance(v, float):
        return _fmt_num(v)
    return repr(v)


def _fmt_num(x: float) -> str:
    if x == 0:
        return "0"
    ax = abs(x)
    if ax >= 1e5 or ax < 1e-3:
        return f"{x:.4e}"
    return f"{x:.6g}"


def _try_latex(expr: str, ns: Dict[str, Any]) -> Optional[str]:
    """Best-effort SymPy LaTeX rendering of an expression."""
    sp = ns.get("sp")
    if sp is None:
        return None
    try:
        parsed = sp.sympify(expr, locals={k: v for k, v in ns.items()
                                           if isinstance(v, (int, float))})
        return sp.latex(parsed)
    except Exception:
        return None
