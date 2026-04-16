"""
Kerma Python REPL — pre-loaded with the shortest-path HP functions.

Differences from the legacy Kerma-DSL shell (`kerma.py`):
  * Runs on Python syntax (code.InteractiveConsole).
  * Pre-loads:
      - K, Kerma        facade (short + long forms)
      - mu, mu_en, t12, lam, hvl, tvl, gamma, dose, activity  (top-level)
      - const           constants namespace
      - eq, eqs         equations library
      - np, sp, ureg, Q_, plt, math functions
  * Magic commands: help, gui, notebook, dsl, exit
"""
from __future__ import annotations

import code
import sys
from typing import Dict

from ..logo import BANNER, TAGLINE


_HELP = """
\033[1mKerma Quick Reference\033[0m

  \033[1;33mAttenuation\033[0m    mu("Pb", 0.662)              # mu/rho for Lead at 662 keV
                 mu_en("Pb", 0.662)           # mu_en/rho
                 hvl("Pb")                     # half-value layer  [cm]
                 tvl("Pb")                     # tenth-value layer [cm]
                 rho("Lead")                   # density g/cm^3

  \033[1;33mDecay\033[0m          t12("Cs-137")                 # half-life (s)
                 lam("Cs-137")                 # decay constant
                 activity(A0=1e9, t=3600, nuclide="Tc-99m")
                 emissions("Co-60")

  \033[1;33mDose\033[0m           gamma("Cs-137")               # Γ (R·m²/Ci·hr)
                 gamma_dose("Cs-137", activity_Ci=1, distance_m=1)
                 dose("Cs-137", activity_Bq=3.7e10, distance_cm=100,
                      layers=[("Pb", 2.0)])

  \033[1;33mEquations\033[0m      eqs()                         # all equations
                 eqs("Shielding")              # category
                 eq("activity").latex          # a specific one

  \033[1;33mConstants\033[0m      const.c, const.N_A, const.Ci
                 const.gamma("Cs-137"), const.hvl("Lead")

  \033[1;33mUnits\033[0m          5 * MeV, (10 * mCi).to(GBq)   # pint scope

  \033[1;36mCommands\033[0m       notebook  — launch the MathCad-style notebook GUI
                 gui       — launch the main GUI window
                 dsl       — drop to the legacy Kerma-DSL shell
                 help      — this message
                 exit      — quit
"""


def _build_namespace() -> Dict:
    ns: Dict = {}

    # ── Kerma facade ────────────────────────────────────────────────
    from kerma2 import Kerma
    ns["Kerma"] = Kerma
    ns["K"] = Kerma

    # ── top-level shortcuts (typing less is the whole point) ────────
    ns["mu"]         = Kerma.mu
    ns["mu_en"]      = Kerma.mu_en
    ns["mu_lin"]     = Kerma.mu_lin
    ns["t12"]        = Kerma.t12
    ns["lam"]        = Kerma.lam
    ns["activity"]   = Kerma.A
    ns["emissions"]  = Kerma.emissions
    ns["branches"]   = Kerma.branches
    ns["hvl"]        = Kerma.hvl
    ns["tvl"]        = Kerma.tvl
    ns["rho"]        = Kerma.rho
    ns["gamma"]      = Kerma.gamma
    ns["gamma_dose"] = Kerma.gamma_dose
    ns["dose"]       = Kerma.dose
    ns["eq"]         = Kerma.eq
    ns["eqs"]        = Kerma.eqs
    ns["const"]      = Kerma.const

    # ── math ────────────────────────────────────────────────────────
    import math
    for f in ("pi", "e", "sqrt", "exp", "log", "log10",
              "sin", "cos", "tan", "asin", "acos", "atan"):
        ns[f] = getattr(math, f)
    ns["ln"] = math.log

    # ── sci stack ───────────────────────────────────────────────────
    try:
        import numpy as np
        ns["np"] = np
    except ImportError:
        pass
    try:
        import sympy as sp
        ns["sp"] = sp
    except ImportError:
        pass
    try:
        import pint
        ureg = pint.UnitRegistry()
        for defn in ("roentgen = 2.58e-4 C/kg = R",
                     "rem = 1e-2 Sv",
                     "curie = 3.7e10 becquerel = Ci"):
            try:
                ureg.define(defn)
            except Exception:
                pass
        ns["ureg"] = ureg
        ns["Q_"] = ureg.Quantity
        for u in ("Bq", "MBq", "GBq", "Ci", "mCi", "uCi",
                  "Sv", "mSv", "uSv", "Gy", "rad", "rem",
                  "eV", "keV", "MeV",
                  "m", "cm", "mm", "hour", "day", "year"):
            try: ns[u] = ureg(u).units
            except Exception: pass
    except ImportError:
        pass
    try:
        import matplotlib.pyplot as plt
        ns["plt"] = plt
    except ImportError:
        pass

    return ns


class _KermaConsole(code.InteractiveConsole):
    """Adds the `gui`, `notebook`, `dsl`, `help`, `exit` magic commands."""

    MAGIC = {"help", "gui", "notebook", "nb", "dsl", "exit", "quit"}

    def push(self, line):
        stripped = line.strip()
        if stripped in self.MAGIC:
            if stripped == "help":
                print(_HELP); return False
            if stripped in ("exit", "quit"):
                raise SystemExit(0)
            if stripped == "gui":
                print("\033[90mLaunching GUI ...\033[0m")
                from ..gui.app import launch_gui
                launch_gui(); return False
            if stripped in ("notebook", "nb"):
                print("\033[90mLaunching notebook (GUI) ...\033[0m")
                from ..gui.app import launch_gui
                launch_gui(); return False
            if stripped == "dsl":
                print("\033[90mDropping to Kerma-DSL shell (Ctrl+D to return).\033[0m")
                import kerma as legacy_kerma
                legacy_kerma.run_repl(use_vm=True); return False
        return super().push(line)


def run_enhanced_repl() -> None:
    ns = _build_namespace()
    console = _KermaConsole(locals=ns)
    sys.ps1 = "\033[1;36mkerma›\033[0m "
    sys.ps2 = "\033[1;36m    ›\033[0m "
    banner = (
        BANNER
        + f"  \033[90mPython {sys.version.split()[0]}  ·  "
        + "mu, t12, lam, dose, hvl, gamma, eqs, const ready in scope\033[0m\n"
        + "  \033[90mType  help  for a quick reference  ·  "
        + "notebook  for the GUI notebook\033[0m\n"
    )
    try:
        console.interact(banner=banner, exitmsg="\033[90mGoodbye.\033[0m")
    except SystemExit:
        pass
