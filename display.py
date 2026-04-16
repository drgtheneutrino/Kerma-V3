"""
Kerma Display Engine
====================
Rich formatted output for the terminal using Unicode math symbols.

Renders:
  - Quantities with proper superscripts: kg·m²·s⁻²
  - Vectors in bracket notation with aligned columns
  - Matrices with box-drawing borders
  - Symbolic expressions in standard math notation
  - Fractions, Greek letters, special operators
"""

from __future__ import annotations
from typing import Any, Union
import math

from units import Quantity, REGISTRY, DIMENSIONLESS, dim_str as raw_dim_str


# ─── Unicode tables ──────────────────────────────────────────────────────────

SUPERSCRIPTS = str.maketrans('0123456789-+', '⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺')
SUBSCRIPTS = str.maketrans('0123456789', '₀₁₂₃₄₅₆₇₈₉')

GREEK_MAP = {
    'alpha': 'α', 'beta': 'β', 'gamma': 'γ', 'delta': 'δ',
    'epsilon': 'ε', 'zeta': 'ζ', 'eta': 'η', 'theta': 'θ',
    'iota': 'ι', 'kappa': 'κ', 'lambda': 'λ', 'mu': 'μ',
    'nu': 'ν', 'xi': 'ξ', 'pi': 'π', 'rho': 'ρ',
    'sigma': 'σ', 'tau': 'τ', 'upsilon': 'υ', 'phi': 'φ',
    'chi': 'χ', 'psi': 'ψ', 'omega': 'ω',
    'Alpha': 'Α', 'Beta': 'Β', 'Gamma': 'Γ', 'Delta': 'Δ',
    'Theta': 'Θ', 'Lambda': 'Λ', 'Pi': 'Π', 'Sigma': 'Σ',
    'Phi': 'Φ', 'Psi': 'Ψ', 'Omega': 'Ω',
}

SPECIAL_SYMBOLS = {
    'inf': '∞', 'infinity': '∞',
    'sqrt': '√', 'cbrt': '∛',
    'partial': '∂', 'nabla': '∇',
    'integral': '∫', 'sum': '∑', 'product': '∏',
    'approx': '≈', 'neq': '≠', 'leq': '≤', 'geq': '≥',
    'plusminus': '±', 'times': '×', 'cdot': '·',
    'arrow': '→', 'darrow': '⇒',
    'hbar': 'ℏ',
}


# ─── Number formatting ──────────────────────────────────────────────────────

def format_number(value: float, sig_figs: int = 6) -> str:
    """Format a number with appropriate precision."""
    if value == 0:
        return "0"
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))

    abs_val = abs(value)
    if 0.001 <= abs_val < 1e6:
        # Fixed notation
        result = f"{value:.{sig_figs}g}"
    else:
        # Scientific notation with Unicode superscripts
        exp = int(math.floor(math.log10(abs_val)))
        mantissa = value / (10 ** exp)
        exp_str = str(exp).translate(SUPERSCRIPTS)
        if abs(mantissa - round(mantissa)) < 1e-10:
            return f"{round(mantissa)}×10{exp_str}"
        return f"{mantissa:.{sig_figs-1}f}×10{exp_str}"

    return result


def format_sci(value: float) -> str:
    """Format in scientific notation with Unicode exponents."""
    if value == 0:
        return "0"
    exp = int(math.floor(math.log10(abs(value))))
    mantissa = value / (10 ** exp)
    exp_str = str(exp).translate(SUPERSCRIPTS)
    if exp == 0:
        return f"{mantissa:g}"
    if abs(mantissa - 1.0) < 1e-10:
        return f"10{exp_str}"
    return f"{mantissa:g}×10{exp_str}"


# ─── Unit formatting ────────────────────────────────────────────────────────

def format_unit_dim(dim: tuple) -> str:
    """Format a dimension vector as a Unicode unit string: kg·m²·s⁻²."""
    base_units = ['m', 'kg', 's', 'A', 'K', 'mol', 'cd']
    parts = []
    for symbol, exp in zip(base_units, dim):
        if exp == 0:
            continue
        if exp == 1:
            parts.append(symbol)
        else:
            exp_str = str(int(exp) if exp == int(exp) else exp).translate(SUPERSCRIPTS)
            parts.append(f"{symbol}{exp_str}")
    return '·'.join(parts) if parts else ''


# ─── Quantity display ────────────────────────────────────────────────────────

def format_quantity(q: Quantity, use_sci: bool = False) -> str:
    """Format a Quantity with value and unit."""
    u = q._best_unit()
    if u:
        display_val = q.value / u.to_si
        val_str = format_number(display_val) if not use_sci else format_sci(display_val)
        return f"{val_str} {u.symbol}"
    if q.dim == DIMENSIONLESS:
        return format_number(q.value)
    val_str = format_number(q.value) if not use_sci else format_sci(q.value)
    dim_str = format_unit_dim(q.dim)
    return f"{val_str} {dim_str}" if dim_str else val_str


# ─── Vector display ─────────────────────────────────────────────────────────

def format_vec(v, use_sci: bool = False) -> str:
    """Format a Vec with aligned columns and unit."""
    from linalg import Vec
    if not isinstance(v, Vec):
        return str(v)

    display = v._display_values()
    formatted = [format_number(x) for x in display]
    unit = v._best_unit_str()

    result = '⟨' + ', '.join(formatted) + '⟩'
    if unit:
        result += f" {unit}"
    return result


def format_vec_column(v, label: str = None) -> str:
    """Format a Vec as a column vector with brackets."""
    from linalg import Vec
    if not isinstance(v, Vec):
        return str(v)

    display = v._display_values()
    formatted = [format_number(x) for x in display]
    width = max(len(s) for s in formatted)
    unit = v._best_unit_str()

    lines = []
    n = len(formatted)
    for i, val in enumerate(formatted):
        if i == 0:
            left, right = '⎡', '⎤'
        elif i == n - 1:
            left, right = '⎣', '⎦'
        else:
            left, right = '⎢', '⎥'
        lines.append(f"{left} {val:>{width}} {right}")

    if unit:
        # Add unit to the middle row
        mid = n // 2
        lines[mid] += f"  {unit}"

    if label:
        lines.insert(0, f"  {label} =")

    return '\n'.join(lines)


# ─── Matrix display ─────────────────────────────────────────────────────────

def format_mat(m, label: str = None) -> str:
    """Format a Mat with box-drawing borders."""
    from linalg import Mat
    if not isinstance(m, Mat):
        return str(m)

    display = m._display_values()
    rows, cols = display.shape

    # Format all values
    formatted = [[format_number(display[i, j]) for j in range(cols)] for i in range(rows)]

    # Column widths
    col_widths = [max(len(formatted[i][j]) for i in range(rows)) for j in range(cols)]

    unit = m._best_unit_str()
    lines = []
    for i in range(rows):
        if i == 0:
            left, right = '⎡', '⎤'
        elif i == rows - 1:
            left, right = '⎣', '⎦'
        else:
            left, right = '⎢', '⎥'

        cells = '  '.join(formatted[i][j].rjust(col_widths[j]) for j in range(cols))
        lines.append(f"{left} {cells} {right}")

    if unit:
        mid = rows // 2
        lines[mid] += f"  {unit}"

    if label:
        lines.insert(0, f"  {label} =")

    return '\n'.join(lines)


# ─── Symbolic display ───────────────────────────────────────────────────────

def format_symbolic(expr) -> str:
    """Format a symbolic expression with Unicode math notation."""
    from symbolic import Expr, Const, Sym, Add, Mul, Pow, Func

    if isinstance(expr, Const):
        return format_number(expr.value)

    if isinstance(expr, Sym):
        name = expr.name
        # Convert known Greek names
        if name in GREEK_MAP:
            return GREEK_MAP[name]
        # Handle subscript notation: x_1 → x₁
        if '_' in name:
            parts = name.split('_', 1)
            base = GREEK_MAP.get(parts[0], parts[0])
            sub = parts[1]
            if sub.isdigit():
                return base + sub.translate(SUBSCRIPTS)
            return base + '_' + sub
        return name

    if isinstance(expr, Add):
        left = format_symbolic(expr.left)
        right_expr = expr.right

        # Detect subtraction: x + (-1)*y → x - y
        if isinstance(right_expr, Mul) and isinstance(right_expr.left, Const) and right_expr.left.value < 0:
            coeff = -right_expr.left.value
            rhs = format_symbolic(right_expr.right)
            if coeff == 1:
                return f"{left} − {rhs}"
            return f"{left} − {format_number(coeff)}·{rhs}"

        right = format_symbolic(right_expr)
        return f"{left} + {right}"

    if isinstance(expr, Mul):
        left = format_symbolic(expr.left)
        right = format_symbolic(expr.right)

        # -1 * x → −x
        if isinstance(expr.left, Const) and expr.left.value == -1:
            return f"−{right}"

        # Const * variable → coefficient notation
        if isinstance(expr.left, Const):
            if isinstance(expr.right, (Sym, Pow, Func)):
                return f"{left}{right}"
            return f"{left}·({right})"

        # Wrap additions in parens
        if isinstance(expr.left, Add):
            left = f"({left})"
        if isinstance(expr.right, Add):
            right = f"({right})"

        return f"{left}·{right}"

    if isinstance(expr, Pow):
        base = format_symbolic(expr.base)
        exp_val = expr.exp

        # x^(-1) → 1/x or x⁻¹
        if isinstance(exp_val, Const) and exp_val.value == -1:
            if isinstance(expr.base, (Sym, Const)):
                return f"{base}⁻¹"
            return f"({base})⁻¹"

        # x^0.5 → √x
        if isinstance(exp_val, Const) and exp_val.value == 0.5:
            return f"√{base}" if isinstance(expr.base, (Sym, Const)) else f"√({base})"

        # Integer exponents → superscript
        if isinstance(exp_val, Const) and exp_val.value == int(exp_val.value) and abs(exp_val.value) < 20:
            exp_str = str(int(exp_val.value)).translate(SUPERSCRIPTS)
            if isinstance(expr.base, (Add, Mul)):
                return f"({base}){exp_str}"
            return f"{base}{exp_str}"

        exp = format_symbolic(exp_val)
        if isinstance(expr.base, (Add, Mul)):
            base = f"({base})"
        return f"{base}^{exp}"

    if isinstance(expr, Func):
        arg = format_symbolic(expr.arg)
        name = expr.name
        if name == 'ln':
            return f"ln({arg})"
        if name == 'sqrt':
            return f"√({arg})"
        return f"{name}({arg})"

    return repr(expr)


# ─── Unified display ────────────────────────────────────────────────────────

def display(value: Any, label: str = None, use_sci: bool = False) -> str:
    """
    Format any Kerma value for rich terminal display.

    Returns a formatted string with Unicode math symbols.
    """
    from linalg import Vec, Mat
    from symbolic import Expr as SymExpr

    if isinstance(value, SymExpr):
        result = format_symbolic(value)
        if label:
            return f"  {label} = {result}"
        return result

    if isinstance(value, Mat):
        return format_mat(value, label)

    if isinstance(value, Vec):
        result = format_vec(value, use_sci)
        if label:
            return f"  {label} = {result}"
        return result

    if isinstance(value, Quantity):
        result = format_quantity(value, use_sci)
        if label:
            return f"  {label} = {result}"
        return result

    if isinstance(value, list):
        inner = ', '.join(display(v) for v in value)
        result = f"[{inner}]"
        if label:
            return f"  {label} = {result}"
        return result

    if isinstance(value, float):
        result = format_number(value)
        if label:
            return f"  {label} = {result}"
        return result

    if isinstance(value, bool):
        return str(value)

    if value is None:
        return "None"

    return str(value)


def display_print(value: Any, output_fn=None):
    """Display a value to the output (terminal)."""
    fn = output_fn or print
    fn(display(value))


# ─── Color support ──────────────────────────────────────────────────────────

class Color:
    """ANSI color codes for terminal output."""
    RESET   = '\033[0m'
    BOLD    = '\033[1m'
    DIM     = '\033[2m'
    # Values
    NUMBER  = '\033[32m'    # green
    UNIT    = '\033[36m'    # cyan
    SYMBOL  = '\033[33m'    # yellow
    ERROR   = '\033[31m'    # red
    LABEL   = '\033[90m'    # gray
    BRACKET = '\033[90m'    # gray


def display_color(value: Any, label: str = None) -> str:
    """Format with ANSI color codes for terminal display."""
    from linalg import Vec, Mat
    from symbolic import Expr as SymExpr

    plain = display(value, label)

    if isinstance(value, Quantity):
        u = value._best_unit()
        if u:
            dv = value.value / u.to_si
            val_str = format_number(dv)
            return f"{Color.NUMBER}{val_str}{Color.RESET} {Color.UNIT}{u.symbol}{Color.RESET}"
        return f"{Color.NUMBER}{plain}{Color.RESET}"

    if isinstance(value, SymExpr):
        return f"{Color.SYMBOL}{plain}{Color.RESET}"

    if isinstance(value, (Vec, Mat)):
        return f"{Color.NUMBER}{plain}{Color.RESET}"

    return plain


# ─── Equation display ───────────────────────────────────────────────────────

def display_equation(lhs: str, rhs: Any) -> str:
    """Format an equation: lhs = rhs."""
    rhs_str = display(rhs)
    return f"  {lhs} = {rhs_str}"


def display_step(description: str, result: Any) -> str:
    """Format a calculation step with description and result."""
    result_str = display(result)
    return f"  {Color.LABEL}{description}{Color.RESET}\n    = {result_str}"
