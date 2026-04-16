"""
Kerma Symbolic Engine
=====================
Expression tree representation with:
  - Differentiation (diff)
  - Simplification (simplify)
  - Substitution (subs)
  - Expansion (expand)
  - Basic integration (integrate)
  - Symbolic solve for linear/quadratic (solve)

Expressions are built from Sym (variable), Const (number), and composite nodes
(Add, Mul, Pow, Func). They support Python operators so you can write:

    x = Sym('x')
    f = x**2 + 3*x + 2
    df = f.diff(x)          # → 2*x + 3
    f.subs(x, 5)            # → Const(42)
"""

from __future__ import annotations
import math
from typing import Union, Optional
from functools import reduce


# ─── Base expression ─────────────────────────────────────────────────────────

class Expr:
    """Base class for all symbolic expressions."""

    def diff(self, var: Sym) -> Expr:
        raise NotImplementedError

    def subs(self, var: Sym, value: Expr) -> Expr:
        raise NotImplementedError

    def simplify(self) -> Expr:
        return self

    def expand(self) -> Expr:
        return self

    def eval(self) -> float:
        """Evaluate to a float if fully numeric."""
        raise ValueError(f"Cannot evaluate: expression contains variables")

    @property
    def is_const(self) -> bool:
        return False

    @property
    def is_zero(self) -> bool:
        return False

    @property
    def is_one(self) -> bool:
        return False

    def free_vars(self) -> set[str]:
        return set()

    # ── Python operator overloads ────────────────────────────────────────

    def __add__(self, other):
        return Add(self, _wrap(other))

    def __radd__(self, other):
        return Add(_wrap(other), self)

    def __sub__(self, other):
        return Add(self, Mul(Const(-1), _wrap(other)))

    def __rsub__(self, other):
        return Add(_wrap(other), Mul(Const(-1), self))

    def __mul__(self, other):
        return Mul(self, _wrap(other))

    def __rmul__(self, other):
        return Mul(_wrap(other), self)

    def __truediv__(self, other):
        return Mul(self, Pow(_wrap(other), Const(-1)))

    def __rtruediv__(self, other):
        return Mul(_wrap(other), Pow(self, Const(-1)))

    def __pow__(self, other):
        return Pow(self, _wrap(other))

    def __rpow__(self, other):
        return Pow(_wrap(other), self)

    def __neg__(self):
        return Mul(Const(-1), self)

    def __pos__(self):
        return self

    def __eq__(self, other):
        return type(self) == type(other) and self._eq(other)

    def __hash__(self):
        return hash(repr(self))

    def _eq(self, other) -> bool:
        return False


# ─── Leaf nodes ──────────────────────────────────────────────────────────────

class Const(Expr):
    __slots__ = ('value',)

    def __init__(self, value: float):
        self.value = float(value)

    @property
    def is_const(self) -> bool:
        return True

    @property
    def is_zero(self) -> bool:
        return self.value == 0.0

    @property
    def is_one(self) -> bool:
        return self.value == 1.0

    def diff(self, var):
        return Const(0)

    def subs(self, var, value):
        return self

    def eval(self) -> float:
        return self.value

    def free_vars(self):
        return set()

    def _eq(self, other):
        return isinstance(other, Const) and self.value == other.value

    def __repr__(self):
        v = self.value
        if v == int(v) and abs(v) < 1e15:
            return str(int(v))
        return f"{v:g}"


class Sym(Expr):
    __slots__ = ('name',)

    def __init__(self, name: str):
        self.name = name

    def diff(self, var):
        if isinstance(var, Sym) and var.name == self.name:
            return Const(1)
        return Const(0)

    def subs(self, var, value):
        if isinstance(var, Sym) and var.name == self.name:
            return _wrap(value)
        return self

    def eval(self) -> float:
        raise ValueError(f"Cannot evaluate: variable '{self.name}' has no value")

    def free_vars(self):
        return {self.name}

    def _eq(self, other):
        return isinstance(other, Sym) and self.name == other.name

    def __repr__(self):
        return self.name


# ─── Composite nodes ────────────────────────────────────────────────────────

class Add(Expr):
    __slots__ = ('left', 'right')

    def __init__(self, left: Expr, right: Expr):
        self.left = left
        self.right = right

    def diff(self, var):
        return Add(self.left.diff(var), self.right.diff(var))

    def subs(self, var, value):
        return Add(self.left.subs(var, value), self.right.subs(var, value))

    def simplify(self):
        l = self.left.simplify()
        r = self.right.simplify()
        if l.is_zero:
            return r
        if r.is_zero:
            return l
        if l.is_const and r.is_const:
            return Const(l.eval() + r.eval())
        # x + x → 2*x
        if l == r:
            return Mul(Const(2), l).simplify()
        # a*x + b*x → (a+b)*x
        lc, lx = _coeff_and_term(l)
        rc, rx = _coeff_and_term(r)
        if lx is not None and rx is not None and lx == rx:
            return Mul(Const(lc + rc), lx).simplify()
        return Add(l, r)

    def expand(self):
        return Add(self.left.expand(), self.right.expand())

    def eval(self):
        return self.left.eval() + self.right.eval()

    def free_vars(self):
        return self.left.free_vars() | self.right.free_vars()

    def _eq(self, other):
        return isinstance(other, Add) and self.left == other.left and self.right == other.right

    def __repr__(self):
        r_str = repr(self.right)
        # Handle subtraction display: x + (-1)*y → x - y
        if isinstance(self.right, Mul) and isinstance(self.right.left, Const) and self.right.left.value < 0:
            coeff = -self.right.left.value
            if coeff == 1:
                return f"{self.left} - {self.right.right}"
            return f"{self.left} - {coeff:g}*{self.right.right}"
        return f"{self.left} + {self.right}"


class Mul(Expr):
    __slots__ = ('left', 'right')

    def __init__(self, left: Expr, right: Expr):
        self.left = left
        self.right = right

    def diff(self, var):
        # Product rule: (f*g)' = f'*g + f*g'
        return Add(
            Mul(self.left.diff(var), self.right),
            Mul(self.left, self.right.diff(var))
        )

    def subs(self, var, value):
        return Mul(self.left.subs(var, value), self.right.subs(var, value))

    def simplify(self):
        l = self.left.simplify()
        r = self.right.simplify()
        if l.is_zero or r.is_zero:
            return Const(0)
        if l.is_one:
            return r
        if r.is_one:
            return l
        if l.is_const and r.is_const:
            return Const(l.eval() * r.eval())
        # (-1) * (-1) * x → x
        if isinstance(l, Const) and l.value == -1 and isinstance(r, Mul) and isinstance(r.left, Const) and r.left.value == -1:
            return r.right.simplify()
        # Combine like powers: x * x → x²
        lb, le = _base_and_exp(l)
        rb, re = _base_and_exp(r)
        if lb == rb:
            return Pow(lb, Add(Const(le), Const(re)).simplify()).simplify()
        # Const * Const*expr → (c1*c2)*expr
        if l.is_const and isinstance(r, Mul) and r.left.is_const:
            return Mul(Const(l.eval() * r.left.eval()), r.right).simplify()
        return Mul(l, r)

    def expand(self):
        l = self.left.expand()
        r = self.right.expand()
        # (a + b) * c → a*c + b*c
        if isinstance(l, Add):
            return Add(Mul(l.left, r).expand(), Mul(l.right, r).expand())
        if isinstance(r, Add):
            return Add(Mul(l, r.left).expand(), Mul(l, r.right).expand())
        return Mul(l, r)

    def eval(self):
        return self.left.eval() * self.right.eval()

    def free_vars(self):
        return self.left.free_vars() | self.right.free_vars()

    def _eq(self, other):
        return isinstance(other, Mul) and self.left == other.left and self.right == other.right

    def __repr__(self):
        l_str = repr(self.left)
        r_str = repr(self.right)
        # -1 * x → -x
        if isinstance(self.left, Const) and self.left.value == -1:
            return f"-{r_str}"
        # Const * expr → coeff*expr (no parens needed for const)
        if isinstance(self.left, Const):
            if isinstance(self.right, (Sym, Pow, Func)):
                return f"{l_str}*{r_str}"
            return f"{l_str}*({r_str})"
        # Wrap additions in parens
        if isinstance(self.left, Add):
            l_str = f"({l_str})"
        if isinstance(self.right, Add):
            r_str = f"({r_str})"
        return f"{l_str}*{r_str}"


class Pow(Expr):
    __slots__ = ('base', 'exp')

    def __init__(self, base: Expr, exp: Expr):
        self.base = base
        self.exp = exp

    def diff(self, var):
        # If exponent is constant: d/dx[f^n] = n*f^(n-1)*f'
        if self.exp.is_const:
            n = self.exp
            return Mul(Mul(n, Pow(self.base, Add(n, Const(-1)))), self.base.diff(var))
        # General: d/dx[f^g] = f^g * (g'*ln(f) + g*f'/f)
        f, g = self.base, self.exp
        return Mul(self,
            Add(Mul(g.diff(var), Func('ln', f)),
                Mul(g, Mul(f.diff(var), Pow(f, Const(-1))))))

    def subs(self, var, value):
        return Pow(self.base.subs(var, value), self.exp.subs(var, value))

    def simplify(self):
        b = self.base.simplify()
        e = self.exp.simplify()
        if e.is_zero:
            return Const(1)
        if e.is_one:
            return b
        if b.is_zero:
            return Const(0)
        if b.is_one:
            return Const(1)
        if b.is_const and e.is_const:
            return Const(b.eval() ** e.eval())
        # (x^a)^b → x^(a*b)
        if isinstance(b, Pow):
            return Pow(b.base, Mul(b.exp, e).simplify()).simplify()
        return Pow(b, e)

    def expand(self):
        b = self.base.expand()
        e = self.exp.expand()
        # (a + b)^2 → a^2 + 2ab + b^2
        if isinstance(b, Add) and isinstance(e, Const) and e.value == 2:
            a, c = b.left, b.right
            return Add(Add(Pow(a, Const(2)), Mul(Const(2), Mul(a, c))), Pow(c, Const(2))).expand()
        return Pow(b, e)

    def eval(self):
        return self.base.eval() ** self.exp.eval()

    def free_vars(self):
        return self.base.free_vars() | self.exp.free_vars()

    def _eq(self, other):
        return isinstance(other, Pow) and self.base == other.base and self.exp == other.exp

    def __repr__(self):
        b_str = repr(self.base)
        e_str = repr(self.exp)
        # x^(-1) → 1/x
        if isinstance(self.exp, Const) and self.exp.value == -1:
            if isinstance(self.base, (Sym, Const)):
                return f"1/{b_str}"
            return f"1/({b_str})"
        # Wrap complex bases in parens
        if isinstance(self.base, (Add, Mul)):
            b_str = f"({b_str})"
        return f"{b_str}^{e_str}"


class Func(Expr):
    """Named function application: sin(x), exp(x), ln(x), etc."""
    __slots__ = ('name', 'arg')

    KNOWN_FUNCS = {'sin', 'cos', 'tan', 'exp', 'ln', 'log', 'sqrt', 'abs',
                   'asin', 'acos', 'atan', 'sinh', 'cosh', 'tanh'}

    def __init__(self, name: str, arg: Expr):
        self.name = name
        self.arg = arg

    def diff(self, var):
        # Chain rule: d/dx[f(g)] = f'(g) * g'
        da = self.arg.diff(var)
        if self.name == 'sin':
            return Mul(Func('cos', self.arg), da)
        if self.name == 'cos':
            return Mul(Mul(Const(-1), Func('sin', self.arg)), da)
        if self.name == 'tan':
            return Mul(Pow(Func('cos', self.arg), Const(-2)), da)
        if self.name in ('exp',):
            return Mul(Func('exp', self.arg), da)
        if self.name in ('ln', 'log'):
            return Mul(Pow(self.arg, Const(-1)), da)
        if self.name == 'sqrt':
            return Mul(Mul(Const(0.5), Pow(self.arg, Const(-0.5))), da)
        if self.name == 'asin':
            return Mul(Pow(Add(Const(1), Mul(Const(-1), Pow(self.arg, Const(2)))), Const(-0.5)), da)
        if self.name == 'acos':
            return Mul(Mul(Const(-1), Pow(Add(Const(1), Mul(Const(-1), Pow(self.arg, Const(2)))), Const(-0.5))), da)
        raise ValueError(f"Don't know how to differentiate '{self.name}'")

    def subs(self, var, value):
        return Func(self.name, self.arg.subs(var, value))

    def simplify(self):
        a = self.arg.simplify()
        if a.is_const:
            return Const(self._eval_func(a.eval()))
        # ln(exp(x)) → x
        if self.name in ('ln', 'log') and isinstance(a, Func) and a.name == 'exp':
            return a.arg
        # exp(ln(x)) → x
        if self.name == 'exp' and isinstance(a, Func) and a.name in ('ln', 'log'):
            return a.arg
        # sqrt(x^2) → |x| (simplified to x for now)
        if self.name == 'sqrt' and isinstance(a, Pow) and isinstance(a.exp, Const) and a.exp.value == 2:
            return a.base
        return Func(self.name, a)

    def eval(self):
        return self._eval_func(self.arg.eval())

    def _eval_func(self, v):
        funcs = {
            'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
            'exp': math.exp, 'ln': math.log, 'log': math.log,
            'sqrt': math.sqrt, 'abs': abs,
            'asin': math.asin, 'acos': math.acos, 'atan': math.atan,
            'sinh': math.sinh, 'cosh': math.cosh, 'tanh': math.tanh,
        }
        if self.name in funcs:
            return funcs[self.name](v)
        raise ValueError(f"Unknown function: {self.name}")

    def free_vars(self):
        return self.arg.free_vars()

    def _eq(self, other):
        return isinstance(other, Func) and self.name == other.name and self.arg == other.arg

    def __repr__(self):
        return f"{self.name}({self.arg})"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _wrap(x) -> Expr:
    """Coerce a number or Quantity to a Const."""
    if isinstance(x, Expr):
        return x
    if isinstance(x, (int, float)):
        return Const(float(x))
    # Handle Kerma Quantity — extract numeric value
    if hasattr(x, 'value') and hasattr(x, 'dim'):
        return Const(float(x.value))
    raise TypeError(f"Cannot convert {type(x).__name__} to symbolic Expr")


def _coeff_and_term(expr: Expr) -> tuple[float, Optional[Expr]]:
    """Extract coefficient and term: 3*x → (3, x), x → (1, x), 5 → (5, None)."""
    if isinstance(expr, Mul) and isinstance(expr.left, Const):
        return expr.left.value, expr.right
    if isinstance(expr, Const):
        return expr.value, None
    return 1.0, expr


def _base_and_exp(expr: Expr) -> tuple[Expr, float]:
    """Extract base and exponent: x^2 → (x, 2), x → (x, 1)."""
    if isinstance(expr, Pow) and isinstance(expr.exp, Const):
        return expr.base, expr.exp.value
    return expr, 1.0


# ─── Top-level functions ────────────────────────────────────────────────────

def sym(name: str) -> Sym:
    """Create a symbolic variable."""
    return Sym(name)


def diff(expr: Expr, var: Expr, n: int = 1) -> Expr:
    """Differentiate expr with respect to var, n times."""
    if isinstance(var, str):
        var = Sym(var)
    result = expr
    for _ in range(n):
        result = result.diff(var).simplify()
    return result


def simplify(expr: Expr) -> Expr:
    """Simplify an expression. Applies rules iteratively until stable."""
    prev = None
    current = expr
    for _ in range(20):  # max iterations to prevent infinite loops
        simplified = current.simplify()
        if simplified == prev:
            return simplified
        prev = current
        current = simplified
    return current


def expand(expr: Expr) -> Expr:
    """Expand products and powers."""
    return expr.expand().simplify()


def subs(expr: Expr, var: Expr, value) -> Expr:
    """Substitute var with value in expr."""
    if isinstance(var, str):
        var = Sym(var)
    result = expr.subs(var, _wrap(value))
    return simplify(result)


def integrate(expr: Expr, var: Expr) -> Expr:
    """Basic symbolic integration. Handles polynomials, exp, sin, cos, 1/x."""
    if isinstance(var, str):
        var = Sym(var)

    # Constant w.r.t. var
    if var.name not in expr.free_vars():
        return Mul(expr, var)

    # x → x²/2
    if isinstance(expr, Sym) and expr.name == var.name:
        return Mul(Const(0.5), Pow(var, Const(2)))

    # x^n → x^(n+1)/(n+1) for n ≠ -1
    if isinstance(expr, Pow) and isinstance(expr.base, Sym) and expr.base.name == var.name:
        if isinstance(expr.exp, Const):
            n = expr.exp.value
            if n == -1:
                return Func('ln', var)
            return Mul(Const(1.0 / (n + 1)), Pow(var, Const(n + 1)))

    # Const * f → Const * ∫f
    if isinstance(expr, Mul) and isinstance(expr.left, Const):
        inner = integrate(expr.right, var)
        return Mul(expr.left, inner).simplify()

    # f + g → ∫f + ∫g
    if isinstance(expr, Add):
        return Add(integrate(expr.left, var), integrate(expr.right, var)).simplify()

    # exp(a*x) → exp(a*x)/a
    if isinstance(expr, Func) and expr.name == 'exp':
        if isinstance(expr.arg, Mul) and isinstance(expr.arg.left, Const) and isinstance(expr.arg.right, Sym) and expr.arg.right.name == var.name:
            a = expr.arg.left.value
            return Mul(Const(1.0 / a), expr)
        if isinstance(expr.arg, Sym) and expr.arg.name == var.name:
            return expr  # ∫exp(x) = exp(x)

    # sin(x) → -cos(x)
    if isinstance(expr, Func) and expr.name == 'sin' and isinstance(expr.arg, Sym) and expr.arg.name == var.name:
        return Mul(Const(-1), Func('cos', var))

    # cos(x) → sin(x)
    if isinstance(expr, Func) and expr.name == 'cos' and isinstance(expr.arg, Sym) and expr.arg.name == var.name:
        return Func('sin', var)

    raise ValueError(f"Cannot integrate: {expr}")


def sym_solve(expr: Expr, var: Expr) -> list[Expr]:
    """Solve expr = 0 for var. Handles linear and quadratic."""
    if isinstance(var, str):
        var = Sym(var)
    expr = expand(expr)

    # Collect polynomial coefficients
    coeffs = _collect_poly(expr, var)
    if coeffs is None:
        raise ValueError(f"Cannot solve: {expr} = 0 for {var.name}")

    degree = len(coeffs) - 1

    if degree == 0:
        return []  # constant equation

    if degree == 1:
        # ax + b = 0 → x = -b/a
        a, b = coeffs[1], coeffs[0]
        return [simplify(Mul(Const(-1), Mul(Const(b), Pow(Const(a), Const(-1)))))]

    if degree == 2:
        # ax² + bx + c = 0
        a, b, c = coeffs[2], coeffs[1], coeffs[0]
        disc_val = b**2 - 4*a*c
        if disc_val < 0:
            return []  # complex roots
        disc = Const(math.sqrt(disc_val))
        x1 = simplify(Mul(Add(Const(-b), disc), Pow(Const(2*a), Const(-1))))
        x2 = simplify(Mul(Add(Const(-b), Mul(Const(-1), disc)), Pow(Const(2*a), Const(-1))))
        if x1 == x2:
            return [x1]
        return [x1, x2]

    raise ValueError(f"Cannot solve degree-{degree} polynomial")


def _collect_poly(expr: Expr, var: Sym) -> Optional[list[float]]:
    """
    Collect polynomial coefficients: returns [c0, c1, c2, ...] for c0 + c1*x + c2*x² + ...
    Returns None if not a polynomial in var.
    """
    # Expand first
    expr = expand(expr)
    terms = _flatten_sum(expr)

    max_deg = 0
    coeffs_dict = {}

    for term in terms:
        coeff, deg = _term_degree(term, var)
        if coeff is None:
            return None
        coeffs_dict[deg] = coeffs_dict.get(deg, 0.0) + coeff
        max_deg = max(max_deg, deg)

    return [coeffs_dict.get(i, 0.0) for i in range(max_deg + 1)]


def _flatten_sum(expr: Expr) -> list[Expr]:
    """Flatten nested Add into a list of terms."""
    if isinstance(expr, Add):
        return _flatten_sum(expr.left) + _flatten_sum(expr.right)
    return [expr]


def _term_degree(term: Expr, var: Sym) -> tuple[Optional[float], int]:
    """Get (coefficient, degree) of a term w.r.t. var. Returns (None, 0) if not polynomial."""
    if var.name not in term.free_vars():
        try:
            return term.eval(), 0
        except ValueError:
            return None, 0

    # x → (1, 1)
    if isinstance(term, Sym) and term.name == var.name:
        return 1.0, 1

    # x^n → (1, n)
    if isinstance(term, Pow) and isinstance(term.base, Sym) and term.base.name == var.name:
        if isinstance(term.exp, Const) and term.exp.value == int(term.exp.value):
            return 1.0, int(term.exp.value)
        return None, 0

    # c * x^n
    if isinstance(term, Mul):
        lc, lt = _split_const_var(term, var)
        if lc is not None and lt is not None:
            _, deg = _term_degree(lt, var)
            return lc, deg
        if lc is not None and lt is None:
            return lc, 0

    return None, 0


def _split_const_var(expr: Expr, var: Sym) -> tuple[Optional[float], Optional[Expr]]:
    """Split a Mul into (constant_part, variable_part)."""
    if isinstance(expr, Const):
        return expr.value, None
    if isinstance(expr, Mul):
        if isinstance(expr.left, Const):
            if var.name not in expr.right.free_vars():
                try:
                    return expr.left.value * expr.right.eval(), None
                except ValueError:
                    return None, None
            return expr.left.value, expr.right
        if isinstance(expr.right, Const):
            if var.name not in expr.left.free_vars():
                try:
                    return expr.right.value * expr.left.eval(), None
                except ValueError:
                    return None, None
            return expr.right.value, expr.left
    return None, None
