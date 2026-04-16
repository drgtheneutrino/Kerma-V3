"""
Kerma main window — sidebar navigation, topbar, and stacked views.

Primary module at launch: the MathCad-style Notebook. The other modules
(Shielding Lab, Decay Chain, Data Browser, About) are still reachable
from the sidebar for quick one-off calculations.
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction, QFont, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMainWindow, QStackedWidget, QStatusBar, QVBoxLayout, QWidget,
)

from ..data.databridge import DataBridge
from .theme import PALETTE, FONT_MONO
from .views.notebook_view import NotebookView
from .views.shielding_view import ShieldingView
from .views.decay_view import DecayView
from .views.data_browser_view import DataBrowserView
from .views.about_view import AboutView
from .views.help_view import HelpView
from .. import __version__


class KermaMainWindow(QMainWindow):
    def __init__(self, db: Optional[DataBridge] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db or DataBridge()

        self.setWindowTitle("Kerma — Health Physics Toolkit")
        self.resize(1440, 880)
        self.setMinimumSize(1120, 720)

        self._build_topbar()
        self._build_body()
        self._build_statusbar()

    # ------------------------------------------------------------------
    def _build_topbar(self) -> None:
        bar = QFrame(self)
        bar.setObjectName("topBar")
        bar.setFixedHeight(58)
        lay = QHBoxLayout(bar); lay.setContentsMargins(22, 10, 22, 10); lay.setSpacing(14)

        brand = QLabel("KERMA")
        brand.setObjectName("brand")
        sub = QLabel(f"· Health Physics · v{__version__}")
        sub.setObjectName("brandSub")

        lay.addWidget(brand)
        lay.addWidget(sub)
        lay.addStretch()

        info = QLabel(f"Data: {self.db.meta('version') or 'unset'}   ·   "
                      f"{len(self.db.list_nuclides())} nuclides · "
                      f"{len(self.db.list_materials())} materials")
        info.setStyleSheet(f"color:{PALETTE['text_faint']}; font-family:{FONT_MONO};")
        lay.addWidget(info)

        self._topbar = bar

    def _build_body(self) -> None:
        central = QWidget(self)
        outer = QVBoxLayout(central); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)
        outer.addWidget(self._topbar)

        body = QWidget(); body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0); body_lay.setSpacing(0)

        # sidebar nav
        self.nav = QListWidget(); self.nav.setObjectName("navList")
        self.nav.setFixedWidth(210)
        self.nav.setFont(QFont())

        for label, icon_char in [
            ("Notebook",      "∫"),
            ("Shielding Lab", "◩"),
            ("Decay Chain",   "↯"),
            ("Data Browser",  "☷"),
            ("Help",          "?"),
            ("About",         "ℹ"),
        ]:
            item = QListWidgetItem(f"  {icon_char}    {label}")
            self.nav.addItem(item)

        self.nav.currentRowChanged.connect(self._on_nav)

        # stacked views
        self.stack = QStackedWidget()
        self.notebook_view = NotebookView(self.db)
        self.shielding_view = ShieldingView(self.db)
        self.decay_view = DecayView(self.db)
        self.browser_view = DataBrowserView(self.db)
        self.help_view = HelpView()
        self.about_view = AboutView()

        self.stack.addWidget(self.notebook_view)
        self.stack.addWidget(self.shielding_view)
        self.stack.addWidget(self.decay_view)
        self.stack.addWidget(self.browser_view)
        self.stack.addWidget(self.help_view)
        self.stack.addWidget(self.about_view)

        body_lay.addWidget(self.nav)
        body_lay.addWidget(self.stack, 1)

        outer.addWidget(body, 1)
        self.setCentralWidget(central)

        self.nav.setCurrentRow(0)

    def _build_statusbar(self) -> None:
        sb = QStatusBar(self)
        sb.showMessage("Ready · DataBridge online")
        self.setStatusBar(sb)

    def _on_nav(self, idx: int) -> None:
        self.stack.setCurrentIndex(idx)
        labels = ["Notebook", "Shielding Lab", "Decay Chain",
                  "Data Browser", "Help", "About"]
        self.statusBar().showMessage(f"Module: {labels[idx]}")
