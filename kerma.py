#!/usr/bin/env python3
"""
Kerma REPL
==========
Interactive shell for the Kerma physics DSL.

Usage:
    python kerma.py              # interactive REPL (VM backend)
    python kerma.py script.krm   # run a file
    python kerma.py -e "5 MeV"   # evaluate expression
    python kerma.py --interp     # use tree-walker backend instead of VM
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lexer import lex, LexerError, TokenType
from parser import parse, ParseError
from interpreter import Interpreter, RuntimeError as KermaError
from units import REGISTRY, Constants, DimensionError

UNIT_SYMS = set(REGISTRY._units.keys())
CONST_NAMES = {a for a in dir(Constants) if not a.startswith('_')}

BANNER = """\033[1;36m
  ╦╔═┌─┐┬─┐┌┬┐┌─┐
  ╠╩╗├┤ ├┬┘│││├─┤
  ╩ ╩└─┘┴└─┴ ┴┴ ┴\033[0m
  \033[90mA physics DSL · v0.1\033[0m
  \033[90mType expressions, assignments, or 'help' for usage.\033[0m
  \033[90mCtrl+D or 'exit' to quit.\033[0m
"""

HELP_TEXT = """
\033[1mKerma Quick Reference\033[0m

  \033[1;33mUnits\033[0m         5 MeV, 30 cm, 100 keV, 585 barn
  \033[1;33mConvert\033[0m       5 MeV | eV          or  E.to(keV)
  \033[1;33mConstants\033[0m     c, h, hbar, k_B, N_A, e, m_e, m_p, m_n
  \033[1;33mMath\033[0m          exp, log, sqrt, sin, cos, tan, abs, pi
  \033[1;33mVariables\033[0m     E = 5 MeV
  \033[1;33mFunctions\033[0m     def f(x):
                      return x * 2
  \033[1;33mControl\033[0m       if/elif/else, while, for ... in range(n)
  \033[1;33mPrint\033[0m         print E | keV
  \033[1;33mLists\033[0m         v = [1, 2, 3]

  \033[1;36mExample:\033[0m
    E = m_e * c**2
    print E | MeV          \033[90m# → 0.510999 MeV\033[0m
"""


def run_repl(use_vm: bool = True):
    backend = "vm" if use_vm else "interp"
    print(BANNER)
    if use_vm:
        from vm import VM
        interp = VM()
    else:
        interp = Interpreter()
    buffer = []
    indent_depth = 0

    while True:
        try:
            prompt = "\033[1;36m>>>\033[0m " if not buffer else "\033[1;36m...\033[0m "
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print("\n\033[90mGoodbye.\033[0m")
            break

        stripped = line.strip()
        if stripped in ('exit', 'quit'):
            print("\033[90mGoodbye.\033[0m")
            break
        if stripped == 'help':
            print(HELP_TEXT)
            continue
        if stripped == '':
            if buffer:
                indent_depth = 0
                source = '\n'.join(buffer)
                buffer.clear()
                _execute(interp, source, use_vm=use_vm)
            continue

        buffer.append(line)

        if stripped.endswith(':'):
            indent_depth += 1
            continue
        if indent_depth > 0:
            if line.startswith(' ') or line.startswith('\t'):
                continue
            else:
                indent_depth = 0
                source = '\n'.join(buffer)
                buffer.clear()
                _execute(interp, source, use_vm=use_vm)
                continue

        source = '\n'.join(buffer)
        buffer.clear()
        _execute(interp, source, use_vm=use_vm)


def _execute(interp, source: str, use_vm: bool = False):
    try:
        tokens = lex(source, UNIT_SYMS, CONST_NAMES)
        program = parse(tokens)

        if use_vm:
            from compiler import compile_program
            code = compile_program(program)
            result = interp.execute(code)
        else:
            result = interp.run(program)

        # Auto-display last expression result (if not None and not a print)
        if result is not None:
            from ast_nodes import ExprStatement, PrintStatement
            last = program.body[-1] if program.body else None
            if isinstance(last, ExprStatement):
                fmt = interp._format_value(result)
                print(f"\033[32m{fmt}\033[0m")
    except LexerError as e:
        print(f"\033[31mLexer error: {e}\033[0m")
    except ParseError as e:
        print(f"\033[31mParse error: {e}\033[0m")
    except KermaError as e:
        print(f"\033[31mRuntime error: {e}\033[0m")
    except DimensionError as e:
        print(f"\033[31mDimension error: {e}\033[0m")
    except NameError as e:
        print(f"\033[31mName error: {e}\033[0m")
    except Exception as e:
        print(f"\033[31mError: {type(e).__name__}: {e}\033[0m")


def run_file(path: str, use_vm: bool = True):
    with open(path) as f:
        source = f.read()
    try:
        tokens = lex(source, UNIT_SYMS, CONST_NAMES)
        program = parse(tokens)
        if use_vm:
            from compiler import compile_program
            from vm import VM
            code = compile_program(program)
            VM().execute(code)
        else:
            Interpreter().run(program)
    except (LexerError, ParseError, KermaError, DimensionError, NameError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def run_expr(expr: str, use_vm: bool = True):
    try:
        tokens = lex(expr, UNIT_SYMS, CONST_NAMES)
        program = parse(tokens)
        if use_vm:
            from compiler import compile_program
            from vm import VM
            code = compile_program(program)
            vm = VM()
            result = vm.execute(code)
            if result is not None:
                print(vm._format_value(result))
        else:
            interp = Interpreter()
            result = interp.run(program)
            if result is not None:
                print(interp._format_value(result))
    except (LexerError, ParseError, KermaError, DimensionError, NameError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    use_interp = '--interp' in sys.argv
    args = [a for a in sys.argv[1:] if a != '--interp']

    if not args:
        run_repl(use_vm=not use_interp)
    elif args[0] == '-e' and len(args) > 1:
        run_expr(' '.join(args[1:]), use_vm=not use_interp)
    elif args[0] in ('-h', '--help'):
        print(__doc__)
    else:
        run_file(args[0], use_vm=not use_interp)
