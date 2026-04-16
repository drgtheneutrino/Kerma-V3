"""
Kerma Virtual Machine
=====================
Stack-based VM that executes compiled bytecode.
Reuses the same runtime types (Quantity, Vec, Mat, SymExpr) as the tree-walker.
"""

from __future__ import annotations
import math
from typing import Any, Optional

from bytecode import Op, CodeObject
from units import Quantity, REGISTRY, Constants, DimensionError
from units import exp as q_exp, log as q_log, sqrt as q_sqrt
from units import sin as q_sin, cos as q_cos, tan as q_tan
from linalg import Vec, Mat
from linalg import dot as la_dot, cross as la_cross, norm as la_norm
from linalg import transpose as la_transpose, det as la_det, inv as la_inv
from linalg import solve as la_solve, eye as la_eye
from symbolic import (Expr as SymExpr, Sym as SymVar, Const as SymConst,
                       Func as SymFunc, _wrap as sym_wrap,
                       sym, diff as sym_diff, simplify as sym_simplify,
                       expand as sym_expand, subs as sym_subs,
                       integrate as sym_integrate, sym_solve)


class VMError(Exception):
    def __init__(self, message: str, ip: int = -1):
        self.ip = ip
        super().__init__(f"[ip={ip}] {message}" if ip >= 0 else message)


class CallFrame:
    """A single frame on the call stack."""
    __slots__ = ('code', 'ip', 'locals', 'stack_base')

    def __init__(self, code: CodeObject, stack_base: int):
        self.code = code
        self.ip = 0
        self.locals: dict[str, Any] = {}
        self.stack_base = stack_base


class VMFunction:
    """A compiled user-defined function."""
    __slots__ = ('code', 'closure')

    def __init__(self, code: CodeObject, closure: dict[str, Any]):
        self.code = code
        self.closure = closure

    def __repr__(self):
        return f"<fn {self.code.name}({', '.join(self.code.params)})>"


class VM:
    """
    Executes Kerma bytecode.

    Usage:
        vm = VM()
        result = vm.execute(code_object)
    """

    MAX_STACK = 10_000
    MAX_FRAMES = 256
    MAX_ITERATIONS = 1_000_000

    def __init__(self, output_fn=None):
        self.stack: list[Any] = []
        self.globals: dict[str, Any] = {}
        self.frames: list[CallFrame] = []
        self.output_fn = output_fn or print
        self.output_log: list[str] = []
        self._iteration_count = 0
        self._setup_builtins()

    def _setup_builtins(self):
        g = self.globals

        # Physical constants
        for name in ('c', 'h', 'hbar', 'k_B', 'N_A', 'e', 'm_e', 'm_p', 'm_n',
                      'sigma', 'eps_0', 'mu_0'):
            g[name] = getattr(Constants, name)

        # Math functions with symbolic dispatch
        def _math_dispatch(name, numeric_fn):
            def wrapper(x):
                if isinstance(x, SymExpr):
                    return SymFunc(name, x)
                return numeric_fn(x)
            return wrapper

        g['exp'] = _math_dispatch('exp', q_exp)
        g['log'] = _math_dispatch('ln', q_log)
        g['sqrt'] = _math_dispatch('sqrt', q_sqrt)
        g['sin'] = _math_dispatch('sin', q_sin)
        g['cos'] = _math_dispatch('cos', q_cos)
        g['tan'] = _math_dispatch('tan', q_tan)
        g['abs'] = lambda x: abs(x) if isinstance(x, (Quantity, SymExpr)) else Quantity(abs(x))
        g['pi'] = Quantity(math.pi)
        g['ln'] = _math_dispatch('ln', q_log)
        g['range'] = lambda n: range(int(n.value) if isinstance(n, Quantity) else int(n))
        g['len'] = len
        g['min'] = min
        g['max'] = max

        # Linear algebra
        g['dot'] = la_dot
        g['cross'] = la_cross
        g['norm'] = la_norm
        g['transpose'] = la_transpose
        g['det'] = la_det
        g['inv'] = la_inv
        g['linsolve'] = la_solve
        g['eye'] = la_eye
        g['Vec'] = Vec
        g['Mat'] = Mat

        # Symbolic
        g['sym'] = sym
        g['diff'] = self._builtin_diff
        g['simplify'] = sym_simplify
        g['expand'] = sym_expand
        g['subs'] = sym_subs
        g['integrate'] = sym_integrate
        g['solve'] = self._builtin_solve

    def _builtin_diff(self, expr, var, *args):
        if isinstance(var, SymExpr):
            return sym_diff(expr, var)
        if isinstance(var, str):
            return sym_diff(expr, SymVar(var))
        raise VMError(f"diff expects a symbolic variable, got {type(var).__name__}")

    def _builtin_solve(self, *args):
        if len(args) == 2:
            a, b = args
            if isinstance(a, Mat) and isinstance(b, Vec):
                return la_solve(a, b)
            if isinstance(a, SymExpr) and isinstance(b, SymExpr):
                roots = sym_solve(a, b)
                return roots[0] if len(roots) == 1 else roots
        raise VMError(f"solve() expects (Expr, Sym) or (Mat, Vec)")

    def _builtin_sum(self, items):
        result = items[0]
        for item in items[1:]:
            result = result + item
        return result

    # ── Execution ────────────────────────────────────────────────────────

    def execute(self, code: CodeObject) -> Any:
        """Execute a top-level code object and return the last value."""
        frame = CallFrame(code, len(self.stack))
        self.frames.append(frame)
        self._iteration_count = 0

        try:
            result = self._run()
        finally:
            if self.frames:
                self.frames.pop()

        return result

    def _run(self) -> Any:
        """Main execution loop."""
        while self.frames:
            frame = self.frames[-1]
            code = frame.code

            if frame.ip >= len(code.instructions):
                # Fell off the end — implicit return None
                self.frames.pop()
                if not self.frames:
                    return self.stack[-1] if self.stack else None
                continue

            op, arg = code.instructions[frame.ip]
            frame.ip += 1
            self._iteration_count += 1

            if self._iteration_count > self.MAX_ITERATIONS:
                raise VMError(f"Exceeded {self.MAX_ITERATIONS} instructions")

            # ── Dispatch ─────────────────────────────────────────────

            if op == Op.LOAD_CONST:
                self.stack.append(code.constants[arg])

            elif op == Op.LOAD_NAME:
                val = frame.locals.get(arg)
                if val is None and arg not in frame.locals:
                    val = self.globals.get(arg)
                    if val is None and arg not in self.globals:
                        raise VMError(f"Undefined variable: '{arg}'", frame.ip - 1)
                self.stack.append(val)

            elif op == Op.STORE_NAME:
                val = self.stack.pop()
                if self.frames and len(self.frames) > 1:
                    # Inside a function — store as local
                    frame.locals[arg] = val
                else:
                    self.globals[arg] = val
                    frame.locals[arg] = val

            elif op == Op.ADD:
                b, a = self.stack.pop(), self.stack.pop()
                a, b = self._coerce_sym(a, b)
                self.stack.append(a + b)

            elif op == Op.SUB:
                b, a = self.stack.pop(), self.stack.pop()
                a, b = self._coerce_sym(a, b)
                self.stack.append(a - b)

            elif op == Op.MUL:
                b, a = self.stack.pop(), self.stack.pop()
                a, b = self._coerce_sym(a, b)
                self.stack.append(a * b)

            elif op == Op.DIV:
                b, a = self.stack.pop(), self.stack.pop()
                a, b = self._coerce_sym(a, b)
                self.stack.append(a / b)

            elif op == Op.MOD:
                b, a = self.stack.pop(), self.stack.pop()
                if isinstance(a, Quantity) and isinstance(b, Quantity):
                    self.stack.append(Quantity(a.value % b.value, a.dim, a._unit_hint))
                else:
                    self.stack.append(a % b)

            elif op == Op.POW:
                b, a = self.stack.pop(), self.stack.pop()
                if isinstance(b, Quantity) and not isinstance(a, SymExpr):
                    self.stack.append(a ** b.value)
                else:
                    a, b = self._coerce_sym(a, b)
                    self.stack.append(a ** b)

            elif op == Op.NEG:
                self.stack.append(-self.stack.pop())

            elif op == Op.CMP_EQ:
                b, a = self.stack.pop(), self.stack.pop()
                self.stack.append(a == b)

            elif op == Op.CMP_NE:
                b, a = self.stack.pop(), self.stack.pop()
                self.stack.append(a != b)

            elif op == Op.CMP_LT:
                b, a = self.stack.pop(), self.stack.pop()
                self.stack.append(a < b)

            elif op == Op.CMP_GT:
                b, a = self.stack.pop(), self.stack.pop()
                self.stack.append(a > b)

            elif op == Op.CMP_LE:
                b, a = self.stack.pop(), self.stack.pop()
                self.stack.append(a <= b)

            elif op == Op.CMP_GE:
                b, a = self.stack.pop(), self.stack.pop()
                self.stack.append(a >= b)

            elif op == Op.BOOL_AND:
                b, a = self.stack.pop(), self.stack.pop()
                self.stack.append(b if self._truthy(a) else a)

            elif op == Op.BOOL_OR:
                b, a = self.stack.pop(), self.stack.pop()
                self.stack.append(a if self._truthy(a) else b)

            elif op == Op.BOOL_NOT:
                self.stack.append(not self._truthy(self.stack.pop()))

            elif op == Op.JUMP:
                frame.ip = arg

            elif op == Op.JUMP_IF_FALSE:
                if not self._truthy(self.stack.pop()):
                    frame.ip = arg

            elif op == Op.JUMP_IF_TRUE:
                if self._truthy(self.stack.pop()):
                    frame.ip = arg

            elif op == Op.CALL:
                nargs = arg
                args = [self.stack.pop() for _ in range(nargs)]
                args.reverse()
                func = self.stack.pop()

                if isinstance(func, VMFunction):
                    if len(args) != len(func.code.params):
                        raise VMError(f"{func.code.name}() expects {len(func.code.params)} args, got {len(args)}")
                    new_frame = CallFrame(func.code, len(self.stack))
                    # Set up locals with params and closure
                    new_frame.locals.update(func.closure)
                    for pname, aval in zip(func.code.params, args):
                        new_frame.locals[pname] = aval
                    # Allow recursion: function can call itself
                    new_frame.locals[func.code.name] = func
                    self.frames.append(new_frame)
                elif callable(func):
                    try:
                        result = func(*args)
                        self.stack.append(result)
                    except Exception as e:
                        raise VMError(str(e), frame.ip - 1)
                else:
                    raise VMError(f"'{func}' is not callable", frame.ip - 1)

            elif op == Op.RETURN:
                ret_val = self.stack.pop() if self.stack else None
                self.frames.pop()
                if self.frames:
                    self.stack.append(ret_val)
                else:
                    return ret_val

            elif op == Op.MAKE_FUNCTION:
                func_code = code.constants[arg]
                # Capture closure from current scope
                closure = dict(frame.locals)
                closure.update(self.globals)
                func = VMFunction(func_code, closure)
                self.stack.append(func)

            elif op == Op.BUILD_LIST:
                elements = [self.stack.pop() for _ in range(arg)]
                elements.reverse()
                self.stack.append(self._maybe_promote(elements))

            elif op == Op.INDEX:
                idx = self.stack.pop()
                obj = self.stack.pop()
                if isinstance(idx, Quantity):
                    idx = int(idx.value)
                self.stack.append(obj[idx])

            elif op == Op.LOAD_ATTR:
                obj = self.stack.pop()
                attr = arg
                if attr == 'to' and isinstance(obj, Quantity):
                    def convert(target):
                        if hasattr(target, 'symbol'):
                            return obj.to(target.symbol)
                        elif isinstance(target, str):
                            return obj.to(target)
                        raise VMError(f"Invalid conversion target: {target}")
                    self.stack.append(convert)
                elif attr == 'value' and isinstance(obj, Quantity):
                    self.stack.append(Quantity(obj.value))
                elif hasattr(obj, attr):
                    self.stack.append(getattr(obj, attr))
                else:
                    raise VMError(f"'{type(obj).__name__}' has no attribute '{attr}'")

            elif op == Op.ATTACH_UNIT:
                value = self.stack.pop()
                unit = self._resolve_unit_info(arg)
                self.stack.append(self._attach_unit(value, unit))

            elif op == Op.PIPE_CONVERT:
                value = self.stack.pop()
                if not isinstance(value, Quantity):
                    raise VMError(f"Cannot convert {type(value).__name__} with |")
                self.stack.append(value.to(arg))

            elif op == Op.RESOLVE_UNIT:
                # Bare unit token — check variable first, then unit registry
                if arg in frame.locals:
                    self.stack.append(frame.locals[arg])
                elif arg in self.globals:
                    self.stack.append(self.globals[arg])
                else:
                    self.stack.append(REGISTRY.get(arg))

            elif op == Op.PRINT:
                val = self.stack.pop()
                text = self._format_value(val)
                self.output_fn(text)
                self.output_log.append(text)

            elif op == Op.POP:
                if self.stack:
                    self.stack.pop()

            elif op == Op.DUP:
                self.stack.append(self.stack[-1])

            elif op == Op.NOP:
                pass

            else:
                raise VMError(f"Unknown opcode: {op}", frame.ip - 1)

        return self.stack[-1] if self.stack else None

    # ── Helpers ──────────────────────────────────────────────────────────

    def _coerce_sym(self, a, b):
        """If either is symbolic, coerce the other."""
        if isinstance(a, SymExpr) or isinstance(b, SymExpr):
            if not isinstance(a, SymExpr):
                a = sym_wrap(a)
            if not isinstance(b, SymExpr):
                b = sym_wrap(b)
        return a, b

    def _truthy(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, Quantity):
            return value.value != 0
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return len(value) > 0
        if isinstance(value, list):
            return len(value) > 0
        return True

    def _resolve_unit_info(self, info) -> Any:
        """Resolve compiled unit info to a Unit or compound Quantity."""
        if isinstance(info, tuple):
            kind = info[0]
            if kind == 'unit':
                return REGISTRY.get(info[1])
            if kind == 'compound':
                op, left_info, right_info = info[1], info[2], info[3]
                left = self._resolve_unit_info(left_info)
                right = self._resolve_unit_info(right_info)
                lq = Quantity(1.0, left.dim, left.symbol) if hasattr(left, 'dim') else left
                rq = Quantity(1.0, right.dim, right.symbol) if hasattr(right, 'dim') else right
                if op == '/':
                    return lq / rq
                elif op == '*':
                    return lq * rq
        return info

    def _attach_unit(self, value: Any, unit: Any) -> Any:
        """Attach a unit to a value or list of values."""
        if isinstance(value, (list, Vec)):
            elements = value._data.tolist() if isinstance(value, Vec) else \
                       [v.value if isinstance(v, Quantity) else float(v) for v in value]
            quantities = [self._attach_single(v, unit) for v in elements]
            return Vec.from_quantities(quantities)
        return self._attach_single(value, unit)

    def _attach_single(self, value: Any, unit: Any) -> Quantity:
        if isinstance(value, Quantity):
            val = value.value
        elif isinstance(value, (int, float)):
            val = float(value)
        else:
            raise VMError(f"Cannot attach unit to {type(value).__name__}")

        if isinstance(unit, Quantity):
            return Quantity(val * unit.value, unit.dim, unit._unit_hint)
        elif hasattr(unit, 'to_si'):
            return Quantity(val * unit.to_si, unit.dim, unit.symbol)
        else:
            raise VMError(f"Invalid unit: {unit}")

    def _maybe_promote(self, elements: list) -> Any:
        if not elements:
            return elements
        if all(isinstance(e, (list, Vec)) for e in elements):
            try:
                if isinstance(elements[0], Vec):
                    import numpy as np
                    dim = elements[0].dim
                    if all(isinstance(v, Vec) and v.dim == dim for v in elements):
                        rows = [v._data for v in elements]
                        return Mat(np.array(rows), dim, elements[0]._unit_hint)
                return elements
            except Exception:
                return elements
        # Promote all-numeric (float/int/Quantity) to Vec
        if all(isinstance(e, (Quantity, int, float)) for e in elements):
            quantities = [e if isinstance(e, Quantity) else Quantity(float(e)) for e in elements]
            try:
                return Vec.from_quantities(quantities)
            except DimensionError:
                return elements
        return elements

    def _format_value(self, value: Any) -> str:
        from display import display
        return display(value)


# ─── Convenience ─────────────────────────────────────────────────────────────

def vm_run_source(source: str, output_fn=None) -> Any:
    """Lex, parse, compile, and execute Kerma source code via the VM."""
    from lexer import lex
    from parser import parse
    from compiler import compile_program

    unit_syms = set(REGISTRY._units.keys())
    const_names = {a for a in dir(Constants) if not a.startswith('_')}

    tokens = lex(source, unit_syms, const_names)
    program = parse(tokens)
    code = compile_program(program)
    vm = VM(output_fn=output_fn)
    return vm.execute(code)
