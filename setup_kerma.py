"""
Kerma v3.0 — one-shot installer.

Run this from the project folder (the one that contains `kerma_app.py` and
the `kerma2/` package). It will:

  1. Confirm the Python version is recent enough.
  2. Upgrade pip.
  3. Install every runtime dependency (PyQt6, matplotlib, sympy, pint,
     numpy, python-docx, pytest).
  4. Pre-build the SQLite nuclear-data warehouse so the first GUI launch
     is instant.
  5. Drop two double-clickable launchers next to itself:
        Kerma_GUI.bat   — opens the PyQt6 main window
        Kerma_REPL.bat  — opens the enhanced Python REPL with Kerma loaded

Just run:
    python setup_kerma.py

No flags. No prior Python knowledge required beyond having Python installed.
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────
MIN_PY = (3, 10)

# Pinned to known-good major versions so a fresh install doesn't pick up
# a breaking PyQt or matplotlib release. Bump deliberately.
DEPS = [
    "PyQt6>=6.5,<7",
    "matplotlib>=3.7",
    "numpy>=1.24",
    "sympy>=1.12",
    "pint>=0.22",
    "python-docx>=1.0",
    "pytest>=7.4",
]

ROOT = Path(__file__).resolve().parent


# ── Pretty printing ──────────────────────────────────────────────
def _line(char: str = "─") -> str:
    return char * 64

def step(n: int, total: int, msg: str) -> None:
    print(f"\n[{n}/{total}] {msg}\n{_line()}")

def ok(msg: str) -> None:
    print(f"  OK   {msg}")

def warn(msg: str) -> None:
    print(f"  WARN {msg}")

def fail(msg: str) -> None:
    print(f"  FAIL {msg}")


# ── Steps ────────────────────────────────────────────────────────
def check_python() -> None:
    v = sys.version_info
    if v < MIN_PY:
        fail(f"Python {MIN_PY[0]}.{MIN_PY[1]}+ required, found "
             f"{v.major}.{v.minor}.{v.micro}")
        print("\n  Download a newer Python from https://www.python.org/downloads/")
        sys.exit(1)
    ok(f"Python {v.major}.{v.minor}.{v.micro} on "
       f"{platform.system()} {platform.release()}")


def upgrade_pip() -> None:
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "pip"]
    print("  $", " ".join(cmd))
    subprocess.check_call(cmd)
    ok("pip is up to date")


def install_deps() -> None:
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", *DEPS]
    print("  $", " ".join(cmd))
    subprocess.check_call(cmd)
    for d in DEPS:
        ok(d)


def build_warehouse() -> None:
    """Pre-build the SQLite data warehouse so first GUI launch is instant.
    Failures here are non-fatal; the GUI rebuilds it lazily on first run."""
    try:
        sys.path.insert(0, str(ROOT))
        from kerma2.data import DataBridge          # type: ignore
        bridge = DataBridge()
        # `rebuild` is idempotent — safe to run on a fresh or existing DB.
        bridge.rebuild()
        ok(f"Data warehouse ready ({bridge.db_path})")
    except Exception as e:
        warn(f"Warehouse pre-build skipped ({e.__class__.__name__}: {e})")
        warn("The GUI will rebuild it on first launch.")


def write_launchers() -> None:
    py = sys.executable                        # absolute path to current python
    here = str(ROOT)

    gui_bat = ROOT / "Kerma_GUI.bat"
    repl_bat = ROOT / "Kerma_REPL.bat"

    gui_contents = (
        "@echo off\r\n"
        f'cd /d "{here}"\r\n'
        f'"{py}" kerma_app.py --gui\r\n'
        "if errorlevel 1 pause\r\n"
    )
    repl_contents = (
        "@echo off\r\n"
        f'cd /d "{here}"\r\n'
        f'"{py}" kerma_app.py\r\n'
        "if errorlevel 1 pause\r\n"
    )

    gui_bat.write_text(gui_contents, encoding="ascii")
    repl_bat.write_text(repl_contents, encoding="ascii")
    ok(f"Wrote {gui_bat.name}")
    ok(f"Wrote {repl_bat.name}")


def smoke_test_imports() -> None:
    """Try to import every dependency; surface failures clearly."""
    mods = ["PyQt6.QtWidgets", "matplotlib", "numpy", "sympy", "pint", "docx"]
    failed = []
    for m in mods:
        try:
            __import__(m)
            ok(f"import {m}")
        except Exception as e:
            failed.append((m, e))
            fail(f"import {m}  ->  {e.__class__.__name__}: {e}")
    if failed:
        print("\n  Some dependencies failed to import. Re-run setup or "
              "install them manually with:")
        print(f"    {sys.executable} -m pip install " + " ".join(DEPS))
        sys.exit(2)


# ── Main ─────────────────────────────────────────────────────────
def main() -> int:
    print(_line("="))
    print("  Kerma v3.0 — installer")
    print(_line("="))

    if not (ROOT / "kerma_app.py").is_file():
        fail("setup_kerma.py must live next to kerma_app.py.")
        print(f"  Looked in: {ROOT}")
        return 1

    total = 6
    step(1, total, "Check Python version")
    check_python()

    step(2, total, "Upgrade pip")
    upgrade_pip()

    step(3, total, "Install Python dependencies")
    install_deps()

    step(4, total, "Verify imports")
    smoke_test_imports()

    step(5, total, "Pre-build nuclear-data warehouse")
    build_warehouse()

    step(6, total, "Write Windows launchers")
    write_launchers()

    print("\n" + _line("="))
    print("  Done.")
    print(_line("="))
    print("  Double-click  Kerma_GUI.bat   to launch the GUI.")
    print("  Double-click  Kerma_REPL.bat  to launch the REPL.")
    print()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as e:
        print(f"\n[!] Command failed (exit {e.returncode})")
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        print("\n[!] Interrupted")
        sys.exit(130)
