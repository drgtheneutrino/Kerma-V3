"""Kerma MathCad-style notebook engine.

A notebook is an ordered list of `Cell` objects evaluated top-to-bottom
in a shared namespace. Three cell kinds:

    math     MathCad-ish syntax. `x := 5 * m` assigns; `f(x) = x**2` shows
             a LaTeX-rendered equation with its numerical value substituted.
    python   raw Python — executed as-is; result shown if a single expr.
    text     markdown; not evaluated.

Public surface:

    from kerma2.notebook import Notebook, Cell, CellKind
    nb = Notebook()
    nb.add_math("A0 := 3.7e10")
    nb.add_math("t  := 30 * year")
    nb.add_math("A  = A0 * exp(-ln(2)/T12 * t)")
    nb.run_all()
    nb.save("example.kmd")
"""
from __future__ import annotations

from .cell import Cell, CellKind            # noqa: F401
from .engine import Notebook, EvalResult     # noqa: F401
