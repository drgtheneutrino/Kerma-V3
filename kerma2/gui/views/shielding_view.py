"""
Shielding Lab view — interactive multi-layer attenuation calculator.

Layout
------
┌──────────────────────────────────────────────────────────────┐
│ SHIELDING LAB                                                │
│ Calculate dose-rate through stacked materials with G-P        │
│ buildup factors.                                             │
│                                                              │
│ ┌ Source ────────┐  ┌ Layers ───────────────────┐  ┌ Result ┐│
│ │ Nuclide ▾      │  │ # │ Material  │  t (cm)   │  │ Ḋ      ││
│ │ Activity       │  │ 1 │ Lead       │  2.0     │  │ μSv/h  ││
│ │ Distance       │  │ 2 │ Concrete   │  5.0     │  │        ││
│ └────────────────┘  └───────────────────────────┘  └────────┘│
│ [ Compute ]         [ + Add Layer ] [ − Remove ]             │
│                                                              │
│ Per-line breakdown (table)                                    │
└──────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

from typing import List

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QDoubleSpinBox, QFormLayout, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPushButton, QSizePolicy, QSpinBox, QSplitter, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from ...data.databridge import DataBridge
from ...physics.shielding import Layer, ShieldingLab
from ..theme import PALETTE, FONT_MONO


class ShieldingView(QWidget):
    def __init__(self, db: DataBridge, parent=None):
        super().__init__(parent)
        self.db = db
        self.lab = ShieldingLab(db)

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 32, 40, 32)
        root.setSpacing(22)

        # ── heading strip ──
        h = QLabel("SHIELDING LAB")
        h.setProperty("class", "sectionTitle")
        h.setStyleSheet(
            f"font-size:9pt; font-weight:700; letter-spacing:1.5px; "
            f"color:{PALETTE['text_faint']};"
        )
        root.addWidget(h)

        title = QLabel("Multi-layer attenuation with G-P buildup")
        title.setProperty("class", "heading")
        title.setStyleSheet(f"font-size:20pt; font-weight:300; color:{PALETTE['text']};")
        root.addWidget(title)

        # ── grid: source | layers | result ──
        grid = QGridLayout()
        grid.setSpacing(20)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 2)
        grid.setColumnStretch(2, 1)

        # --- Source card ---
        src_card = _card("SOURCE")
        fl = QFormLayout(); fl.setContentsMargins(18, 10, 18, 18); fl.setSpacing(12)
        self.cmbSource = QComboBox()
        for n in self.db.list_nuclides():
            self.cmbSource.addItem(n)
        default_idx = self.cmbSource.findText("Cs-137")
        if default_idx >= 0:
            self.cmbSource.setCurrentIndex(default_idx)

        self.spinActivity = _double_spin(1e-3, 1e18, 3.7e10, decimals=3)
        self.spinDistance = _double_spin(0.1, 1e5, 100.0, decimals=2)

        fl.addRow(_lbl("Nuclide"),      self.cmbSource)
        fl.addRow(_lbl("Activity  [Bq]"), self.spinActivity)
        fl.addRow(_lbl("Distance  [cm]"), self.spinDistance)
        src_card.layout().addLayout(fl)

        # --- Layers card ---
        lay_card = _card("LAYERS")
        lay_lay = QVBoxLayout(); lay_lay.setContentsMargins(18, 10, 18, 18); lay_lay.setSpacing(10)
        self.tblLayers = QTableWidget(0, 2)
        self.tblLayers.setHorizontalHeaderLabels(["Material", "Thickness [cm]"])
        self.tblLayers.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tblLayers.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tblLayers.verticalHeader().setVisible(False)
        self.tblLayers.setAlternatingRowColors(True)
        self.tblLayers.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        lay_lay.addWidget(self.tblLayers, 1)

        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        self.btnAdd = QPushButton("+ Add")
        self.btnDel = QPushButton("− Remove")
        self.btnAdd.setProperty("class", "ghost")
        self.btnDel.setProperty("class", "ghost")
        self.btnAdd.clicked.connect(self._add_layer)
        self.btnDel.clicked.connect(self._del_layer)
        btn_row.addWidget(self.btnAdd); btn_row.addWidget(self.btnDel); btn_row.addStretch()
        lay_lay.addLayout(btn_row)
        lay_card.layout().addLayout(lay_lay)

        # prime with a default 1-layer stack
        self._append_row("Lead", 2.0)

        # --- Result card ---
        res_card = _card("DOSE RATE")
        res_lay = QVBoxLayout(); res_lay.setContentsMargins(18, 14, 18, 18); res_lay.setSpacing(4)
        self.lblReadout = QLabel("— — —")
        self.lblReadout.setProperty("class", "readout")
        self.lblReadout.setStyleSheet(
            f"font-family:{FONT_MONO}; font-size:26pt; font-weight:500; color:{PALETTE['text']};"
        )
        self.lblUnit = QLabel("µSv / h")
        self.lblUnit.setStyleSheet(f"color:{PALETTE['text_faint']}; font-size:10pt;")

        self.lblBadge = QLabel("—")
        self.lblBadge.setStyleSheet(
            f"background:{PALETTE['surface_alt']}; color:{PALETTE['text_faint']}; "
            f"padding:3px 10px; border:1px solid {PALETTE['border']}; "
            f"font-weight:600; font-size:9pt; letter-spacing:0.5px;"
        )
        self.lblBadge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lblBadge.setFixedWidth(110)

        res_lay.addWidget(self.lblReadout)
        res_lay.addWidget(self.lblUnit)
        res_lay.addSpacing(12)
        res_lay.addWidget(self.lblBadge)
        res_lay.addStretch()

        self.btnCompute = QPushButton("Compute  →")
        self.btnCompute.setProperty("class", "primary")
        self.btnCompute.setStyleSheet(
            f"QPushButton {{ background:{PALETTE['accent']}; color:white; "
            f"border:1px solid {PALETTE['accent']}; padding:9px 18px; "
            f"border-radius:2px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{PALETTE['accent_hover']}; "
            f"border-color:{PALETTE['accent_hover']}; }}"
        )
        self.btnCompute.clicked.connect(self._compute)
        res_lay.addWidget(self.btnCompute)
        res_card.layout().addLayout(res_lay)

        grid.addWidget(src_card, 0, 0)
        grid.addWidget(lay_card, 0, 1)
        grid.addWidget(res_card, 0, 2)
        root.addLayout(grid)

        # ── per-line breakdown table ──
        head = QLabel("PER-LINE BREAKDOWN")
        head.setStyleSheet(
            f"font-size:9pt; font-weight:700; letter-spacing:1.5px; "
            f"color:{PALETTE['text_faint']}; padding-top:6px;"
        )
        root.addWidget(head)

        self.tblLines = QTableWidget(0, 5)
        self.tblLines.setHorizontalHeaderLabels(
            ["Energy [keV]", "Yield", "μd [mfp]", "Buildup B", "Dose [µSv/h]"])
        self.tblLines.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tblLines.verticalHeader().setVisible(False)
        self.tblLines.setAlternatingRowColors(True)
        self.tblLines.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        root.addWidget(self.tblLines, 1)

    # ------------------------------------------------------------------
    def _append_row(self, material: str, thickness: float) -> None:
        r = self.tblLines.rowCount() if False else self.tblLayers.rowCount()
        self.tblLayers.insertRow(r)
        cmb = QComboBox()
        for mn in self.db.list_materials():
            cmb.addItem(mn)
        idx = cmb.findText(material)
        if idx >= 0:
            cmb.setCurrentIndex(idx)
        self.tblLayers.setCellWidget(r, 0, cmb)

        sp = QDoubleSpinBox()
        sp.setRange(0.0, 1e4)
        sp.setDecimals(3)
        sp.setSingleStep(0.1)
        sp.setValue(thickness)
        self.tblLayers.setCellWidget(r, 1, sp)

    def _add_layer(self) -> None:
        self._append_row("Concrete (Ordinary)", 5.0)

    def _del_layer(self) -> None:
        r = self.tblLayers.currentRow()
        if r < 0 and self.tblLayers.rowCount():
            r = self.tblLayers.rowCount() - 1
        if r >= 0:
            self.tblLayers.removeRow(r)

    def _read_layers(self) -> List[Layer]:
        out = []
        for r in range(self.tblLayers.rowCount()):
            mat = self.tblLayers.cellWidget(r, 0).currentText()
            t = float(self.tblLayers.cellWidget(r, 1).value())
            if t > 0:
                out.append(Layer(mat, t))
        return out

    def _compute(self) -> None:
        try:
            nuclide = self.cmbSource.currentText()
            A = float(self.spinActivity.value())
            r = float(self.spinDistance.value())
            layers = self._read_layers()
            res = self.lab.dose_rate(nuclide, activity_Bq=A, distance_cm=r, layers=layers)
        except Exception as e:
            QMessageBox.critical(self, "Shielding Lab", f"{type(e).__name__}: {e}")
            return

        d = res.total_uSv_per_hr
        self.lblReadout.setText(_fmt(d))

        # semantic badge (regulatory-inspired thresholds for an occupational worker)
        if d < 2.5:
            self.lblBadge.setText("SAFE")
            self.lblBadge.setStyleSheet(
                f"background:{PALETTE['safe_soft']}; color:{PALETTE['safe']}; "
                f"padding:3px 10px; border:1px solid {PALETTE['safe']}; "
                f"font-weight:600; font-size:9pt; letter-spacing:0.5px;"
            )
        elif d < 25:
            self.lblBadge.setText("CAUTION")
            self.lblBadge.setStyleSheet(
                f"background:{PALETTE['warn_soft']}; color:{PALETTE['warn']}; "
                f"padding:3px 10px; border:1px solid {PALETTE['warn']}; "
                f"font-weight:600; font-size:9pt; letter-spacing:0.5px;"
            )
        else:
            self.lblBadge.setText("HIGH")
            self.lblBadge.setStyleSheet(
                f"background:{PALETTE['danger_soft']}; color:{PALETTE['danger']}; "
                f"padding:3px 10px; border:1px solid {PALETTE['danger']}; "
                f"font-weight:600; font-size:9pt; letter-spacing:0.5px;"
            )

        # populate breakdown
        self.tblLines.setRowCount(0)
        for ln in res.lines:
            r = self.tblLines.rowCount()
            self.tblLines.insertRow(r)
            vals = [f"{ln.energy_MeV*1000:.1f}", f"{ln.yield_per_decay:.4f}",
                    f"{ln.mu_d:.3f}", f"{ln.buildup:.3f}", _fmt(ln.dose_uSv_per_hr)]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tblLines.setItem(r, c, it)


# ----------------------------------------------------------------------
# small helpers
# ----------------------------------------------------------------------
def _card(title: str) -> QFrame:
    f = QFrame()
    f.setStyleSheet(
        f"QFrame {{ background: #FFFFFF; border:1px solid {PALETTE['border']}; "
        f"border-radius:2px; }}"
    )
    v = QVBoxLayout(f); v.setContentsMargins(18, 14, 18, 14); v.setSpacing(0)
    h = QLabel(title)
    h.setStyleSheet(
        f"font-size:9pt; font-weight:700; letter-spacing:1.5px; "
        f"color:{PALETTE['text_faint']}; padding-bottom:4px;"
    )
    v.addWidget(h)
    return f


def _lbl(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color:{PALETTE['text_muted']}; font-size:9.5pt;")
    return lbl


def _double_spin(lo, hi, val, decimals=3) -> QDoubleSpinBox:
    sp = QDoubleSpinBox()
    sp.setRange(lo, hi)
    sp.setDecimals(decimals)
    sp.setValue(val)
    sp.setSingleStep(max(val / 10.0, 0.1))
    sp.setAccelerated(True)
    return sp


def _fmt(x: float) -> str:
    if x == 0:
        return "0.000"
    if abs(x) >= 1e4 or abs(x) < 1e-3:
        return f"{x:.3e}"
    return f"{x:.4g}"
