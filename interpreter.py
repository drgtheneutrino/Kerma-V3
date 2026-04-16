"""
Kerma Interpreter
=================
Tree-walking interpreter that executes AST nodes directly.
Bridges AST nodes to the Quantity/unit system for physics-aware computation.
"""

from __future__ import annotations
import math
from typing import Any, Optional

from ast_nodes import *
from units import Quantity, REGISTRY, Constants, DimensionError
from units import exp as q_exp, log as q_log, sqrt as q_sqrt
from units import sin as q_sin, cos as q_cos, tan as q_tan
from linalg import Vec, Mat
from linalg import dot as la_dot, cross as la_cross, norm as la_norm
from linalg import transpose as la_transpose, det as la_det, inv as la_inv
from linalg import solve as la_solve, eye as la_eye
from symbolic import (Expr as SymExpr, Sym as SymVar, Const as SymConst,
                       Add as SymAdd, Mul as SymMul, Pow as SymPow, Func as SymFunc,
                       sym, diff as sym_diff, simplify as sym_simplify,
                       expand as sym_expand, subs as sym_subs,
                       integrate as sym_integrate, sym_solve)


# ─── Environment (scope chain) ──────────────────────────────────────────────

class Environment:
    """Variable scope with parent chain for lexical scoping."""

    def __init__(self, parent: Optional[Environment] = None):
        self.parent = parent
        self.vars: dict[str, Any] = {}

    def get(self, name: str) -> Any:
        if name in self.vars:
            return self.vars[name]
        if self.parent:
            return self.parent.get(name)
        raise NameError(f"Undefined variable: '{name}'")

    def set(self, name: str, value: Any):
        self.vars[name] = value

    def update(self, name: str, value: Any):
        """Update existing variable, walking up scope chain."""
        if name in self.vars:
            self.vars[name] = value
            return
        if self.parent:
            self.parent.update(name, value)
            return
        # If not found anywhere, set in current scope
        self.vars[name] = value


class ReturnSignal(Exception):
    """Used to unwind the call stack on return."""
    def __init__(self, value: Any):
        self.value = value


class KermaFunction:
    """A user-defined function."""
    def __init__(self, name: str, params: list[str], body: list[Node], closure: Environment):
        self.name = name
        self.params = params
        self.body = body
        self.closure = closure

    def __repr__(self):
        return f"<fn {self.name}({', '.join(self.params)})>"


class RuntimeError(Exception):
    def __init__(self, message: str, node: Node = None):
        self.node = node
        loc = f"Line {node.line}: " if node else ""
        super().__init__(f"{loc}{message}")


# ─── Interpreter ─────────────────────────────────────────────────────────────

class Interpreter:
    """
    Executes a Kerma AST.

    Usage:
        interp = Interpreter()
        interp.run(program)
    """

    def __init__(self, output_fn=None):
        self.global_env = Environment()
        self.output_fn = output_fn or print
        self.output_log: list[str] = []
        self._setup_builtins()

    def _setup_builtins(self):
        """Register built-in constants and functions."""
        env = self.global_env

        # Physical constants
        for name in ('c', 'h', 'hbar', 'k_B', 'N_A', 'e', 'm_e', 'm_p', 'm_n',
                      'sigma', 'eps_0', 'mu_0'):
            env.set(name, getattr(Constants, name))

        # Math functions (dispatch: symbolic if Expr arg, otherwise unit-aware)
        def _math_dispatch(name, numeric_fn):
            def wrapper(x):
                if isinstance(x, SymExpr):
                    return SymFunc(name, x)
                return numeric_fn(x)
            return wrapper

        env.set('exp', _math_dispatch('exp', q_exp))
        env.set('log', _math_dispatch('ln', q_log))
        env.set('sqrt', _math_dispatch('sqrt', q_sqrt))
        env.set('sin', _math_dispatch('sin', q_sin))
        env.set('cos', _math_dispatch('cos', q_cos))
        env.set('tan', _math_dispatch('tan', q_tan))
        env.set('abs', lambda x: abs(x) if isinstance(x, (Quantity, SymExpr)) else Quantity(abs(x)))
        env.set('pi', Quantity(math.pi))
        env.set('ln', _math_dispatch('ln', q_log))

        env.set('range', lambda n: range(int(n.value) if isinstance(n, Quantity) else int(n)))

        # List operations
        env.set('len', len)
        env.set('sum', self._builtin_sum)
        env.set('min', min)
        env.set('max', max)

        # Linear algebra
        env.set('dot', la_dot)
        env.set('cross', la_cross)
        env.set('norm', la_norm)
        env.set('transpose', la_transpose)
        env.set('det', la_det)
        env.set('inv', la_inv)
        env.set('linsolve', la_solve)
        env.set('eye', la_eye)
        env.set('Vec', Vec)
        env.set('Mat', Mat)

        # Symbolic
        env.set('sym', sym)
        env.set('diff', self._builtin_diff)
        env.set('simplify', sym_simplify)
        env.set('expand', sym_expand)
        env.set('subs', sym_subs)
        env.set('integrate', sym_integrate)
        env.set('solve', self._builtin_solve)

    def _builtin_sum(self, items):
        result = items[0]
        for item in items[1:]:
            result = result + item
        return result

    def _builtin_diff(self, expr, var, *args):
        """diff(expr, var) — symbolic differentiation."""
        if isinstance(var, SymExpr):
            return sym_diff(expr, var)
        # If var is a string, make it a Sym
        if isinstance(var, str):
            return sym_diff(expr, SymVar(var))
        raise RuntimeError(f"diff expects a symbolic variable, got {type(var).__name__}")

    def _builtin_solve(self, *args):
        """Dispatches between linalg solve (Mat, Vec) and symbolic solve (Expr, Sym)."""
        if len(args) == 2:
            a, b = args
            # Matrix solve: linsolve(A, b)
            if isinstance(a, Mat) and isinstance(b, Vec):
                return la_solve(a, b)
            # Symbolic solve: solve(expr, var)
            if isinstance(a, SymExpr) and isinstance(b, SymExpr):
                roots = sym_solve(a, b)
                if len(roots) == 1:
                    return roots[0]
                return roots
        raise RuntimeError(f"solve() expects (Expr, Sym) or (Mat, Vec)")

    # ── Run ──────────────────────────────────────────────────────────────

    def run(self, program: Program) -> Any:
        """Execute a program and return the last expression value."""
        result = None
        for stmt in program.body:
            result = self._exec(stmt, self.global_env)
        return result

    # ── Statement execution ──────────────────────────────────────────────

    def _exec(self, node: Node, env: Environment) -> Any:
        if isinstance(node, Assignment):
            return self._exec_assignment(node, env)
        if isinstance(node, AugAssignment):
            return self._exec_aug_assignment(node, env)
        if isinstance(node, ExprStatement):
            return self._eval(node.expr, env)
        if isinstance(node, PrintStatement):
            return self._exec_print(node, env)
        if isinstance(node, IfStatement):
            return self._exec_if(node, env)
        if isinstance(node, WhileStatement):
            return self._exec_while(node, env)
        if isinstance(node, ForStatement):
            return self._exec_for(node, env)
        if isinstance(node, FuncDef):
            return self._exec_funcdef(node, env)
        if isinstance(node, Return):
            value = self._eval(node.value, env) if node.value else None
            raise ReturnSignal(value)
        raise RuntimeError(f"Unknown statement type: {type(node).__name__}", node)

    def _exec_assignment(self, node: Assignment, env: Environment):
        value = self._eval(node.value, env)
        env.set(node.target, value)
        return value

    def _exec_aug_assignment(self, node: AugAssignment, env: Environment):
        current = env.get(node.target)
        rhs = self._eval(node.value, env)
        ops = {'+': lambda a, b: a + b, '-': lambda a, b: a - b,
               '*': lambda a, b: a * b, '/': lambda a, b: a / b}
        result = ops[node.op](current, rhs)
        env.update(node.target, result)
        return result

    def _exec_print(self, node: PrintStatement, env: Environment):
        value = self._eval(node.value, env)
        text = self._format_value(value)
        self.output_fn(text)
        self.output_log.append(text)
        return value

    def _exec_if(self, node: IfStatement, env: Environment):
        if self._truthy(self._eval(node.condition, env)):
            return self._exec_block(node.body, env)
        for cond, body in node.elif_clauses:
            if self._truthy(self._eval(cond, env)):
                return self._exec_block(body, env)
        if node.else_body:
            return self._exec_block(node.else_body, env)
        return None

    def _exec_while(self, node: WhileStatement, env: Environment):
        result = None
        iterations = 0
        max_iter = 100_000
        while self._truthy(self._eval(node.condition, env)):
            result = self._exec_block(node.body, env)
            iterations += 1
            if iterations > max_iter:
                raise RuntimeError(f"While loop exceeded {max_iter} iterations", node)
        return result

    def _exec_for(self, node: ForStatement, env: Environment):
        iterable = self._eval(node.iterable, env)
        result = None
        for item in iterable:
            env.set(node.var, item)
            result = self._exec_block(node.body, env)
        return result

    def _exec_funcdef(self, node: FuncDef, env: Environment):
        func = KermaFunction(node.name, node.params, node.body, env)
        env.set(node.name, func)
        return func

    def _exec_block(self, stmts: list[Node], env: Environment) -> Any:
        result = None
        for stmt in stmts:
            result = self._exec(stmt, env)
        return result

    # ── Expression evaluation ────────────────────────────────────────────

    def _eval(self, node: Node, env: Environment) -> Any:
        if isinstance(node, NumberLiteral):
            return Quantity(node.value)
        if isinstance(node, StringLiteral):
            return node.value
        if isinstance(node, BoolLiteral):
            return node.value
        if isinstance(node, NoneLiteral):
            return None
        if isinstance(node, Identifier):
            return env.get(node.name)
        if isinstance(node, ConstantRef):
            return env.get(node.name)
        if isinstance(node, UnitLiteral):
            # If a variable with this name exists, use it (e.g. user assigned m = 2 kg)
            try:
                return env.get(node.symbol)
            except NameError:
                return self._resolve_unit(node)
        if isinstance(node, UnitAttach):
            return self._eval_unit_attach(node, env)
        if isinstance(node, BinOp):
            return self._eval_binop(node, env)
        if isinstance(node, UnaryOp):
            return self._eval_unary(node, env)
        if isinstance(node, Compare):
            return self._eval_compare(node, env)
        if isinstance(node, BoolOp):
            return self._eval_boolop(node, env)
        if isinstance(node, Call):
            return self._eval_call(node, env)
        if isinstance(node, Index):
            return self._eval_index(node, env)
        if isinstance(node, Attribute):
            return self._eval_attribute(node, env)
        if isinstance(node, ListLiteral):
            elements = [self._eval(e, env) for e in node.elements]
            return self._maybe_promote(elements)
        if isinstance(node, PipeConvert):
            return self._eval_pipe(node, env)
        raise RuntimeError(f"Unknown expression type: {type(node).__name__}", node)

    def _maybe_promote(self, elements: list) -> Any:
        """Promote a list to Vec or Mat if all elements are numeric/Quantity."""
        if not elements:
            return elements
        # Check for nested lists → Mat
        if all(isinstance(e, (list, Vec)) for e in elements):
            # Nested list or list of Vecs → try Mat
            try:
                if isinstance(elements[0], Vec):
                    rows = [v._data for v in elements]
                    dim = elements[0].dim
                    for v in elements[1:]:
                        if v.dim != dim:
                            return elements  # mixed dims, stay as list
                    import numpy as np
                    return Mat(np.array(rows), dim, elements[0]._unit_hint)
                else:
                    # Nested plain lists — promote inner lists first
                    inner = [self._maybe_promote(e) if isinstance(e, list) else e for e in elements]
                    if all(isinstance(v, Vec) for v in inner):
                        return self._maybe_promote(inner)
                    return inner
            except Exception:
                return elements
        # Check for all Quantities → Vec
        if all(isinstance(e, Quantity) for e in elements):
            try:
                return Vec.from_quantities(elements)
            except DimensionError:
                return elements  # mixed dims, stay as list
        return elements

    def _eval_unit_attach(self, node: UnitAttach, env: Environment) -> Any:
        """Evaluate value and attach a unit: 5 MeV → Quantity(5, MeV)."""
        value = self._eval(node.value, env)
        unit = self._resolve_unit(node.unit)

        if isinstance(value, (list, Vec)):
            # Vector with unit: [1, 2, 3] m → Vec with unit
            if isinstance(value, Vec):
                elements = value._data
            else:
                elements = [v.value if isinstance(v, Quantity) else float(v) for v in value]
            quantities = [self._attach_single(Quantity(v) if not isinstance(v, Quantity) else v, unit, node)
                          for v in (elements if isinstance(elements, list) else elements.tolist())]
            return Vec.from_quantities(quantities)
        return self._attach_single(value, unit, node)

    def _attach_single(self, value: Any, unit: Any, node: Node) -> Quantity:
        """Attach a unit to a single value. Value is in the given unit; store as SI internally."""
        if isinstance(value, Quantity):
            val = value.value  # already SI if dimensionless
        elif isinstance(value, (int, float)):
            val = float(value)
        else:
            raise RuntimeError(f"Cannot attach unit to {type(value).__name__}", node)

        if isinstance(unit, Quantity):
            # Compound unit result (e.g. m/s): unit is Quantity(1_SI, dim)
            # val is in compound-unit scale, multiply by the SI factor
            return Quantity(val * unit.value, unit.dim, unit._unit_hint)
        elif hasattr(unit, 'to_si'):
            # Unit object from registry
            return Quantity(val * unit.to_si, unit.dim, unit.symbol)
        else:
            raise RuntimeError(f"Invalid unit: {unit}", node)

    def _resolve_unit(self, node: Node) -> Any:
        """Resolve a unit expression to a Unit object or compound Quantity."""
        if isinstance(node, UnitLiteral):
            return REGISTRY.get(node.symbol)
        if isinstance(node, BinOp):
            left = self._resolve_unit(node.left)
            right = self._resolve_unit(node.right)
            # Convert units to Quantity(1, unit) for arithmetic
            lq = Quantity(1.0, left.dim, left.symbol) if hasattr(left, 'dim') else left
            rq = Quantity(1.0, right.dim, right.symbol) if hasattr(right, 'dim') else right
            if node.op == '/':
                return lq / rq
            elif node.op == '*':
                return lq * rq
            elif node.op == '**':
                if isinstance(right, Quantity):
                    return lq ** right.value
                return lq ** right
        raise RuntimeError(f"Cannot resolve unit from {type(node).__name__}")

    def _eval_binop(self, node: BinOp, env: Environment) -> Any:
        left = self._eval(node.left, env)
        right = self._eval(node.right, env)
        # If either operand is symbolic, coerce the other
        if isinstance(left, SymExpr) or isinstance(right, SymExpr):
            from symbolic import _wrap as sym_wrap
            if not isinstance(left, SymExpr):
                left = sym_wrap(left)
            if not isinstance(right, SymExpr):
                right = sym_wrap(right)
        try:
            if node.op == '+':
                return left + right
            if node.op == '-':
                return left - right
            if node.op == '*':
                return left * right
            if node.op == '/':
                return left / right
            if node.op == '%':
                if isinstance(left, Quantity) and isinstance(right, Quantity):
                    return Quantity(left.value % right.value, left.dim, left._unit_hint)
                return left % right
            if node.op == '**':
                if isinstance(right, Quantity):
                    return left ** right.value
                return left ** right
        except DimensionError as e:
            raise RuntimeError(str(e), node)
        raise RuntimeError(f"Unknown operator: {node.op}", node)

    def _eval_unary(self, node: UnaryOp, env: Environment) -> Any:
        operand = self._eval(node.operand, env)
        if node.op == '-':
            return -operand
        if node.op == 'not':
            return not self._truthy(operand)
        raise RuntimeError(f"Unknown unary operator: {node.op}", node)

    def _eval_compare(self, node: Compare, env: Environment) -> bool:
        values = [self._eval(o, env) for o in node.operands]
        for i, op in enumerate(node.ops):
            a, b = values[i], values[i + 1]
            try:
                if op == '==' and not (a == b): return False
                if op == '!=' and not (a != b): return False
                if op == '<'  and not (a < b):  return False
                if op == '>'  and not (a > b):  return False
                if op == '<=' and not (a <= b): return False
                if op == '>=' and not (a >= b): return False
            except DimensionError as e:
                raise RuntimeError(str(e), node)
        return True

    def _eval_boolop(self, node: BoolOp, env: Environment) -> Any:
        left = self._eval(node.left, env)
        if node.op == 'and':
            return self._eval(node.right, env) if self._truthy(left) else left
        if node.op == 'or':
            return left if self._truthy(left) else self._eval(node.right, env)

    def _eval_call(self, node: Call, env: Environment) -> Any:
        func = self._eval(node.func, env)
        args = [self._eval(a, env) for a in node.args]

        # Built-in callable
        if callable(func) and not isinstance(func, KermaFunction):
            try:
                return func(*args)
            except (DimensionError, TypeError, ValueError) as e:
                raise RuntimeError(str(e), node)

        # User-defined function
        if isinstance(func, KermaFunction):
            if len(args) != len(func.params):
                raise RuntimeError(
                    f"{func.name}() expects {len(func.params)} args, got {len(args)}", node)
            call_env = Environment(parent=func.closure)
            for pname, arg in zip(func.params, args):
                call_env.set(pname, arg)
            try:
                self._exec_block(func.body, call_env)
                return None  # no explicit return
            except ReturnSignal as ret:
                return ret.value

        raise RuntimeError(f"'{func}' is not callable", node)

    def _eval_index(self, node: Index, env: Environment) -> Any:
        obj = self._eval(node.obj, env)
        idx = self._eval(node.index, env)
        if isinstance(idx, Quantity):
            idx = int(idx.value)
        try:
            return obj[idx]
        except (IndexError, KeyError, TypeError) as e:
            raise RuntimeError(str(e), node)

    def _eval_attribute(self, node: Attribute, env: Environment) -> Any:
        obj = self._eval(node.obj, env)

        # .to(unit) — unit conversion
        if node.attr == 'to' and isinstance(obj, Quantity):
            def convert(target):
                if hasattr(target, 'symbol'):
                    return obj.to(target.symbol)
                elif isinstance(target, str):
                    return obj.to(target)
                raise RuntimeError(f"Invalid conversion target: {target}")
            return convert

        # .value — raw numerical value
        if node.attr == 'value' and isinstance(obj, Quantity):
            return Quantity(obj.value)

        # List methods
        if node.attr == 'append' and isinstance(obj, list):
            return obj.append

        # Generic attribute access
        if hasattr(obj, node.attr):
            return getattr(obj, node.attr)

        raise RuntimeError(f"'{type(obj).__name__}' has no attribute '{node.attr}'", node)

    def _eval_pipe(self, node: PipeConvert, env: Environment) -> Quantity:
        """Evaluate E | eV → E.to('eV')."""
        value = self._eval(node.value, env)
        if not isinstance(value, Quantity):
            raise RuntimeError(f"Cannot convert {type(value).__name__} with |", node)
        try:
            return value.to(node.target_unit)
        except (DimensionError, ValueError) as e:
            raise RuntimeError(str(e), node)

    # ── Helpers ──────────────────────────────────────────────────────────

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

    def _format_value(self, value: Any) -> str:
        from display import display
        return display(value)


# ─── Convenience ─────────────────────────────────────────────────────────────

def run_source(source: str, output_fn=None) -> Any:
    """Lex, parse, and interpret Kerma source code."""
    from lexer import lex
    from parser import parse

    unit_syms = set(REGISTRY._units.keys())
    const_names = {a for a in dir(Constants) if not a.startswith('_')}

    tokens = lex(source, unit_syms, const_names)
    program = parse(tokens)
    interp = Interpreter(output_fn=output_fn)
    return interp.run(program)
