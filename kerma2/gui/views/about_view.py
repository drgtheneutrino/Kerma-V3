"""About view — preserved ASCII logo, version, citations, credits.

Rewritten for v3.0: clean layout, proper CSS (no unmatched braces),
scrollable body, real hyperlinks, stable font stack fallbacks.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDesktopServices, QFont
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
)

from ... import __version__, __release__, __codename__
from ...logo import LOGO_ASCII, TAGLINE
from ..theme import PALETTE, FONT_MONO, FONT_UI


# ──────────────────────────────────────────────────────────────────────
class _Card(QFrame):
    """A simple white card with a hairline border."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AboutCard")
        self.setStyleSheet(
            f"#AboutCard {{"
            f"  background: {PALETTE['surface']};"
            f"  border: 1px solid {PALETTE['border']};"
            f"  border-radius: 3px;"
            f"}}"
        )


class AboutView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {PALETTE['bg']};")

        # Scrollable outer region — previous version could overflow on
        # small screens with no way to see the lower content.
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ background: {PALETTE['bg']}; border: none; }}")

        holder = QWidget()
        outer = QVBoxLayout(holder)
        outer.setContentsMargins(40, 36, 40, 36)
        outer.setSpacing(22)

        # ── Hero card: logo + version + tagline ─────────────────────
        hero = _Card()
        hero_l = QVBoxLayout(hero)
        hero_l.setContentsMargins(36, 30, 36, 30)
        hero_l.setSpacing(14)

        logo = QLabel(LOGO_ASCII)
        logo.setFont(QFont("JetBrains Mono", 18))
        logo.setStyleSheet(
            f"color: {PALETTE['accent']}; font-family: {FONT_MONO};"
            f"font-size: 20pt; background: transparent;"
        )
        logo.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        hero_l.addWidget(logo)

        title_row = QHBoxLayout()
        title_row.setSpacing(14)
        heading = QLabel(f"Kerma  ·  v{__version__}")
        heading.setStyleSheet(
            f"font-size: 24pt; font-weight: 300; color: {PALETTE['text']};"
            f"background: transparent;"
        )
        codename = QLabel(f"“{__codename__}” · {__release__}")
        codename.setStyleSheet(
            f"font-size: 11pt; color: {PALETTE['text_faint']};"
            f"background: transparent;"
        )
        title_row.addWidget(heading, 0, Qt.AlignmentFlag.AlignBottom)
        title_row.addWidget(codename, 0, Qt.AlignmentFlag.AlignBottom)
        title_row.addStretch()
        hero_l.addLayout(title_row)

        tagline = QLabel(TAGLINE)
        tagline.setStyleSheet(
            f"color: {PALETTE['text_muted']}; font-size: 11pt;"
            f"background: transparent;"
        )
        tagline.setWordWrap(True)
        hero_l.addWidget(tagline)

        outer.addWidget(hero)

        # ── Feature matrix ─────────────────────────────────────────
        features = _Card()
        fl = QVBoxLayout(features)
        fl.setContentsMargins(30, 24, 30, 26)
        fl.setSpacing(10)

        hdr = QLabel("What’s inside")
        hdr.setStyleSheet(
            f"font-size: 13pt; font-weight: 600; color: {PALETTE['text']};"
            f"background: transparent;"
        )
        fl.addWidget(hdr)

        for title, body in [
            ("Notebook (MathCad-style)",
             "Math, Python and text cells. LaTeX rendering, live variable pane, "
             "equation sidebar, Save/Open .kmd, Export to .py / .docx / .md."),
            ("Shielding Lab",
             "Multi-layer narrow-/broad-beam attenuation with ANSI/ANS-6.4.3 "
             "G-P buildup, HVL/TVL lookups, mixture support, mass-thickness mode."),
            ("Decay-Chain Engine",
             "Bateman solver for arbitrary chains, sourced from ICRP 107 "
             "half-lives and branching. Plot activities vs time and dump tables."),
            ("Data Browser",
             "Searchable SQLite warehouse: nuclides, emissions, decay branches, "
             "NIST XCOM μ/ρ, μ_en/ρ, FGR 11-13 / ICRP 116-119 dose coefficients."),
            ("Statistics Toolkit (v3.0)",
             "Poisson/binomial exact CIs, Currie & MARLAP & ISO 11929 detection "
             "limits, χ² GoF, Welch t, paired-t, propagation of uncertainty, "
             "Shewhart/Poisson control charts, linear-calibration fits."),
            ("REPL",
             "Same namespace as the notebook — K.mu, K.t12, K.hvl, K.gamma, K.dose. "
             "Magic commands: help / gui / notebook / dsl / exit."),
        ]:
            t = QLabel(f"<b>{title}</b>")
            t.setTextFormat(Qt.TextFormat.RichText)
            t.setStyleSheet(f"color: {PALETTE['text']}; background: transparent;")
            b = QLabel(body)
            b.setWordWrap(True)
            b.setStyleSheet(
                f"color: {PALETTE['text_muted']}; font-family: {FONT_UI};"
                f"font-size: 10.5pt; background: transparent;"
            )
            fl.addWidget(t)
            fl.addWidget(b)
            spacer = QFrame(); spacer.setFixedHeight(4)
            fl.addWidget(spacer)

        outer.addWidget(features)

        # ── Data sources & standards ───────────────────────────────
        sources = _Card()
        sl = QVBoxLayout(sources)
        sl.setContentsMargins(30, 24, 30, 26)
        sl.setSpacing(8)
        sl.addWidget(self._section_title("Data sources & standards"))

        for line in [
            "ICRP Publication 107 — Nuclear Decay Data for Dosimetric Calculations",
            "ICRP Publications 103, 116, 119 — Recommendations and reference coefficients",
            "NIST XCOM — Photon Cross Sections (μ/ρ, μ_en/ρ)",
            "ANSI/ANS-6.4.3 — Gamma-ray Buildup-factor Coefficients",
            "MARLAP (2004) — Multi-Agency Radiological Laboratory Protocols",
            "ISO 11929 (2019) — Determination of Characteristic Limits",
            "Currie, L.A. (1968), Anal. Chem. 40, 586",
            "Knoll, G.F. (2010) — Radiation Detection and Measurement, 4e",
        ]:
            item = QLabel("• " + line)
            item.setWordWrap(True)
            item.setStyleSheet(
                f"color: {PALETTE['text_muted']}; font-size: 10pt;"
                f"background: transparent;"
            )
            sl.addWidget(item)

        outer.addWidget(sources)

        # ── Footer: stack + legal + buttons ────────────────────────
        footer = _Card()
        fo = QVBoxLayout(footer)
        fo.setContentsMargins(30, 22, 30, 24)
        fo.setSpacing(10)
        fo.addWidget(self._section_title("Stack"))
        stack = QLabel(
            "Python · PyQt6 · NumPy · SciPy · SymPy · pint · matplotlib · "
            "python-docx · SQLite."
        )
        stack.setWordWrap(True)
        stack.setStyleSheet(
            f"color: {PALETTE['text_muted']}; font-size: 10pt;"
            f"background: transparent;"
        )
        fo.addWidget(stack)

        legal = QLabel(
            "© 2026 Kerma Project · Distributed AS-IS, without warranty. "
            "Kerma is an engineering aid — all regulatory, clinical, and "
            "operational decisions require independent professional review."
        )
        legal.setWordWrap(True)
        legal.setStyleSheet(
            f"color: {PALETTE['text_faint']}; font-size: 9.5pt;"
            f"background: transparent;"
        )
        fo.addWidget(legal)

        outer.addWidget(footer)
        outer.addStretch()

        scroll.setWidget(holder)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

    def _section_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"font-size: 12pt; font-weight: 600; color: {PALETTE['text']};"
            f"background: transparent;"
        )
        return lbl
