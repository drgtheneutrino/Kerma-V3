"""
Help view — a proper, production-looking Help system.

Left pane is a tree of topics; right pane is a scrollable text panel
with rich-text content, code snippets, and tables. Topics include
quick-start, notebook syntax, command reference, equation catalog,
keyboard shortcuts, and troubleshooting.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QSplitter,
    QTextBrowser, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ... import __version__
from ...equations import LIBRARY, categories
from ..theme import PALETTE, FONT_MONO, FONT_UI


# ──────────────────────────────────────────────────────────────────────
class HelpView(QWidget):
    """Two-pane help: topic tree on the left, rich HTML on the right."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {PALETTE['bg']};")

        split = QSplitter(Qt.Orientation.Horizontal, self)
        split.setHandleWidth(1)
        split.setChildrenCollapsible(False)

        # ── Left: topic tree ───────────────────────────────────────
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setFont(QFont("Segoe UI", 10))
        self.tree.setStyleSheet(
            f"QTreeWidget {{"
            f"  background: {PALETTE['surface']};"
            f"  border: none; border-right: 1px solid {PALETTE['border']};"
            f"  padding: 8px;"
            f"}}"
            f"QTreeWidget::item {{ padding: 4px 6px; }}"
            f"QTreeWidget::item:selected {{"
            f"  background: {PALETTE['accent_soft']};"
            f"  color: {PALETTE['text']};"
            f"}}"
        )
        self.tree.setMinimumWidth(240)

        # ── Right: text browser ────────────────────────────────────
        self.body = QTextBrowser()
        self.body.setOpenExternalLinks(True)
        self.body.setStyleSheet(
            f"QTextBrowser {{"
            f"  background: {PALETTE['surface']};"
            f"  border: none;"
            f"  padding: 28px 36px;"
            f"  font-family: {FONT_UI}; font-size: 11pt;"
            f"  color: {PALETTE['text']};"
            f"}}"
        )

        split.addWidget(self.tree)
        split.addWidget(self.body)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([260, 900])

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(split)

        self._topics: dict[str, str] = {}
        self._populate()
        self.tree.currentItemChanged.connect(self._on_select)

        # Pick the welcome topic by default
        first = self.tree.topLevelItem(0)
        if first is not None:
            self.tree.setCurrentItem(first)

    # ──────────────────────────────────────────────────────────
    def _populate(self) -> None:
        def _add(parent, label, html_key):
            it = QTreeWidgetItem([label])
            it.setData(0, Qt.ItemDataRole.UserRole, html_key)
            if parent is None:
                self.tree.addTopLevelItem(it)
            else:
                parent.addChild(it)
            return it

        _add(None, "Welcome", "welcome")

        quick = _add(None, "Quick-start", None)
        _add(quick, "Launching Kerma", "quick_launch")
        _add(quick, "Your first notebook", "quick_notebook")
        _add(quick, "Your first calculation", "quick_calc")

        nb = _add(None, "Notebook", None)
        _add(nb, "Cell types", "nb_cells")
        _add(nb, "Math syntax (:=, expressions)", "nb_math")
        _add(nb, "Using units (pint)", "nb_units")
        _add(nb, "Variables pane", "nb_variables")
        _add(nb, "Saving & exporting", "nb_exports")

        facade = _add(None, "Facade · K.*", None)
        _add(facade, "Decay & activity", "f_decay")
        _add(facade, "Shielding & attenuation", "f_shield")
        _add(facade, "Dose & exposure", "f_dose")
        _add(facade, "Nuclide lookups", "f_nuclide")

        stats = _add(None, "Statistics", None)
        _add(stats, "Counting (Poisson, binomial)", "st_count")
        _add(stats, "Detection limits (L_C, L_D, MDA)", "st_det")
        _add(stats, "Goodness-of-fit · t-tests", "st_tests")
        _add(stats, "Propagation of uncertainty", "st_unc")
        _add(stats, "Control charts & calibration", "st_cal")

        eqs = _add(None, "Equation catalog", "eq_index")
        for cat in categories():
            _add(eqs, cat, f"eq_cat::{cat}")

        repl = _add(None, "REPL", None)
        _add(repl, "Commands & magics", "repl_magics")
        _add(repl, "Short names in scope", "repl_names")

        misc = _add(None, "Reference", None)
        _add(misc, "Keyboard shortcuts", "kb")
        _add(misc, "Troubleshooting", "trouble")
        _add(misc, "Changelog", "changelog")
        _add(misc, "License & data sources", "license")

        # preload every static topic — category topics are generated lazily.
        self._topics.update(_build_topic_map())

    # ──────────────────────────────────────────────────────────
    def _on_select(self, cur, _prev):
        if cur is None:
            return
        key = cur.data(0, Qt.ItemDataRole.UserRole)
        if key is None:
            # group heading — render a simple intro from its children
            html = "<h1>{}</h1><p>Select a topic on the left.</p>".format(cur.text(0))
            self.body.setHtml(_wrap(html))
            return
        if key.startswith("eq_cat::"):
            self.body.setHtml(_wrap(_render_equation_category(key.split("::", 1)[1])))
            return
        if key == "eq_index":
            self.body.setHtml(_wrap(_render_equation_index()))
            return
        html = self._topics.get(key, f"<h1>{cur.text(0)}</h1><p>TODO.</p>")
        self.body.setHtml(_wrap(html))


# ════════════════════════════════════════════════════════════════════
#  Static topic HTML
# ════════════════════════════════════════════════════════════════════
def _wrap(inner: str) -> str:
    return (
        "<html><head><style>"
        f"h1 {{ color:{PALETTE['text']}; font-weight:300; font-size:22pt;"
        f" border-bottom:1px solid {PALETTE['border']}; padding-bottom:6px;}}"
        f"h2 {{ color:{PALETTE['text']}; font-size:14pt; font-weight:600;"
        f" margin-top:22px; }}"
        f"h3 {{ color:{PALETTE['text_muted']}; font-size:11pt;"
        f" font-weight:600; text-transform:uppercase; letter-spacing:1px;"
        f" margin-top:16px; }}"
        f"p, li {{ color:{PALETTE['text']}; font-size:11pt; line-height:150%; }}"
        f"code {{ background:{PALETTE['surface_alt']}; color:{PALETTE['text']};"
        f" font-family:{FONT_MONO}; font-size:10.5pt; padding:1px 5px;"
        f" border-radius:2px; }}"
        f"pre {{ background:{PALETTE['surface_alt']}; color:{PALETTE['text']};"
        f" font-family:{FONT_MONO}; font-size:10pt; padding:10px 14px;"
        f" border-left:3px solid {PALETTE['accent']}; white-space:pre-wrap; }}"
        f"table {{ border-collapse:collapse; margin:10px 0; }}"
        f"th, td {{ border-bottom:1px solid {PALETTE['border']};"
        f" padding:5px 14px; text-align:left; font-size:10.5pt; }}"
        f"th {{ color:{PALETTE['text_muted']}; font-weight:600;"
        f" text-transform:uppercase; font-size:9.5pt; letter-spacing:.5px; }}"
        f"kbd {{ background:{PALETTE['surface_alt']};"
        f" border:1px solid {PALETTE['border']}; border-radius:3px;"
        f" padding:1px 6px; font-family:{FONT_MONO}; font-size:10pt; }}"
        f"a {{ color:{PALETTE['accent']}; }}"
        "</style></head><body>"
        + inner +
        "</body></html>"
    )


def _render_equation_index() -> str:
    out = ["<h1>Equation catalog</h1>",
           f"<p>The library ships with <b>{len(LIBRARY)}</b> equations "
           "across the following categories. Pick one from the tree for "
           "details, or use <code>Kerma.eq('<i>key</i>')</code> in the "
           "notebook / REPL.</p>",
           "<ul>"]
    for cat in categories():
        n = sum(1 for e in LIBRARY.values() if e.category == cat)
        out.append(f"<li><b>{cat}</b> — {n} equations</li>")
    out.append("</ul>")
    return "".join(out)


def _render_equation_category(cat: str) -> str:
    items = [e for e in LIBRARY.values() if e.category == cat]
    out = [f"<h1>{cat}</h1>"]
    for e in sorted(items, key=lambda x: x.name):
        out.append(f"<h2>{e.name} <code>{e.key}</code></h2>")
        out.append(f"<p>{e.description}</p>")
        out.append(f"<pre>{e.latex}</pre>")
        if e.variables:
            out.append("<h3>Variables</h3><table>")
            out.append("<tr><th>Name</th><th>Unit hint</th></tr>")
            for name, unit in e.variables.items():
                out.append(f"<tr><td><code>{name}</code></td><td>{unit}</td></tr>")
            out.append("</table>")
        if e.snippet:
            out.append(f"<h3>Snippet</h3><pre>{e.snippet}</pre>")
    return "".join(out)


def _build_topic_map() -> dict[str, str]:
    T: dict[str, str] = {}

    T["welcome"] = f"""
    <h1>Welcome to Kerma v{__version__}</h1>
    <p><b>Kerma</b> is a MathCad-style notebook plus a REPL plus a GUI
    lab for health-physics and nuclear-engineering calculations.</p>
    <p>The left-hand tree covers everything in a few clicks:</p>
    <ul>
      <li><b>Quick-start</b> — launch and first calculation</li>
      <li><b>Notebook</b> — math / Python / text cells, exports</li>
      <li><b>Facade</b> — the short <code>K.*</code> methods</li>
      <li><b>Statistics</b> — counting, MDA, t-tests, propagation</li>
      <li><b>Equation catalog</b> — every formula in the library</li>
      <li><b>REPL</b> — magic commands and in-scope names</li>
    </ul>
    <p>If something feels wrong, check
    <a href="#">Troubleshooting</a> first.</p>
    """

    T["quick_launch"] = """
    <h1>Launching Kerma</h1>
    <h3>GUI</h3>
    <pre>python -m kerma2.gui</pre>
    <h3>REPL</h3>
    <pre>python -m kerma2.repl</pre>
    <h3>From Python</h3>
    <pre>from kerma2 import Kerma
K = Kerma
K.t12('Cs-137')                                 # 9.49e8 s
K.hvl('Pb', energy_MeV=0.662)                   # half-value layer
K.dose('Cs-137', activity_Bq=37e9,
        distance_cm=100,
        layers=[('Pb', 2)])                      # shielded dose rate</pre>
    """

    T["quick_notebook"] = """
    <h1>Your first notebook</h1>
    <ol>
      <li>Open the GUI and stay on the <b>Notebook</b> tab.</li>
      <li>Click <kbd>+ Math</kbd> and type <code>E := 0.662</code>.</li>
      <li>Click <kbd>+ Math</kbd> and type <code>K.hvl('Pb', E)</code>.</li>
      <li>Hit <kbd>Run All</kbd>.</li>
      <li>Use <kbd>Export ▾</kbd> to save as <code>.py</code>,
          <code>.docx</code>, <code>.md</code>, <code>.html</code>
          or <code>.tex</code>.</li>
    </ol>
    """

    T["quick_calc"] = """
    <h1>Your first calculation</h1>
    <p>Dose-rate 1&nbsp;m from a 37&nbsp;GBq Cs-137 source behind 2&nbsp;cm of lead:</p>
    <pre>K.dose('Cs-137',
       activity_Bq=37e9,
       distance_cm=100,
       layers=[('Pb', 2)])
# → ~312 µSv/h</pre>
    <p>This calls the shielding engine with G-P buildup, looks up μ for
    lead at 662 keV, and formats the result as an equivalent-dose rate.</p>
    """

    T["nb_cells"] = """
    <h1>Cell types</h1>
    <table>
      <tr><th>Kind</th><th>Purpose</th><th>Syntax</th></tr>
      <tr><td><b>Math</b></td>
          <td>Readable formula + auto-print result</td>
          <td><code>E := 0.662</code> or bare expr</td></tr>
      <tr><td><b>Python</b></td>
          <td>Anything goes — full Python 3</td>
          <td><code>for i in range(3): print(i)</code></td></tr>
      <tr><td><b>Text</b></td>
          <td>Markdown-style prose / notes</td>
          <td>Free form</td></tr>
    </table>
    """

    T["nb_math"] = """
    <h1>Math syntax</h1>
    <h3>Assignment</h3>
    <pre>x := 5
y := sqrt(x) + pi</pre>
    <h3>Display expression</h3>
    <p>Any bare expression auto-prints its value:</p>
    <pre>K.t12('Cs-137') / 86400  # half-life in days</pre>
    <h3>Available names</h3>
    <p><code>K / Kerma</code>, <code>pi e sqrt exp log sin cos tan</code>,
    <code>math</code>, <code>np</code>, <code>sp</code> (SymPy),
    <code>ureg</code>, <code>stats</code>, every value you have assigned.</p>
    """

    T["nb_units"] = """
    <h1>Units (pint)</h1>
    <p>The <code>ureg</code> registry is pre-loaded with radiation units
    (<code>Ci</code>, <code>R</code>, <code>rem</code>, <code>rad</code>).</p>
    <pre>A = 5 * ureg.Ci
A.to('Bq')            # → 1.85e11 Bq
(1 * ureg.R).to('mGy')  # free-air kerma approx</pre>
    """

    T["nb_variables"] = """
    <h1>Variables pane</h1>
    <p>The right-hand pane lists every user-defined symbol with its
    value and type. Double-click any variable to insert it into the
    current math cell.</p>
    """

    T["nb_exports"] = """
    <h1>Saving & exporting</h1>
    <p>Notebooks live in <code>.kmd</code> files (plain JSON).
    Click <kbd>Export ▾</kbd> to write:</p>
    <ul>
      <li><code>.py</code> — runnable script with <code>from kerma2 import Kerma</code></li>
      <li><code>.docx</code> — Word document with centred math, code and results</li>
      <li><code>.md</code> — Markdown with $$LaTeX$$ blocks</li>
      <li><code>.html</code> — self-contained page with MathJax rendering</li>
      <li><code>.tex</code> — LaTeX <code>article</code> fragment</li>
    </ul>
    """

    T["f_decay"] = """
    <h1>Decay & activity</h1>
    <pre>K.t12('Cs-137')                        # half-life (s)
K.lam('Cs-137')                        # λ (1/s)
K.A(A0=1e10, t=3600, nuclide='Tc-99m') # activity after time
K.emissions('Co-60')                   # principal γ lines
K.branches('Sr-90')                    # decay branches</pre>
    """

    T["f_shield"] = """
    <h1>Shielding</h1>
    <pre>K.mu('Pb', 0.662)                   # μ/ρ (cm²/g)
K.mu_lin('Pb', 0.662)               # μ linear (1/cm)
K.hvl('Pb', energy_MeV=0.662)       # HVL (cm)
K.tvl('Pb', energy_MeV=0.662)       # TVL (cm)
K.material('Concrete')              # composition lookup</pre>
    """

    T["f_dose"] = """
    <h1>Dose & exposure</h1>
    <pre>K.gamma('Cs-137')                   # specific γ-ray constant
K.gamma_dose('Cs-137', activity_Ci=1, distance_m=1)
K.dose('Co-60', activity_Bq=1e10,
       distance_cm=100, layers=[('Pb', 3)])</pre>
    """

    T["f_nuclide"] = """
    <h1>Nuclide lookups</h1>
    <pre>K.nuclide('Tc-99m')      # full record
K.rho('Aluminum')        # density (g/cm³)
K.const.N_A              # Avogadro's number</pre>
    """

    T["st_count"] = """
    <h1>Counting statistics</h1>
    <pre>import kerma2.statistics as st
st.poisson_ci(12)                     # exact Garwood CI
st.poisson_test(obs=15, expected=9)
st.binomial_ci(successes=3, n=20)     # Wilson-score default</pre>
    """

    T["st_det"] = """
    <h1>Detection limits</h1>
    <pre>import kerma2.statistics as st
st.currie_limits(background_counts=100)
st.mda(background_cpm=30, count_time_min=5, efficiency=0.15, yield_=0.85)
st.iso11929_decision_threshold(100)</pre>
    """

    T["st_tests"] = """
    <h1>GoF & t-tests</h1>
    <pre>st.chi2_gof([98, 102, 99, 101, 100])
st.one_sample_t(data, mu0=0)
st.two_sample_t(a, b, equal_var=False)   # Welch
st.paired_t(before, after)</pre>
    """

    T["st_unc"] = """
    <h1>Propagation of uncertainty</h1>
    <pre>st.combine_uncertainty(0.02, 0.03, 0.01)     # quadrature
st.propagate_ratio(num=1200, u_num=35, den=60, u_den=1)
st.propagate_product([0.02, 0.03, 0.01])     # relative</pre>
    """

    T["st_cal"] = """
    <h1>Control charts & calibration</h1>
    <pre>st.shewhart_limits(counts)
st.poisson_limits(mean_counts=100)
fit = st.linear_fit(x=concentrations, y=responses)
fit.slope, fit.intercept, fit.r_squared
fit.inverse(y=350)           # unknowns from calibration</pre>
    """

    T["repl_magics"] = """
    <h1>REPL magic commands</h1>
    <table>
      <tr><th>Command</th><th>What it does</th></tr>
      <tr><td><code>help</code></td><td>Show magic-command list</td></tr>
      <tr><td><code>gui</code></td><td>Launch the notebook window</td></tr>
      <tr><td><code>notebook</code>, <code>nb</code></td><td>New in-REPL notebook</td></tr>
      <tr><td><code>dsl</code></td><td>Switch to the legacy Kerma DSL</td></tr>
      <tr><td><code>exit</code>, <code>quit</code></td><td>Leave</td></tr>
    </table>
    """

    T["repl_names"] = """
    <h1>Names preloaded in the REPL</h1>
    <p><code>K / Kerma</code>, <code>mu, mu_en, mu_lin, t12, lam, A,
    emissions, branches, hvl, tvl, rho, gamma, gamma_dose, dose, eq,
    eqs, const</code>, and the usual <code>math / numpy / sympy / pint</code>
    stack.</p>
    """

    T["kb"] = """
    <h1>Keyboard shortcuts</h1>
    <table>
      <tr><th>Shortcut</th><th>Action</th></tr>
      <tr><td><kbd>Shift</kbd>+<kbd>Enter</kbd></td><td>Run current cell</td></tr>
      <tr><td><kbd>Ctrl</kbd>+<kbd>Enter</kbd></td><td>Run all cells</td></tr>
      <tr><td><kbd>Ctrl</kbd>+<kbd>S</kbd></td><td>Save notebook</td></tr>
      <tr><td><kbd>Ctrl</kbd>+<kbd>O</kbd></td><td>Open notebook</td></tr>
      <tr><td><kbd>Ctrl</kbd>+<kbd>M</kbd></td><td>New math cell</td></tr>
      <tr><td><kbd>Ctrl</kbd>+<kbd>Y</kbd></td><td>New Python cell</td></tr>
      <tr><td><kbd>Ctrl</kbd>+<kbd>T</kbd></td><td>New text cell</td></tr>
    </table>
    """

    T["trouble"] = """
    <h1>Troubleshooting</h1>
    <h2>“Unknown nuclide: Cs-137”</h2>
    <p>The local SQLite cache is corrupt. Delete
    <code>kerma2/data/nuclear.db</code> and relaunch — it auto-seeds.</p>
    <h2>Math cells render as raw text</h2>
    <p>matplotlib is required for LaTeX rendering. Install with
    <code>pip install matplotlib</code>.</p>
    <h2>.docx export fails</h2>
    <p><code>pip install python-docx</code>.</p>
    <h2>Nothing happens after Run All</h2>
    <p>Open the Python cell showing the red border — its traceback
    will be printed underneath.</p>
    """

    T["changelog"] = f"""
    <h1>Changelog</h1>
    <h2>v{__version__} “Becquerel” · 2026-04</h2>
    <ul>
      <li>New <b>statistics</b> module: Poisson/binomial CIs, Currie &amp;
          MARLAP &amp; ISO 11929 detection limits, χ² goodness-of-fit,
          t-tests (one-sample, Welch, paired), propagation of uncertainty,
          Shewhart / Poisson control charts, linear calibration fits.</li>
      <li>Equation library expanded: Klein–Nishina, Compton scatter,
          pair threshold, bremsstrahlung yield, Katz–Penfold β range,
          neutron moderation / kerma, reactor kinetics (reactivity,
          period, inhour), rectangle solid angle, dead-time corrections.</li>
      <li>Nuclide database expanded from ~32 to 100+ entries
          (PET/therapy, fission products, NORM chain, actinides, reactor
          activation).</li>
      <li>New exporters: <code>to_html</code> (MathJax) and
          <code>to_latex</code>.</li>
      <li>Fixed: About-page styling issues; Python-script export now
          preserves assignment order.</li>
      <li>New <b>Help</b> tab with full command reference, equation
          catalog, keyboard shortcuts, and troubleshooting.</li>
    </ul>
    <h2>v2.0.0</h2>
    <ul>
      <li>MathCad-style notebook; LaTeX rendering; .kmd save/load;
          .py/.docx/.md exports; REPL preloading.</li>
    </ul>
    """

    T["license"] = """
    <h1>License & data sources</h1>
    <p>© 2026 Kerma Project. Distributed AS-IS.</p>
    <p>Bundled numerical data derive from publicly released reference
    compilations:</p>
    <ul>
      <li>ICRP Publications 103, 107, 116, 119</li>
      <li>NIST XCOM photon cross-section database</li>
      <li>ANSI/ANS-6.4.3 G-P buildup factors</li>
      <li>FGR 11-13 dose conversion factors</li>
      <li>MARLAP (2004) · ISO 11929 (2019)</li>
    </ul>
    """

    return T
