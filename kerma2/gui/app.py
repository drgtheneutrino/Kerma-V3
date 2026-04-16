"""GUI bootstrap — builds QApplication, applies Nordic theme, shows main window."""

from __future__ import annotations

import sys


def launch_gui(argv=None) -> int:
    """Start the PyQt6 GUI. Blocks until the window is closed."""
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QFont, QFontDatabase
    except ImportError as e:
        print(
            "ERROR: PyQt6 is not installed. Install it with:\n"
            "    pip install PyQt6 matplotlib\n",
            file=sys.stderr,
        )
        return 2

    from .theme import apply_theme, FONT_UI
    from .main_window import KermaMainWindow

    app = QApplication.instance() or QApplication(argv or sys.argv)
    apply_theme(app)

    # set a sensible default font (even if Inter isn't installed, Segoe UI
    # is the Windows fallback and looks clean; the fallback stack in the
    # stylesheet does the rest).
    app.setFont(QFont("Segoe UI", 10))

    w = KermaMainWindow()
    w.show()
    return app.exec()
