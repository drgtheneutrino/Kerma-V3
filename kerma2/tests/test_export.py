"""Tests for notebook exporters — .py, .md, .docx, .html, .tex round-trips."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from kerma2.notebook import Notebook, Cell, CellKind
from kerma2.notebook.export import (
    to_python, to_markdown, to_docx, to_html, to_latex,
)


@pytest.fixture
def sample_notebook():
    nb = Notebook()
    nb.cells.append(Cell(kind=CellKind.TEXT,
                         source="Demo notebook for export tests."))
    nb.cells.append(Cell(kind=CellKind.MATH,
                         source="E := 0.662",
                         latex=r"E = 0.662",
                         output="0.662"))
    nb.cells.append(Cell(kind=CellKind.MATH,
                         source="2 + 2",
                         latex=r"2 + 2",
                         output="4"))
    nb.cells.append(Cell(kind=CellKind.PYTHON,
                         source="print('hi')",
                         output="hi"))
    return nb


# ── .py ────────────────────────────────────────────────────────────
def test_to_python_writes_and_compiles(tmp_path, sample_notebook):
    p = tmp_path / "out.py"
    to_python(sample_notebook, p)
    src = p.read_text()
    assert "from kerma2 import Kerma" in src
    assert "E = 0.662" in src
    assert "print('E =', E)" in src
    # compile check — catches any syntax issues in generated script
    compile(src, str(p), "exec")


def test_to_python_handles_empty_cells(tmp_path):
    nb = Notebook()
    nb.cells.append(Cell(kind=CellKind.MATH, source=""))
    nb.cells.append(Cell(kind=CellKind.TEXT, source=""))
    p = tmp_path / "empty.py"
    to_python(nb, p)
    compile(p.read_text(), str(p), "exec")


# ── .md ────────────────────────────────────────────────────────────
def test_to_markdown_has_math_blocks(tmp_path, sample_notebook):
    p = tmp_path / "out.md"
    to_markdown(sample_notebook, p)
    txt = p.read_text()
    assert "$$" in txt
    assert "```python" in txt
    assert "Kerma Notebook" in txt


# ── .docx ──────────────────────────────────────────────────────────
def test_to_docx_writes_file(tmp_path, sample_notebook):
    pytest.importorskip("docx")
    p = tmp_path / "out.docx"
    to_docx(sample_notebook, p)
    assert p.exists() and p.stat().st_size > 500


# ── .html ──────────────────────────────────────────────────────────
def test_to_html_has_mathjax(tmp_path, sample_notebook):
    p = tmp_path / "out.html"
    to_html(sample_notebook, p)
    txt = p.read_text()
    assert "<html>" in txt
    assert "MathJax" in txt
    assert "0.662" in txt


def test_to_html_escapes(tmp_path):
    nb = Notebook()
    nb.cells.append(Cell(kind=CellKind.PYTHON,
                         source="x = 3 < 4 & 1 > 0"))
    p = tmp_path / "esc.html"
    to_html(nb, p)
    txt = p.read_text()
    assert "&lt;" in txt
    assert "&amp;" in txt


# ── .tex ───────────────────────────────────────────────────────────
def test_to_latex_structure(tmp_path, sample_notebook):
    p = tmp_path / "out.tex"
    to_latex(sample_notebook, p)
    txt = p.read_text()
    assert r"\documentclass" in txt
    assert r"\begin{equation*}" in txt
    assert r"\end{document}" in txt


def test_to_latex_escapes_specials(tmp_path):
    nb = Notebook()
    nb.cells.append(Cell(kind=CellKind.TEXT, source="100 % of $$ money"))
    p = tmp_path / "esc.tex"
    to_latex(nb, p)
    txt = p.read_text()
    assert r"\%" in txt
    assert r"\$" in txt
