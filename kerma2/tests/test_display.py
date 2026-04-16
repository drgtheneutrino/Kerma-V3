"""Tests for the Kerma display engine."""

import sys
sys.path.insert(0, "/home/claude/kerma")

import numpy as np
from display import *
from units import Quantity, REGISTRY
from linalg import Vec, Mat
from symbolic import Sym, Const as SC, Add, Mul, Pow, Func

passed = 0
failed = 0

def test(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name}")

def test_eq(name, result, expected):
    global passed, failed
    if result == expected:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name} (got '{result}', expected '{expected}')")

def test_contains(name, result, substring):
    global passed, failed
    if substring in result:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name} ('{substring}' not in '{result}')")


# ─── Number formatting ──────────────────────────────────────────────────────

print("\n─── Number formatting ───")

test_eq("zero", format_number(0), "0")
test_eq("integer", format_number(42.0), "42")
test_eq("negative int", format_number(-7.0), "-7")
test_eq("simple float", format_number(3.14), "3.14")
test_contains("small sci", format_number(9.109e-31), "×10⁻³¹")
test_contains("large sci", format_number(6.022e23), "×10²³")

test_eq("format_sci zero", format_sci(0), "0")
test_contains("format_sci exp", format_sci(1.6e-19), "×10⁻¹⁹")


# ─── Unit dimension formatting ──────────────────────────────────────────────

print("\n─── Unit dim formatting ───")

test_eq("energy dims", format_unit_dim((2,1,-2,0,0,0,0)), "m²·kg·s⁻²")
test_eq("velocity dims", format_unit_dim((1,0,-1,0,0,0,0)), "m·s⁻¹")
test_eq("dimensionless", format_unit_dim((0,0,0,0,0,0,0)), "")
test_eq("length", format_unit_dim((1,0,0,0,0,0,0)), "m")
test_eq("area", format_unit_dim((2,0,0,0,0,0,0)), "m²")


# ─── Quantity display ────────────────────────────────────────────────────────

print("\n─── Quantity display ───")

q = Quantity(5 * REGISTRY.get('MeV').to_si, (2,1,-2,0,0,0,0), 'MeV')
test_eq("5 MeV", format_quantity(q), "5 MeV")

q2 = Quantity(299792458.0, (1,0,-1,0,0,0,0), 'm/s')
r = format_quantity(q2)
test_contains("speed of light", r, "299792458")

q3 = Quantity(42.0)
test_eq("dimensionless", format_quantity(q3), "42")


# ─── Vec display ─────────────────────────────────────────────────────────────

print("\n─── Vec display ───")

v = Vec(np.array([1.0, 2.0, 3.0]), (1,0,0,0,0,0,0), 'm')
r = format_vec(v)
test_contains("vec has angle brackets", r, "⟨")
test_contains("vec has unit", r, "m")
test_contains("vec has values", r, "1, 2, 3")

# Column format
col = format_vec_column(v, label='r')
test_contains("column has top bracket", col, "⎡")
test_contains("column has bottom bracket", col, "⎣")
test_contains("column has label", col, "r =")
test_contains("column has unit", col, "m")


# ─── Mat display ─────────────────────────────────────────────────────────────

print("\n─── Mat display ───")

m = Mat(np.array([[1.0, 2.0], [3.0, 4.0]]))
r = format_mat(m, label='A')
test_contains("mat has top bracket", r, "⎡")
test_contains("mat has bottom bracket", r, "⎣")
test_contains("mat has label", r, "A =")
test_contains("mat has values", r, "1")

# 3x3
m3 = Mat(np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]))
r3 = format_mat(m3)
test_contains("3x3 has middle bracket", r3, "⎢")


# ─── Symbolic display ───────────────────────────────────────────────────────

print("\n─── Symbolic display ───")

x = Sym('x')
y = Sym('y')

test_eq("sym variable", format_symbolic(x), "x")
test_eq("const", format_symbolic(SC(3)), "3")
test_eq("const float", format_symbolic(SC(3.14)), "3.14")

# Polynomial
f = x**2 + SC(3)*x + SC(2)
r = format_symbolic(f)
test_contains("poly has x²", r, "x²")
test_contains("poly has 3x", r, "3x")

# Subtraction display
g = x - SC(1)
r = format_symbolic(g)
test_contains("subtraction has −", r, "−")

# Powers
test_eq("x²", format_symbolic(x**2), "x²")
test_eq("x³", format_symbolic(x**3), "x³")
test_eq("x⁻¹", format_symbolic(x**SC(-1)), "x⁻¹")
test_eq("√x", format_symbolic(x**SC(0.5)), "√x")

# Functions
test_eq("sin(x)", format_symbolic(Func('sin', x)), "sin(x)")
test_eq("cos(x²)", format_symbolic(Func('cos', x**2)), "cos(x²)")
test_eq("ln(x)", format_symbolic(Func('ln', x)), "ln(x)")
test_eq("√(x+1)", format_symbolic(Func('sqrt', x + SC(1))), "√(x + 1)")

# Negation
test_eq("-x", format_symbolic(-x), "−x")

# Greek letters
test_eq("alpha", format_symbolic(Sym('alpha')), "α")
test_eq("beta", format_symbolic(Sym('beta')), "β")
test_eq("theta", format_symbolic(Sym('theta')), "θ")
test_eq("lambda", format_symbolic(Sym('lambda')), "λ")

# Subscripts
test_contains("x_1", format_symbolic(Sym('x_1')), "₁")
test_contains("x_2", format_symbolic(Sym('x_2')), "₂")


# ─── Unified display function ───────────────────────────────────────────────

print("\n─── Unified display ───")

q = Quantity(5 * REGISTRY.get('MeV').to_si, (2,1,-2,0,0,0,0), 'MeV')
test_eq("display quantity", display(q), "5 MeV")

v = Vec(np.array([1.0, 2.0]), (1,0,0,0,0,0,0), 'm')
test_contains("display vec", display(v), "⟨")

test_eq("display bool", display(True), "True")
test_eq("display none", display(None), "None")
test_eq("display string", display("hello"), "hello")

# With label
test_contains("display label", display(q, label="E"), "E = 5 MeV")

# Symbolic
test_contains("display symbolic", display(x**2), "x²")


# ─── Color display ──────────────────────────────────────────────────────────

print("\n─── Color display ───")

r = display_color(q)
test_contains("color has green", r, Color.NUMBER)
test_contains("color has cyan", r, Color.UNIT)
test_contains("color has reset", r, Color.RESET)

r = display_color(f)
test_contains("sym color has yellow", r, Color.SYMBOL)


# ─── Equation display ───────────────────────────────────────────────────────

print("\n─── Equation display ───")

r = display_equation("E", q)
test_contains("equation has =", r, "E = 5 MeV")


# ─── Integration: display through interpreter ───────────────────────────────

print("\n─── Integration with interpreter ───")

from interpreter import run_source
output = []
def cap(text):
    output.append(text)

run_source("print 5 MeV", output_fn=cap)
test_eq("interp print uses display", output[0], "5 MeV")

output.clear()
run_source("print m_e", output_fn=cap)
test_contains("interp electron mass", output[0], "×10⁻³¹")


# ─── Integration: display through VM ────────────────────────────────────────

print("\n─── Integration with VM ───")

from vm import vm_run_source
output.clear()

vm_run_source("print 5 MeV", output_fn=cap)
test_eq("VM print uses display", output[0], "5 MeV")

output.clear()
vm_run_source("print m_e", output_fn=cap)
test_contains("VM electron mass", output[0], "×10⁻³¹")


# ─── Summary ─────────────────────────────────────────────────────────────────

print(f"\n{'='*50}")
print(f"  Results: {passed} passed, {failed} failed")
print(f"{'='*50}")
sys.exit(0 if failed == 0 else 1)
