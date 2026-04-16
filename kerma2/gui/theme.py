"""
Kerma v3.0 — Overleaf-inspired theme.

Design notes
------------
Overleaf's interface leans on a restrained palette: warm white paper,
deep-green primary accent, soft warm greys, and a confident serif for
body prose paired with a clean humanist sans-serif for UI chrome and a
stable monospace for code. This stylesheet emulates that: it avoids
heavy shadows, bubbly radii, and gradients, and sticks to 2-3 px
hairline borders and understated hover states.

Colour reference
----------------
  Overleaf green          #138A07  → primary buttons, active-nav bar, links
  Overleaf green dark     #0E6905
  Overleaf green pale     #E8F1E3  tab-active fill, chip backgrounds
  Paper white             #FFFFFF
  Canvas (warm)           #FAF9F7  body bg, slight warmth
  Sidebar tone            #F4F3EF  subtle warm grey
  Hairline                #E3E1DC
  Ink                     #1F2328  primary text
  Warm muted              #5C6369  secondary
  Faint                   #8B9299  tertiary / metadata
"""
from __future__ import annotations

# ── Palette ────────────────────────────────────────────────────────
PALETTE = {
    "bg":            "#FAF9F7",
    "surface":       "#FFFFFF",
    "surface_alt":   "#F4F3EF",
    "surface_dim":   "#EEEDE8",
    "border":        "#E3E1DC",
    "border_strong": "#C8C5BE",
    "text":          "#1F2328",
    "text_muted":    "#5C6369",
    "text_faint":    "#8B9299",
    "accent":        "#138A07",
    "accent_hover":  "#0E6905",
    "accent_soft":   "#E8F1E3",
    "accent_dim":    "#CDE5C4",
    "safe":          "#3E8B4A",
    "safe_soft":     "#E6F1E4",
    "warn":          "#B77B1A",
    "warn_soft":     "#F6ECD8",
    "danger":        "#B3433B",
    "danger_soft":   "#F5DDD9",
    "grid":          "#ECEAE4",
    "sidebar":       "#F4F3EF",
    "topbar":        "#FFFFFF",
}

# ── Typography ─────────────────────────────────────────────────────
FONT_UI    = '"Lato", "Open Sans", "Segoe UI", -apple-system, sans-serif'
FONT_MONO  = '"Fira Code", "Source Code Pro", "JetBrains Mono", "Cascadia Mono", "Consolas", monospace'
FONT_SERIF = '"Charter", "Georgia", "Latin Modern Roman", "Palatino", serif'

# ── QSS stylesheet ─────────────────────────────────────────────────
STYLESHEET = f"""
* {{
    font-family: {FONT_UI};
    font-size: 10.5pt;
    color: {PALETTE['text']};
}}

QMainWindow, QWidget {{
    background: {PALETTE['bg']};
}}

/* Top bar ------------------------------------------------------- */
QFrame#topBar {{
    background: {PALETTE['surface']};
    border-bottom: 1px solid {PALETTE['border']};
}}
QLabel#brand {{
    font-family: {FONT_UI};
    font-size: 15pt;
    font-weight: 700;
    letter-spacing: 1.2px;
    color: {PALETTE['accent']};
}}
QLabel#brandSub {{
    color: {PALETTE['text_faint']};
    font-size: 10pt;
    font-weight: 400;
    margin-left: 2px;
}}

/* Sidebar nav --------------------------------------------------- */
QListWidget#navList {{
    background: {PALETTE['sidebar']};
    border: none;
    border-right: 1px solid {PALETTE['border']};
    outline: none;
    padding: 10px 0 0 0;
    font-size: 10.5pt;
}}
QListWidget#navList::item {{
    padding: 10px 18px 10px 14px;
    border: none;
    border-left: 3px solid transparent;
    color: {PALETTE['text_muted']};
}}
QListWidget#navList::item:hover {{
    background: {PALETTE['surface_dim']};
    color: {PALETTE['text']};
}}
QListWidget#navList::item:selected {{
    background: {PALETTE['accent_soft']};
    border-left: 3px solid {PALETTE['accent']};
    color: {PALETTE['accent_hover']};
    font-weight: 600;
}}

/* Status bar ---------------------------------------------------- */
QStatusBar {{
    background: {PALETTE['surface']};
    border-top: 1px solid {PALETTE['border']};
    color: {PALETTE['text_muted']};
    font-size: 9.5pt;
    padding: 3px 8px;
}}

/* Buttons ------------------------------------------------------- */
QPushButton {{
    background: {PALETTE['surface']};
    border: 1px solid {PALETTE['border_strong']};
    border-radius: 3px;
    padding: 6px 14px;
    color: {PALETTE['text']};
}}
QPushButton:hover {{
    background: {PALETTE['surface_alt']};
    border-color: {PALETTE['accent']};
}}
QPushButton:pressed {{
    background: {PALETTE['accent_soft']};
}}
QPushButton:disabled {{
    color: {PALETTE['text_faint']};
    border-color: {PALETTE['border']};
}}
QPushButton[primary="true"] {{
    background: {PALETTE['accent']};
    color: #FFFFFF;
    border: 1px solid {PALETTE['accent']};
    font-weight: 600;
}}
QPushButton[primary="true"]:hover {{
    background: {PALETTE['accent_hover']};
    border-color: {PALETTE['accent_hover']};
}}

/* Text inputs --------------------------------------------------- */
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {PALETTE['surface']};
    border: 1px solid {PALETTE['border_strong']};
    border-radius: 2px;
    padding: 5px 8px;
    selection-background-color: {PALETTE['accent_soft']};
    selection-color: {PALETTE['text']};
    color: {PALETTE['text']};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {PALETTE['accent']};
}}
QPlainTextEdit, QTextEdit {{
    font-family: {FONT_MONO};
    font-size: 10.5pt;
}}

/* Tree / table / list ------------------------------------------- */
QTreeWidget, QTreeView, QTableWidget, QTableView, QListView {{
    background: {PALETTE['surface']};
    border: 1px solid {PALETTE['border']};
    alternate-background-color: {PALETTE['surface_dim']};
    selection-background-color: {PALETTE['accent_soft']};
    selection-color: {PALETTE['text']};
    gridline-color: {PALETTE['grid']};
    outline: none;
}}
QHeaderView::section {{
    background: {PALETTE['surface_alt']};
    border: none;
    border-bottom: 1px solid {PALETTE['border_strong']};
    padding: 6px 10px;
    color: {PALETTE['text_muted']};
    font-weight: 600;
    font-size: 9.5pt;
    text-transform: uppercase;
    letter-spacing: 0.4px;
}}
QTreeWidget::item, QTreeView::item {{ padding: 4px 2px; }}
QTreeWidget::item:selected, QTreeView::item:selected {{
    background: {PALETTE['accent_soft']};
    color: {PALETTE['text']};
}}

/* Splitter ------------------------------------------------------ */
QSplitter::handle {{
    background: {PALETTE['border']};
}}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical   {{ height: 1px; }}

/* Scroll bars --------------------------------------------------- */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {PALETTE['border_strong']};
    border-radius: 3px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {PALETTE['text_faint']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0; background: transparent;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {PALETTE['border_strong']};
    border-radius: 3px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {PALETTE['text_faint']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0; background: transparent;
}}

/* Tabs ---------------------------------------------------------- */
QTabWidget::pane {{
    border: 1px solid {PALETTE['border']};
    background: {PALETTE['surface']};
    top: -1px;
}}
QTabBar::tab {{
    background: {PALETTE['surface_alt']};
    color: {PALETTE['text_muted']};
    padding: 8px 16px;
    border: 1px solid {PALETTE['border']};
    border-bottom: none;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {PALETTE['surface']};
    color: {PALETTE['accent']};
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{
    background: {PALETTE['surface_dim']};
    color: {PALETTE['text']};
}}

/* Tooltip ------------------------------------------------------- */
QToolTip {{
    background: {PALETTE['text']};
    color: {PALETTE['surface']};
    border: none;
    padding: 5px 9px;
    font-size: 9.5pt;
}}

/* Menus --------------------------------------------------------- */
QMenuBar {{
    background: {PALETTE['surface']};
    border-bottom: 1px solid {PALETTE['border']};
}}
QMenuBar::item:selected {{
    background: {PALETTE['accent_soft']};
    color: {PALETTE['accent_hover']};
}}
QMenu {{
    background: {PALETTE['surface']};
    border: 1px solid {PALETTE['border_strong']};
}}
QMenu::item {{
    padding: 6px 20px;
}}
QMenu::item:selected {{
    background: {PALETTE['accent_soft']};
    color: {PALETTE['accent_hover']};
}}

/* Group box ----------------------------------------------------- */
QGroupBox {{
    background: {PALETTE['surface']};
    border: 1px solid {PALETTE['border']};
    border-radius: 3px;
    margin-top: 14px;
    padding-top: 10px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {PALETTE['text_muted']};
    font-weight: 600;
    text-transform: uppercase;
    font-size: 9pt;
    letter-spacing: 0.5px;
}}

/* Labels with semantic role ------------------------------------- */
QLabel[role="heading"] {{
    color: {PALETTE['text']};
    font-weight: 300;
    font-size: 18pt;
}}
QLabel[role="subheading"] {{
    color: {PALETTE['text_muted']};
    font-size: 10.5pt;
}}
"""


# ── Public helpers ─────────────────────────────────────────────────
def apply_theme(app) -> None:
    """Apply the Overleaf-inspired stylesheet to a QApplication."""
    app.setStyleSheet(STYLESHEET)


__all__ = ["PALETTE", "STYLESHEET", "FONT_UI", "FONT_MONO", "FONT_SERIF",
           "apply_theme"]
