#!/usr/bin/env python3
"""
Kerma — unified application entry point.

Usage
-----
    python kerma_app.py                     # enhanced Python REPL (default)
    python kerma_app.py --gui               # launch the Nordic Light GUI
    python kerma_app.py --dsl               # legacy Kerma-DSL REPL
    python kerma_app.py --rebuild-db        # force-rebuild the data warehouse
    python kerma_app.py -c "EXPR"           # evaluate a Python expression
    python kerma_app.py path/to/script.py   # run a Python script with Kerma in scope

The old `kerma.py` entry point is untouched — invoking it still works
exactly as before. This new entry just layers the v2 capabilities on top.
"""

from __future__ import annotations

import argparse
import os
import sys

# Make sibling modules importable regardless of the working directory
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kerma", description="Kerma — Health Physics & Nuclear Engineering toolkit")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--gui", action="store_true",
                      help="launch the Nordic Light PyQt6 GUI")
    mode.add_argument("--dsl", action="store_true",
                      help="drop into the legacy Kerma-DSL REPL")
    mode.add_argument("--repl", action="store_true",
                      help="enhanced Python REPL (default)")
    p.add_argument("-c", "--command", metavar="EXPR",
                   help="evaluate one Python expression and exit")
    p.add_argument("--rebuild-db", action="store_true",
                   help="drop and re-seed the nuclear data warehouse")
    p.add_argument("--no-banner", action="store_true",
                   help="suppress the logo (for piping output)")
    p.add_argument("script", nargs="?",
                   help="optional Python script path to execute")
    return p


def _maybe_rebuild_db() -> None:
    from kerma2.data import DataBridge
    print("Rebuilding nuclear data warehouse ...")
    db = DataBridge()
    db.rebuild(verbose=True)
    print(f"✓ DB at {db.db_path}")


def _run_command(expr: str) -> int:
    # small, self-contained eval namespace
    from kerma2 import Kerma
    ns = {"Kerma": Kerma, "K": Kerma}
    try:
        import numpy as np; ns["np"] = np
    except ImportError:
        pass
    try:
        import pint; ns["ureg"] = pint.UnitRegistry()
    except ImportError:
        pass
    try:
        result = eval(expr, ns)
        if result is not None:
            print(result)
    except SyntaxError:
        exec(expr, ns)
    return 0


def _run_script(path: str) -> int:
    from kerma2 import Kerma
    ns = {"__name__": "__main__", "Kerma": Kerma, "K": Kerma}
    with open(path, encoding="utf-8") as f:
        src = f.read()
    code = compile(src, path, "exec")
    exec(code, ns)
    return 0


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)

    if args.rebuild_db:
        _maybe_rebuild_db()
        if not (args.gui or args.dsl or args.script or args.command):
            return 0

    if args.script:
        return _run_script(args.script)

    if args.command:
        return _run_command(args.command)

    if args.gui:
        from kerma2.gui import launch_gui
        return launch_gui()

    if args.dsl:
        # the legacy REPL is the preserved kerma.py
        import kerma as legacy
        legacy.run_repl(use_vm=True)
        return 0

    # default: enhanced Python REPL
    from kerma2.repl import run_enhanced_repl
    run_enhanced_repl()
    return 0


if __name__ == "__main__":
    sys.exit(main())
