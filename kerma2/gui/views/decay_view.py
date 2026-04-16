"""
Decay Chain view — pick a parent, set initial activity, plot A_i(t).

Uses matplotlib embedded into the Qt widget. The plot uses the
Nordic palette explicitly so it reads as a coherent part of the UI
rather than the default matplotlib grey.
"""

from __future__ import annotations

import numpy as np

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QDoubleSpinBox, QFormLayout, QFrame,
    QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from ...data.databridge import DataBridge
from ...physics.decay import DecayChain, solve_bateman
from ..theme import PALETTE, FONT_MONO


class DecayView(QWidget):
    def __init__(self, db: DataBridge, parent=None):
        super().__init__(parent)
        self.db = db
        self.engine = DecayChain(db)

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 32, 40, 32)
        root.setSpacing(20)

        h = QLabel("DECAY CHAIN ENGINE")
        h.setStyleSheet(
            f"font-size:9pt; font-weight:700; letter-spacing:1.5px; "
            f"color:{PALETTE['text_faint']};"
        )
        root.addWidget(h)

        title = QLabel("Solve the Bateman equations")
        title.setStyleSheet(f"font-size:20pt; font-weight:300; color:{PALETTE['text']};")
        root.addWidget(title)

        # ── controls ──
        ctl = QHBoxLayout(); ctl.setSpacing(18)

        self.cmbParent = QComboBox()
        # candidates most interesting to show chains
        candidates = ["Mo-99", "Cs-137", "Sr-90", "Ra-226", "Co-60", "I-131", "F-18"]
        for c in candidates:
            if self.db.get_nuclide(c):
                self.cmbParent.addItem(c)
        # plus the rest for completeness
        for n in self.db.list_nuclides():
            if n not in candidates and self.db.get_nuclide(n).half_life_s:
                self.cmbParent.addItem(n)

        self.spnActivity = QDoubleSpinBox()
        self.spnActivity.setRange(1.0, 1e18); self.spnActivity.setDecimals(3)
        self.spnActivity.setValue(1.0e9)

        self.spnDepth = QSpinBox(); self.spnDepth.setRange(1, 8); self.spnDepth.setValue(3)
        self.spnTmax = QDoubleSpinBox()
        self.spnTmax.setRange(0.001, 1e7); self.spnTmax.setSuffix(" × half-life")
        self.spnTmax.setValue(5.0); self.spnTmax.setDecimals(2)

        self.btnRun = QPushButton("Solve  →")
        self.btnRun.setStyleSheet(
            f"QPushButton {{ background:{PALETTE['accent']}; color:white; "
            f"border:1px solid {PALETTE['accent']}; padding:8px 18px; "
            f"border-radius:2px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{PALETTE['accent_hover']}; "
            f"border-color:{PALETTE['accent_hover']}; }}"
        )
        self.btnRun.clicked.connect(self._solve)

        ctl.addWidget(_labeled("Parent", self.cmbParent))
        ctl.addWidget(_labeled("Activity A₀  [Bq]", self.spnActivity))
        ctl.addWidget(_labeled("Chain depth", self.spnDepth))
        ctl.addWidget(_labeled("Time span", self.spnTmax))
        ctl.addStretch()
        ctl.addWidget(self.btnRun)
        root.addLayout(ctl)

        # ── figure ──
        self.fig = Figure(figsize=(8, 3.8), facecolor=PALETTE["surface"])
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.ax = self.fig.add_subplot(111)
        self._style_axes(self.ax)
        root.addWidget(self.canvas, 1)

        # ── chain listing ──
        head = QLabel("CHAIN")
        head.setStyleSheet(
            f"font-size:9pt; font-weight:700; letter-spacing:1.5px; "
            f"color:{PALETTE['text_faint']}; padding-top:6px;"
        )
        root.addWidget(head)

        self.tblChain = QTableWidget(0, 4)
        self.tblChain.setHorizontalHeaderLabels(["Nuclide", "Half-life", "λ  [1/s]", "Branch from parent"])
        self.tblChain.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tblChain.verticalHeader().setVisible(False)
        self.tblChain.setAlternatingRowColors(True)
        self.tblChain.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        root.addWidget(self.tblChain)

    # ------------------------------------------------------------------
    def _style_axes(self, ax):
        ax.set_facecolor(PALETTE["surface"])
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        for sp in ("left", "bottom"):
            ax.spines[sp].set_color(PALETTE["border_strong"])
        ax.tick_params(colors=PALETTE["text_muted"], which="both", length=3)
        ax.grid(True, color=PALETTE["grid"], linewidth=0.7)
        ax.set_xlabel("time", color=PALETTE["text_muted"])
        ax.set_ylabel("Activity [Bq]", color=PALETTE["text_muted"])
        ax.title.set_color(PALETTE["text"])

    def _solve(self):
        try:
            parent = self.cmbParent.currentText()
            A0 = float(self.spnActivity.value())
            depth = int(self.spnDepth.value())
            multiplier = float(self.spnTmax.value())

            chain = self.engine.build(parent, max_depth=depth)
            if not chain:
                raise ValueError("empty chain")

            # time axis in seconds, based on parent half-life
            T_parent = chain[0].half_life_s or 1.0
            t_max = T_parent * multiplier
            t = np.linspace(0, t_max, 400)

            res = solve_bateman(chain, parent_activity_Bq=A0, t_array_s=t)
        except Exception as e:
            QMessageBox.critical(self, "Decay Chain", f"{type(e).__name__}: {e}")
            return

        # update chart
        self.ax.clear()
        self._style_axes(self.ax)
        self.ax.set_title(f"Bateman solution · parent {parent}",
                          fontsize=11, color=PALETTE["text"])

        # pick xlabel unit
        unit, scale = _pick_time_unit(t_max)
        palette_cycle = [PALETTE["accent"], PALETTE["safe"], PALETTE["warn"],
                         PALETTE["danger"], "#8C5DB3", "#3D8C9E", "#9E7B3D"]
        for i, node in enumerate(res.chain):
            c = palette_cycle[i % len(palette_cycle)]
            self.ax.plot(res.t / scale, res.A[i],
                         color=c, linewidth=2,
                         label=f"{node.symbol}")
        self.ax.set_xlabel(f"time  [{unit}]", color=PALETTE["text_muted"])
        self.ax.set_yscale("linear")
        self.ax.legend(frameon=False, labelcolor=PALETTE["text"])
        self.fig.tight_layout()
        self.canvas.draw_idle()

        # populate chain listing
        self.tblChain.setRowCount(0)
        for node in res.chain:
            r = self.tblChain.rowCount()
            self.tblChain.insertRow(r)
            T = _human_half_life(node.half_life_s)
            cells = [node.symbol, T,
                     f"{node.lam:.3e}" if node.lam else "—",
                     f"{node.parent_branching:.4f}"]
            for c, v in enumerate(cells):
                it = QTableWidgetItem(v)
                if c != 0:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tblChain.setItem(r, c, it)


# ----------------------------------------------------------------------
def _labeled(text: str, w) -> QWidget:
    box = QWidget()
    v = QVBoxLayout(box); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(3)
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color:{PALETTE['text_muted']}; font-size:9pt;")
    v.addWidget(lbl); v.addWidget(w)
    return box


def _pick_time_unit(t_max: float):
    if t_max < 120:        return "s", 1.0
    if t_max < 7200:       return "min", 60.0
    if t_max < 172800:     return "h", 3600.0
    if t_max < 60 * 86400: return "days", 86400.0
    return "years", 86400.0 * 365.25


def _human_half_life(s):
    if s is None:
        return "stable"
    if s < 120:
        return f"{s:.3g} s"
    if s < 7200:
        return f"{s/60:.3g} min"
    if s < 172800:
        return f"{s/3600:.3g} h"
    if s < 60 * 86400:
        return f"{s/86400:.3g} d"
    return f"{s/(86400*365.25):.4g} y"
