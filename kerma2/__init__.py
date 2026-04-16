"""
Kerma V3 — Health Physics & Nuclear Engineering Toolkit
========================================================
A hybrid REPL + GUI environment for radiation shielding, decay-chain
analysis, dose-rate calculations, and radiation-counting statistics.

Public API:
    from kerma2 import Kerma          # facade for data/calculations
    from kerma2 import statistics     # radiation-statistics library
    from kerma2.logo import BANNER    # preserved ASCII logo
"""

from .facade import Kerma
from . import statistics  # re-exported for convenience

__all__ = ["Kerma", "statistics"]
__version__ = "3.0.0"
__release__ = "2026.04"
__codename__ = "Becquerel"
