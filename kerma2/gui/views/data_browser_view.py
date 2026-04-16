"""
Data Browser — browse the nuclear data warehouse.

Two tabs:
  • Nuclides   — symbol, Z, A, half-life, principal γ lines
  • Materials  — name, density, Z_eff, μ/ρ at 662 keV (Cs-137 calibration)
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QTabWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ...data.databridge import DataBridge
from ..theme import PALETTE


class DataBrowserView(QWidget):
    def __init__(self, db: DataBridge, parent=None):
        super().__init__(parent)
        self.db = db
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 32, 40, 32); root.setSpacing(18)

        root.addWidget(_title("DATA WAREHOUSE"))
        root.addWidget(_heading("Browse the integrated nuclear database"))

        tabs = QTabWidget()
        tabs.addTab(self._build_nuclides_tab(), "Nuclides")
        tabs.addTab(self._build_materials_tab(), "Materials")
        root.addWidget(tabs, 1)

    # ------------------------------------------------------------------
    def _build_nuclides_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w); v.setContentsMargins(0, 14, 0, 0)
        tbl = QTableWidget(0, 6)
        tbl.setHorizontalHeaderLabels(
            ["Symbol", "Z", "A", "Half-life", "Decay const [1/s]", "Principal γ [MeV]"])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tbl.verticalHeader().setVisible(False)
        tbl.setAlternatingRowColors(True)
        tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        for sym in self.db.list_nuclides():
            n = self.db.get_nuclide(sym)
            if not n:
                continue
            em = self.db.get_emissions(sym, radiation="G")
            top = ", ".join(f"{e.energy_MeV:.3f} ({e.yield_per_decay*100:.1f}%)" for e in em[:3])
            r = tbl.rowCount()
            tbl.insertRow(r)
            vals = [
                sym, str(n.Z), str(n.A), _human_T(n.half_life_s),
                f"{n.decay_const_s:.3e}" if n.decay_const_s else "—",
                top or "—",
            ]
            for c, val in enumerate(vals):
                it = QTableWidgetItem(val)
                if c in (1, 2, 4):
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                tbl.setItem(r, c, it)
        v.addWidget(tbl)
        return w

    def _build_materials_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w); v.setContentsMargins(0, 14, 0, 0)
        tbl = QTableWidget(0, 5)
        tbl.setHorizontalHeaderLabels(
            ["Name", "Density [g/cm³]", "Z_eff", "μ/ρ @ 662 keV", "μ (linear) @ 662 keV"])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tbl.verticalHeader().setVisible(False)
        tbl.setAlternatingRowColors(True)
        tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        for name in self.db.list_materials():
            m = self.db.get_material(name)
            if not m:
                continue
            try:
                mu_rho = self.db.get_attenuation(name, 0.662)
                mu_lin = mu_rho * m.density_g_cm3
                mu_rho_s = f"{mu_rho:.4f} cm²/g"
                mu_lin_s = f"{mu_lin:.4f} cm⁻¹"
            except Exception:
                mu_rho_s = mu_lin_s = "—"
            r = tbl.rowCount()
            tbl.insertRow(r)
            vals = [name, f"{m.density_g_cm3:.4f}",
                    f"{m.Z_eff:.2f}" if m.Z_eff else "—",
                    mu_rho_s, mu_lin_s]
            for c, val in enumerate(vals):
                it = QTableWidgetItem(val)
                if c >= 1:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                tbl.setItem(r, c, it)
        v.addWidget(tbl)
        return w


def _title(text):
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"font-size:9pt; font-weight:700; letter-spacing:1.5px; "
        f"color:{PALETTE['text_faint']};"
    )
    return lbl


def _heading(text):
    lbl = QLabel(text)
    lbl.setStyleSheet(f"font-size:20pt; font-weight:300; color:{PALETTE['text']};")
    return lbl


def _human_T(s):
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
