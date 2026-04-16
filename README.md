```
  ╦╔═┌─┐┬─┐┌┬┐┌─┐
  ╠╩╗├┤ ├┬┘│││├─┤
  ╩ ╩└─┘┴└─┴ ┴┴ ┴
```

# Kerma v3.0 "Becquerel"

**A Health Physics & Nuclear Engineering toolkit for Python.**

Kerma provides a unified environment for radiation shielding design, decay-chain analysis, dose-rate calculations, and radiation-counting statistics -- all backed by published nuclear data (ICRP 107, NIST XCOM, ANSI/ANS-6.4.3, EPA FGR 11/12/13). It ships as a single package with no external data files: run the installer once and compute offline forever.

Three ways to work:

- **Enhanced Python REPL** -- pre-loaded with health-physics functions, constants, and unit support
- **Nordic Light GUI** -- a PyQt6 interface with a MathCad-style notebook, shielding lab, decay explorer, and data browser
- **Scripting** -- import `kerma2` from any Python script or Jupyter notebook

---

## Quick Start

### Requirements

- Python 3.10+
- Windows, macOS, or Linux

### Installation

```bash
git clone https://github.com/<your-drgtheneutrino>/Kerma.git
cd Kerma
python setup_kerma.py
```

The setup script will install all dependencies, pre-build the nuclear data warehouse, and create launcher scripts. On Windows it drops two double-clickable `.bat` files.

### Launch

```bash
python kerma_app.py           # Enhanced Python REPL (default)
python kerma_app.py --gui     # Nordic Light GUI
python kerma_app.py --dsl     # Legacy Kerma-DSL REPL
python kerma_app.py -c "K.hvl('Pb')"   # One-liner evaluation
python kerma_app.py script.py           # Run a script with Kerma in scope
```

On Windows, double-click `Kerma_GUI.bat` or `Kerma_REPL.bat`.

---

## Features

### Facade API

The `Kerma` singleton (aliased as `K`) provides short, memorable commands for interactive use:

```python
from kerma2 import Kerma as K

K.mu("Pb", 0.662)             # Mass-attenuation coefficient for lead at 662 keV
K.t12("Cs-137")               # Half-life in seconds
K.lam("Co-60")                # Decay constant (1/s)
K.hvl("Pb")                   # Half-value layer at 662 keV
K.gamma("Cs-137")             # Specific gamma-ray constant

K.A(A0=1e9, t=3600, nuclide="Tc-99m")   # Activity after 1 hour

K.dose("Cs-137",              # Multi-layer dose rate (uSv/h)
       activity_Bq=3.7e10,
       distance_cm=100,
       layers=[("Pb", 2.0)])

K.emissions("Co-60")          # Photon emissions per decay
K.branches("Co-60")           # Decay branching ratios
K.material("Lead")            # Material properties (density, composition)
K.eq("activity")              # Look up a health-physics equation
K.const.c                     # Speed of light (CODATA 2018)
```

### Shielding Lab

Multi-layer photon attenuation using point-isotropic geometry, NIST XCOM cross-sections, and ANSI/ANS-6.4.3 Geometric-Progression buildup factors. Handles per-emission-line breakdown with optical thickness and returns total dose rate at the receptor.

```python
from kerma2.physics import ShieldingLab, Layer

lab = ShieldingLab()
result = lab.dose_rate(
    nuclide="Co-60",
    activity_Bq=3.7e10,
    distance_cm=100,
    layers=[Layer("Pb", 5.0), Layer("Concrete", 30.0)]
)
print(result.total_uSv_h)
```

### Decay Chain Solver

Solves the Bateman equations for arbitrary parent-to-daughter decay chains, handling branching fractions and degenerate decay constants:

```python
from kerma2.physics import DecayChain, solve_bateman
import numpy as np

chain = DecayChain("Mo-99", max_depth=3)
t = np.linspace(0, 7 * 86400, 500)
result = solve_bateman(chain, A0_Bq=1e12, t_array_s=t)
```

### Dosimetry

Dose conversion factor lookups spanning FGR 11/12/13 and ICRP 116/119 for inhalation, ingestion, submersion, ground exposure, and water immersion across multiple age groups:

```python
from kerma2.physics import Dosimetry

d = Dosimetry()
dcf = d.lookup("Cs-137", pathway="inhalation", age_group="adult")
```

### Counting Statistics

Self-contained statistics module (no SciPy required) implementing Currie critical levels, MARLAP detection limits, chi-squared tests, and control chart utilities:

```python
from kerma2 import statistics as st

result = st.currie(gross=150, background=120, t_s=60, t_b=60)
print(result.Lc, result.Ld, result.mda_Bq)
```

### Equations Library

Pre-built symbolic equations with LaTeX rendering (via SymPy) and callable solvers covering decay, shielding, dosimetry, geometry, and statistics:

```python
eq = K.eq("inverse_square")
print(eq.latex)        # LaTeX string
print(eq.solve(...))   # Numerical result
```

### MathCad-Style Notebook

Create documents mixing math, Python, and text cells in a shared namespace. Math cells use `:=` for assignment and render LaTeX alongside numerical output:

```
A0 := 3.7e10
t  := 30 * year
A  = A0 * exp(-ln(2)/T12 * t)
```

Export to Python (`.py`), Markdown, Word (`.docx`), HTML (with MathJax), or LaTeX.

### Nuclear Data Warehouse

An embedded SQLite database with 8 tables covering nuclide properties, decay branches, photon emissions, material cross-sections, buildup-factor coefficients, and dose conversion factors. Thread-safe, lazily seeded on first use, works offline.

### Constants & Regulatory Limits

Pre-loaded CODATA 2018 fundamental constants, unit conversion factors (Ci/Bq, Sv/rem, Gy/rad), specific gamma-ray constants for 24 common nuclides, half-value layers for standard energies, and 10 CFR 20 / ICRP 103 occupational and public dose limits.

---

## Project Structure

```
Kerma/
├── kerma_app.py                 # Unified CLI entry point
├── setup_kerma.py               # One-command installer
├── kerma.py                     # Legacy Kerma-DSL REPL (preserved)
│
├── kerma2/                      # Main package (v3.0)
│   ├── __init__.py              # Public API: Kerma, statistics
│   ├── facade.py                # High-level Kerma() singleton
│   ├── constants.py             # CODATA 2018, HVL tables, regulatory limits
│   ├── equations.py             # Symbolic equation library
│   ├── statistics.py            # Counting statistics & detection limits
│   ├── logo.py                  # ASCII banner
│   │
│   ├── data/                    # Nuclear data warehouse
│   │   ├── databridge.py        # Thread-safe SQLite accessor
│   │   ├── _interp.py           # Log-log & log-linear interpolation
│   │   └── schema.sql           # 8 tables, 15+ indices
│   │
│   ├── physics/                 # Calculation engines
│   │   ├── shielding.py         # G-P buildup, multi-layer attenuation
│   │   ├── decay.py             # Bateman equation solver
│   │   └── dosimetry.py         # Dose conversion factor lookups
│   │
│   ├── gui/                     # PyQt6 "Nordic Light" interface
│   │   ├── app.py               # Application launcher
│   │   ├── main_window.py       # Sidebar navigation + stacked views
│   │   ├── theme.py             # Overleaf-inspired stylesheet
│   │   └── views/               # Modular view panels
│   │       ├── notebook_view.py # 3-pane notebook (equations, cells, variables)
│   │       ├── shielding_view.py
│   │       ├── decay_view.py
│   │       ├── data_browser_view.py
│   │       ├── help_view.py
│   │       └── about_view.py
│   │
│   ├── notebook/                # MathCad-style notebook engine
│   │   ├── engine.py            # Cell evaluator
│   │   ├── cell.py              # Cell dataclass (math / python / text)
│   │   └── export.py            # Export to .py, .md, .docx, .html, .tex
│   │
│   ├── repl/                    # Enhanced Python REPL
│   │   └── kerma_shell.py       # Pre-loaded interactive console
│   │
│   └── tests/                   # Test suite (pytest)
│       ├── test_databridge.py
│       ├── test_equations.py
│       ├── test_statistics.py
│       └── ...
│
├── lexer.py, parser.py, ...     # Legacy DSL modules
└── Examples/                    # Sample .krm scripts
```

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| PyQt6 | >= 6.5, < 7 | GUI framework |
| matplotlib | >= 3.7 | LaTeX rendering in notebook cells |
| numpy | >= 1.24 | Numerical computation |
| sympy | >= 1.12 | Symbolic mathematics |
| pint | >= 0.22 | Physical unit tracking & conversion |
| python-docx | >= 1.0 | Word document export |
| pytest | >= 7.4 | Test suite |

The REPL and scripting modes degrade gracefully when optional dependencies are missing. Only the standard library is strictly required for core calculations.

---

## Data Sources

Kerma's embedded nuclear data warehouse draws from:

- **ICRP 107** -- Nuclear decay data (half-lives, emissions, branching ratios)
- **NIST XCOM** -- Photon cross-sections and mass-attenuation coefficients
- **ANSI/ANS-6.4.3** -- Geometric-Progression buildup-factor coefficients
- **EPA FGR 11/12/13** -- Federal Guidance Report dose conversion factors
- **ICRP 116/119** -- Updated dose coefficients
- **CODATA 2018** -- Fundamental physical constants

All data is embedded in Python seed functions and compiled into a local SQLite database at first launch. No internet connection is needed after setup.

---

## Running Tests

```bash
pytest kerma2/tests/ -v
```

---

## License

See [LICENSE](LICENSE) for details.
