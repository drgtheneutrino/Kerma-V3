"""
MathCad-style notebook view.

Three-pane layout:

    ┌──────────────┬─────────────────────────────────┬──────────────┐
    │ EQUATIONS    │        NOTEBOOK  (cells)        │ VARIABLES    │
    │ (sidebar)    │                                 │ (live watch) │
    └──────────────┴─────────────────────────────────┴──────────────┘

    ── toolbar: [+ Math] [+ Python] [+ Text] [Run All] [Save] [Open] [Export ▾]

Each cell is a compact card with a kind-tag on the left, an editable source
area, a rendered LaTeX strip (for math cells), and a numeric readout.
Clicking an equation in the sidebar inserts it into the currently-focused
cell (or appends a new math cell if none is focused).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QTextCursor, QPixmap, QImage, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox, QPlainTextEdit,
    QPushButton, QScrollArea, QSizePolicy, QSplitter, QTableWidget,
    QTableWidgetItem, QToolBar, QToolButton, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget, QHeaderView,
)

from ...notebook import Notebook, Cell, CellKind
from ...notebook import export as _export
from ... import equations as _eqlib
from ..theme import PALETTE, FONT_UI, FONT_MONO


# ═══════════════════════════════════════════════════════════════════
# LaTeX rendering — via matplotlib's mathtext, rendered to a QPixmap.
# ═══════════════════════════════════════════════════════════════════
def render_latex_pixmap(latex: str, *, fontsize: int = 13,
                        color: str = None, dpi: int = 140) -> Optional[QPixmap]:
    """Render a LaTeX string to a QPixmap using matplotlib's mathtext.
    Returns None if rendering fails (bad syntax, missing dep)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
    except Exception:
        return None
    color = color or PALETTE["text"]
    try:
        fig = Figure(figsize=(0.01, 0.01), dpi=dpi)
        fig.patch.set_alpha(0.0)
        canvas = FigureCanvasAgg(fig)
        txt = fig.text(0, 0, f"${latex}$", fontsize=fontsize, color=color)
        canvas.draw()
        bbox = txt.get_window_extent(renderer=canvas.get_renderer())
        w, h = int(bbox.width) + 6, int(bbox.height) + 4
        fig.set_size_inches(w / dpi, h / dpi)
        txt.set_position((3 / w, 2 / h))
        canvas.draw()
        buf = canvas.buffer_rgba()
        qimg = QImage(bytes(buf), canvas.get_width_height()[0],
                      canvas.get_width_height()[1], QImage.Format.Format_RGBA8888)
        return QPixmap.fromImage(qimg.copy())
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════
# A single cell widget
# ═══════════════════════════════════════════════════════════════════
class CellWidget(QFrame):
    requestRun     = pyqtSignal(str)   # cell_id
    requestDelete  = pyqtSignal(str)
    requestMoveUp  = pyqtSignal(str)
    requestMoveDn  = pyqtSignal(str)
    focusGained    = pyqtSignal(str)

    def __init__(self, cell: Cell, parent=None):
        super().__init__(parent)
        self.cell = cell
        self.setObjectName("cellCard")
        self.setStyleSheet(
            f"QFrame#cellCard {{ background: {PALETTE['surface']}; "
            f"border: 1px solid {PALETTE['border']}; border-radius: 3px; }}"
            f"QFrame#cellCard:focus-within {{ border: 1px solid {PALETTE['accent']}; }}"
        )
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # left kind-strip
        strip = QLabel()
        strip.setFixedWidth(6)
        kind_colors = {
            CellKind.MATH:   PALETTE["accent"],
            CellKind.PYTHON: PALETTE["safe"],
            CellKind.TEXT:   PALETTE["text_faint"],
        }
        strip.setStyleSheet(f"background: {kind_colors[cell.kind]};")
        outer.addWidget(strip)

        body = QVBoxLayout()
        body.setContentsMargins(14, 10, 14, 10)
        body.setSpacing(8)

        # header row  (kind label + buttons)
        hdr = QHBoxLayout(); hdr.setSpacing(4)
        kind_lbl = QLabel(cell.kind.value.upper())
        kind_lbl.setStyleSheet(
            f"font-family:{FONT_UI}; font-size:8.5pt; font-weight:700; "
            f"letter-spacing:1.4px; color:{PALETTE['text_faint']};")
        hdr.addWidget(kind_lbl)
        hdr.addStretch()
        for txt, slot, tip in [
            ("▲", lambda: self.requestMoveUp.emit(cell.id),   "Move up"),
            ("▼", lambda: self.requestMoveDn.emit(cell.id),   "Move down"),
            ("⟳", lambda: self.requestRun.emit(cell.id),       "Run this cell"),
            ("×", lambda: self.requestDelete.emit(cell.id),   "Delete cell"),
        ]:
            b = QToolButton(); b.setText(txt); b.setToolTip(tip)
            b.setStyleSheet(
                f"QToolButton {{ background:transparent; border:none; "
                f"color:{PALETTE['text_faint']}; padding:2px 6px; font-size:11pt; }}"
                f"QToolButton:hover {{ color:{PALETTE['accent']}; }}")
            b.clicked.connect(slot)
            hdr.addWidget(b)
        body.addLayout(hdr)

        # source editor
        self.editor = QPlainTextEdit()
        self.editor.setPlainText(cell.source)
        self.editor.setStyleSheet(
            f"QPlainTextEdit {{ background: transparent; border: none; "
            f"font-family: {FONT_MONO}; font-size: 10.5pt; "
            f"color: {PALETTE['text']}; }}")
        self.editor.setFrameStyle(QFrame.Shape.NoFrame)
        self._autosize_editor()
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.focusInEvent = self._focus_wrap(self.editor.focusInEvent)
        body.addWidget(self.editor)

        # LaTeX render area (math only)
        self.latexLabel = QLabel()
        self.latexLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.latexLabel.setStyleSheet("padding: 6px 0;")
        self.latexLabel.setVisible(False)
        body.addWidget(self.latexLabel)

        # readout
        self.readout = QLabel()
        self.readout.setStyleSheet(
            f"font-family:{FONT_MONO}; font-size:11pt; font-weight:600; "
            f"color:{PALETTE['accent']}; padding: 2px 0;")
        self.readout.setVisible(False)
        body.addWidget(self.readout)

        # error area
        self.err = QLabel()
        self.err.setStyleSheet(
            f"font-family:{FONT_MONO}; font-size:9pt; "
            f"color:{PALETTE['danger']}; padding: 4px 0;")
        self.err.setWordWrap(True)
        self.err.setVisible(False)
        body.addWidget(self.err)

        outer.addLayout(body, 1)

        # keyboard: Ctrl+Enter runs
        QShortcut(QKeySequence("Ctrl+Return"), self.editor,
                  activated=lambda: self.requestRun.emit(cell.id))
        QShortcut(QKeySequence("Shift+Return"), self.editor,
                  activated=lambda: self.requestRun.emit(cell.id))

    def _focus_wrap(self, fn):
        def _wrapped(event):
            self.focusGained.emit(self.cell.id)
            return fn(event)
        return _wrapped

    def _on_text_changed(self):
        self.cell.source = self.editor.toPlainText()
        self._autosize_editor()

    def _autosize_editor(self):
        doc = self.editor.document()
        n = max(1, doc.blockCount())
        h = int(n * self.editor.fontMetrics().lineSpacing() + 12)
        self.editor.setFixedHeight(min(max(h, 28), 400))

    def refresh_output(self):
        """Pull results out of self.cell and paint them."""
        c = self.cell
        # error
        if c.error:
            # keep only last line of traceback for compactness
            line = c.error.strip().splitlines()[-1] if c.error.strip() else ""
            self.err.setText(line)
            self.err.setVisible(True)
        else:
            self.err.setVisible(False)

        # latex (math only)
        if c.kind == CellKind.MATH and c.latex:
            pm = render_latex_pixmap(c.latex, fontsize=14,
                                      color=PALETTE["text"])
            if pm is not None:
                self.latexLabel.setPixmap(pm)
                self.latexLabel.setVisible(True)
            else:
                self.latexLabel.setVisible(False)
        else:
            self.latexLabel.setVisible(False)

        # readout
        if c.output:
            self.readout.setText("= " + c.output)
            self.readout.setVisible(True)
        else:
            self.readout.setVisible(False)


# ═══════════════════════════════════════════════════════════════════
# Equations sidebar
# ═══════════════════════════════════════════════════════════════════
class EquationsSidebar(QWidget):
    insertEquation = pyqtSignal(str)   # snippet

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(250)
        self.setStyleSheet(
            f"background:{PALETTE['surface']}; "
            f"border-right:1px solid {PALETTE['border']};")
        v = QVBoxLayout(self); v.setContentsMargins(14, 18, 12, 14); v.setSpacing(10)

        title = QLabel("EQUATIONS")
        title.setStyleSheet(
            f"font-family:{FONT_UI}; font-size:9pt; font-weight:700; "
            f"letter-spacing:1.5px; color:{PALETTE['text_faint']};")
        v.addWidget(title)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search…")
        self.search.textChanged.connect(self._filter)
        v.addWidget(self.search)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setStyleSheet(
            f"QTreeWidget {{ background:{PALETTE['surface']}; border:none; "
            f"font-family:{FONT_UI}; }}"
            f"QTreeWidget::item {{ padding: 3px 2px; }}"
            f"QTreeWidget::item:hover {{ background:{PALETTE['surface_alt']}; }}"
            f"QTreeWidget::item:selected {{ background:{PALETTE['accent_soft']}; "
            f"color:{PALETTE['text']}; }}")
        self.tree.itemDoubleClicked.connect(self._on_double)
        v.addWidget(self.tree, 1)

        hint = QLabel("Double-click to insert")
        hint.setStyleSheet(
            f"color:{PALETTE['text_faint']}; font-size:9pt; "
            f"font-style:italic;")
        v.addWidget(hint)

        self._populate()

    def _populate(self):
        self.tree.clear()
        by_cat = {}
        for eq in _eqlib.list_equations():
            by_cat.setdefault(eq.category, []).append(eq)
        for cat in sorted(by_cat):
            cat_it = QTreeWidgetItem([cat])
            cat_it.setExpanded(True)
            f = cat_it.font(0); f.setBold(True); cat_it.setFont(0, f)
            cat_it.setForeground(0, cat_it.foreground(0))
            self.tree.addTopLevelItem(cat_it)
            for eq in by_cat[cat]:
                it = QTreeWidgetItem([eq.name])
                it.setToolTip(0, eq.description)
                it.setData(0, Qt.ItemDataRole.UserRole, eq.snippet)
                cat_it.addChild(it)
            cat_it.setExpanded(True)
        self.tree.expandAll()

    def _filter(self, text: str):
        text = text.lower().strip()
        for i in range(self.tree.topLevelItemCount()):
            cat = self.tree.topLevelItem(i)
            any_visible = False
            for j in range(cat.childCount()):
                ch = cat.child(j)
                visible = (text == "") or (text in ch.text(0).lower())
                ch.setHidden(not visible)
                any_visible = any_visible or visible
            cat.setHidden(not any_visible)

    def _on_double(self, item, _col):
        snippet = item.data(0, Qt.ItemDataRole.UserRole)
        if snippet:
            self.insertEquation.emit(snippet)


# ═══════════════════════════════════════════════════════════════════
# Variables watch pane
# ═══════════════════════════════════════════════════════════════════
class VariablesPane(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(250)
        self.setStyleSheet(
            f"background:{PALETTE['surface']}; "
            f"border-left:1px solid {PALETTE['border']};")
        v = QVBoxLayout(self); v.setContentsMargins(14, 18, 14, 14); v.setSpacing(10)

        title = QLabel("VARIABLES")
        title.setStyleSheet(
            f"font-family:{FONT_UI}; font-size:9pt; font-weight:700; "
            f"letter-spacing:1.5px; color:{PALETTE['text_faint']};")
        v.addWidget(title)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Name", "Value"])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        v.addWidget(self.table, 1)

    def update_vars(self, vars_dict: dict):
        items = sorted(vars_dict.items())
        self.table.setRowCount(len(items))
        for r, (k, val) in enumerate(items):
            k_it = QTableWidgetItem(k)
            try:
                mag = getattr(val, "magnitude", None)
                if mag is not None:
                    v_it = QTableWidgetItem(f"{mag:.4g} {val.units:~P}")
                elif isinstance(val, float):
                    v_it = QTableWidgetItem(f"{val:.4g}")
                else:
                    v_it = QTableWidgetItem(str(val)[:60])
            except Exception:
                v_it = QTableWidgetItem(str(val)[:60])
            self.table.setItem(r, 0, k_it)
            self.table.setItem(r, 1, v_it)


# ═══════════════════════════════════════════════════════════════════
# The main NotebookView
# ═══════════════════════════════════════════════════════════════════
class NotebookView(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.nb: Notebook = Notebook()
        self._focus_cell_id: Optional[str] = None
        self._cell_widgets: dict[str, CellWidget] = {}
        self.current_path: Optional[str] = None

        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        root.addWidget(self._build_toolbar())

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setHandleWidth(1)
        split.setStyleSheet(f"QSplitter::handle {{ background:{PALETTE['border']}; }}")

        self.sidebar = EquationsSidebar()
        self.sidebar.insertEquation.connect(self._insert_snippet)
        split.addWidget(self.sidebar)

        # scrollable notebook canvas
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet(f"QScrollArea {{ background:{PALETTE['bg']}; }}")

        self.canvas = QWidget()
        self.canvas.setStyleSheet(f"background:{PALETTE['bg']};")
        self.cells_layout = QVBoxLayout(self.canvas)
        self.cells_layout.setContentsMargins(48, 32, 48, 160)
        self.cells_layout.setSpacing(14)
        self.cells_layout.addStretch()
        self.scroll.setWidget(self.canvas)
        split.addWidget(self.scroll)

        self.vars_pane = VariablesPane()
        split.addWidget(self.vars_pane)

        split.setStretchFactor(0, 0); split.setStretchFactor(1, 1); split.setStretchFactor(2, 0)
        root.addWidget(split, 1)

        # seed: a friendly welcome cell
        self._seed_welcome()

    # ---- toolbar -------------------------------------------------------
    def _build_toolbar(self) -> QWidget:
        bar = QFrame(); bar.setFixedHeight(48)
        bar.setStyleSheet(
            f"QFrame {{ background:{PALETTE['surface']}; "
            f"border-bottom:1px solid {PALETTE['border']}; }}")
        lay = QHBoxLayout(bar); lay.setContentsMargins(18, 6, 18, 6); lay.setSpacing(6)

        def _btn(label, slot, primary=False):
            b = QPushButton(label)
            if primary:
                b.setStyleSheet(
                    f"QPushButton {{ background:{PALETTE['accent']}; color:white; "
                    f"border:1px solid {PALETTE['accent']}; border-radius:2px; "
                    f"padding:6px 14px; font-weight:600; }}"
                    f"QPushButton:hover {{ background:{PALETTE['accent_hover']}; }}")
            else:
                b.setStyleSheet(
                    f"QPushButton {{ background:transparent; "
                    f"border:1px solid {PALETTE['border_strong']}; border-radius:2px; "
                    f"padding:6px 12px; color:{PALETTE['text']}; }}"
                    f"QPushButton:hover {{ border-color:{PALETTE['accent']}; "
                    f"color:{PALETTE['accent']}; }}")
            b.clicked.connect(slot)
            return b

        title = QLabel("NOTEBOOK")
        title.setStyleSheet(
            f"font-family:{FONT_UI}; font-size:9.5pt; font-weight:700; "
            f"letter-spacing:1.5px; color:{PALETTE['text_faint']};")
        lay.addWidget(title)
        lay.addSpacing(14)
        lay.addWidget(_btn("+ Math",   lambda: self._add_cell(CellKind.MATH)))
        lay.addWidget(_btn("+ Python", lambda: self._add_cell(CellKind.PYTHON)))
        lay.addWidget(_btn("+ Text",   lambda: self._add_cell(CellKind.TEXT)))
        lay.addSpacing(10)
        lay.addWidget(_btn("▶ Run All", self._run_all, primary=True))
        lay.addStretch()
        lay.addWidget(_btn("Open",     self._open))
        lay.addWidget(_btn("Save",     self._save))

        export_btn = QToolButton()
        export_btn.setText("Export ▾")
        export_btn.setStyleSheet(
            f"QToolButton {{ background:transparent; "
            f"border:1px solid {PALETTE['border_strong']}; border-radius:2px; "
            f"padding:6px 12px; color:{PALETTE['text']}; }}"
            f"QToolButton:hover {{ border-color:{PALETTE['accent']}; "
            f"color:{PALETTE['accent']}; }}")
        export_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        m = QMenu(export_btn)
        m.addAction("Python script (.py)", self._export_py)
        m.addAction("Word document (.docx)", self._export_docx)
        m.addAction("Markdown (.md)", self._export_md)
        export_btn.setMenu(m)
        lay.addWidget(export_btn)

        return bar

    # ---- welcome cell --------------------------------------------------
    def _seed_welcome(self):
        self._add_cell(CellKind.TEXT,
            "# Welcome\nMathCad-style notebook. Pre-loaded: `K` (Kerma facade), "
            "`exp`, `ln`, `sqrt`, `pi`, `np`, `sp`, `ureg`, `Q_`.\n"
            "Use `:=` to assign variables and `=` or a bare expression to show "
            "a LaTeX-rendered result. Press Ctrl+Enter to run a cell.")
        self._add_cell(CellKind.MATH,
            "# Cs-137 example\n"
            "A0   := 10 * 3.7e7       # 10 mCi source  (Bq)\n"
            "T12  := K.t12('Cs-137')  # half-life (s)\n"
            "t    := 5 * K.const.year_s\n"
            "A    := A0 * exp(-ln(2)/T12 * t)")
        self._add_cell(CellKind.PYTHON,
            "# use the shielding engine\n"
            "res = K.dose('Cs-137', activity_Bq=A0, distance_cm=100,\n"
            "             layers=[('Pb', 2.0)])\n"
            "f'{res.total_uSv_per_hr:.2f} µSv/h'")

    # ---- cell lifecycle ------------------------------------------------
    def _add_cell(self, kind: CellKind, source: str = "") -> None:
        cell = self.nb.add(kind, source)
        w = CellWidget(cell)
        w.requestRun.connect(self._run_cell)
        w.requestDelete.connect(self._delete_cell)
        w.requestMoveUp.connect(lambda cid: self._move_cell(cid, -1))
        w.requestMoveDn.connect(lambda cid: self._move_cell(cid, +1))
        w.focusGained.connect(self._on_focus_gained)
        self._cell_widgets[cell.id] = w

        # insert before the stretch
        count = self.cells_layout.count()
        self.cells_layout.insertWidget(count - 1, w)
        self._focus_cell_id = cell.id

    def _delete_cell(self, cid: str) -> None:
        w = self._cell_widgets.pop(cid, None)
        if w:
            w.setParent(None); w.deleteLater()
        self.nb.remove(cid)

    def _move_cell(self, cid: str, delta: int) -> None:
        self.nb.move(cid, delta)
        # rebuild UI order
        for w in self._cell_widgets.values():
            w.setParent(None)
        for c in self.nb.cells:
            w = self._cell_widgets[c.id]
            count = self.cells_layout.count()
            self.cells_layout.insertWidget(count - 1, w)

    def _on_focus_gained(self, cid: str) -> None:
        self._focus_cell_id = cid

    # ---- running -------------------------------------------------------
    def _run_all(self) -> None:
        self.nb.run_all()
        for c in self.nb.cells:
            w = self._cell_widgets.get(c.id)
            if w: w.refresh_output()
        self.vars_pane.update_vars(self.nb.variables)

    def _run_cell(self, cid: str) -> None:
        # safest: re-run the whole notebook so order is preserved
        self._run_all()

    # ---- equation insertion -------------------------------------------
    def _insert_snippet(self, snippet: str) -> None:
        if self._focus_cell_id and self._focus_cell_id in self._cell_widgets:
            w = self._cell_widgets[self._focus_cell_id]
            cur = w.editor.textCursor()
            cur.insertText(snippet + "\n")
            w.editor.setFocus()
        else:
            self._add_cell(CellKind.MATH, snippet)

    # ---- file I/O ------------------------------------------------------
    def _save(self) -> None:
        path = self.current_path or QFileDialog.getSaveFileName(
            self, "Save Notebook", "", "Kerma Notebook (*.kmd);;All files (*)")[0]
        if not path:
            return
        if not path.endswith(".kmd"):
            path += ".kmd"
        try:
            self.nb.save(path)
            self.current_path = path
        except Exception as e:
            QMessageBox.critical(self, "Save", f"{type(e).__name__}: {e}")

    def _open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Notebook", "", "Kerma Notebook (*.kmd);;All files (*)")
        if not path:
            return
        try:
            nb = Notebook.load(path)
        except Exception as e:
            QMessageBox.critical(self, "Open", f"{type(e).__name__}: {e}")
            return
        # clear
        for w in list(self._cell_widgets.values()):
            w.setParent(None); w.deleteLater()
        self._cell_widgets.clear()
        self.nb = nb
        for c in self.nb.cells:
            w = CellWidget(c)
            w.requestRun.connect(self._run_cell)
            w.requestDelete.connect(self._delete_cell)
            w.requestMoveUp.connect(lambda cid: self._move_cell(cid, -1))
            w.requestMoveDn.connect(lambda cid: self._move_cell(cid, +1))
            w.focusGained.connect(self._on_focus_gained)
            self._cell_widgets[c.id] = w
            self.cells_layout.insertWidget(self.cells_layout.count() - 1, w)
        self.current_path = path
        self._run_all()

    def _export_py(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export to Python", "", "Python (*.py)")
        if path:
            if not path.endswith(".py"): path += ".py"
            _export.to_python(self.nb, path)

    def _export_docx(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export to Word", "", "Word (*.docx)")
        if path:
            if not path.endswith(".docx"): path += ".docx"
            try:
                _export.to_docx(self.nb, path)
            except RuntimeError as e:
                QMessageBox.warning(self, "Export", str(e))

    def _export_md(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export to Markdown", "", "Markdown (*.md)")
        if path:
            if not path.endswith(".md"): path += ".md"
            _export.to_markdown(self.nb, path)
