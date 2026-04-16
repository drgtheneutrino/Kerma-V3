"""Tests for the notebook engine, equations library, constants, and new facade helpers."""
from __future__ import annotations

import math
import pytest

from kerma2 import Kerma
from kerma2 import equations as eqlib
from kerma2.constants import gamma_constant, CONST
from kerma2.notebook import Notebook, CellKind


# ── Facade shortcuts ────────────────────────────────────────────────
def test_facade_mu_alias():
    v1 = Kerma.mu("Pb", 0.662)
    v2 = Kerma.get_attenuation("Lead", 0.662)
    assert v1 == pytest.approx(v2, rel=1e-12)


def test_facade_t12_alias():
    assert Kerma.t12("Cs-137") == Kerma.half_life("Cs-137")


def test_facade_hvl_tabulated():
    assert Kerma.hvl("Pb") == pytest.approx(0.65, rel=1e-3)
    assert Kerma.hvl("Iron") == pytest.approx(1.58, rel=1e-3)


def test_facade_hvl_matches_ln2_over_mu_for_non_tabulated_energy():
    hvl = Kerma.hvl("Pb", energy_MeV=0.3)
    mu_lin = Kerma.mu_lin("Pb", 0.3)
    assert hvl == pytest.approx(math.log(2) / mu_lin, rel=1e-6)


def test_facade_activity_via_nuclide():
    A0 = 1.0e9
    t = Kerma.t12("Tc-99m")
    A = Kerma.A(A0=A0, t=t, nuclide="Tc-99m")
    assert abs(A / A0 - 0.5) < 1e-6


def test_facade_gamma_constant():
    g = Kerma.gamma("Cs-137")
    assert g is not None and 0.3 < g < 0.4


# ── Constants module ────────────────────────────────────────────────
def test_constants_lookup():
    assert CONST.c == pytest.approx(2.99792458e8)
    assert CONST.gamma("Co-60") == pytest.approx(1.32, rel=0.01)
    assert CONST.density("Lead") == pytest.approx(11.35, rel=0.01)


# ── Equations library ──────────────────────────────────────────────
def test_equations_loaded():
    assert len(eqlib.list_equations()) >= 20
    assert "activity" in eqlib.LIBRARY
    assert "hvl_from_mu" in eqlib.LIBRARY


def test_equation_activity_matches_facade():
    eq = eqlib.get("activity")
    lam = Kerma.lam("Cs-137")
    A_from_eq = eq.solve(A0=1e9, lam=lam, t=3600)
    A_from_facade = Kerma.A(A0=1e9, t=3600, nuclide="Cs-137")
    assert A_from_eq == pytest.approx(A_from_facade, rel=1e-9)


def test_equation_hvl_from_mu():
    mu_lin = Kerma.mu_lin("Pb", 0.662)
    hvl_eq = eqlib.get("hvl_from_mu").solve(mu=mu_lin)
    assert hvl_eq == pytest.approx(math.log(2)/mu_lin, rel=1e-12)


def test_equation_inverse_square():
    eq = eqlib.get("inverse_square")
    assert eq.solve(D1=100, r1=1, r2=2) == pytest.approx(25.0)


# ── Notebook engine ────────────────────────────────────────────────
def test_notebook_math_assignment_and_use():
    nb = Notebook()
    nb.add_math("A0 := 3.7e10")
    nb.add_math("A0 * 2")
    results = nb.run_all()
    assert all(r.ok for r in results)
    assert results[-1].value == pytest.approx(7.4e10)


def test_notebook_kerma_in_scope():
    nb = Notebook()
    nb.add_math("v := K.mu('Pb', 0.662)")
    nb.add_math("v")
    results = nb.run_all()
    assert results[-1].ok
    assert 0.10 < results[-1].value < 0.12


def test_notebook_python_cell():
    nb = Notebook()
    nb.add_python("x = 5\ny = 7\nx * y")
    r = nb.run_all()
    assert r[-1].ok and r[-1].value == 35


def test_notebook_error_captured():
    nb = Notebook()
    nb.add_math("foo := 1/0")
    r = nb.run_all()
    assert not r[0].ok
    assert "ZeroDivisionError" in (r[0].error or "")


def test_notebook_save_load_roundtrip(tmp_path):
    nb = Notebook()
    nb.add_math("x := 42")
    nb.add_python("y = x + 1")
    p = tmp_path / "n.kmd"
    nb.save(p)
    nb2 = Notebook.load(p)
    assert len(nb2.cells) == 2
    assert nb2.cells[0].kind == CellKind.MATH
    assert "42" in nb2.cells[0].source


def test_notebook_exports(tmp_path):
    from kerma2.notebook import export
    nb = Notebook()
    nb.add_math("x := 5")
    nb.add_math("y := x**2")
    nb.run_all()
    p_py = tmp_path / "n.py"
    p_md = tmp_path / "n.md"
    export.to_python(nb, p_py)
    export.to_markdown(nb, p_md)
    assert p_py.stat().st_size > 0
    assert p_md.stat().st_size > 0
    # generated .py should be executable
    code = compile(p_py.read_text(), str(p_py), "exec")
    ns: dict = {}
    exec(code, ns)
    assert ns.get("x") == 5
    assert ns.get("y") == 25


def test_notebook_variables_tracked():
    nb = Notebook()
    nb.add_math("alpha := 0.5")
    nb.add_math("beta  := 2.0")
    nb.run_all()
    assert nb.variables.get("alpha") == 0.5
    assert nb.variables.get("beta") == 2.0
