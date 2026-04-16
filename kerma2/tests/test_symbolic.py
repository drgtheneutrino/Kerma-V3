"""Tests for Kerma symbolic math engine."""

import sys, math
sys.path.insert(0, "/home/claude/kerma")

from interpreter import run_source
from symbolic import (Sym, Const, Add, Mul, Pow, Func, Expr,
                       sym, diff, simplify, expand, subs, integrate, sym_solve)

passed = 0
failed = 0
output_capture = []

def capture(text):
    output_capture.append(text)

def run(source):
    output_capture.clear()
    return run_source(source, output_fn=capture)

def test(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name}")

def test_eq(name, result, expected_str):
    global passed, failed
    r = repr(result).strip()
    if r == expected_str:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name} (got '{r}', expected '{expected_str}')")

def test_contains(name, result, expected_str):
    global passed, failed
    r = repr(result)
    if expected_str in r:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name} (got '{r}', expected to contain '{expected_str}')")

def test_eval(name, expr, expected, rel_tol=1e-6):
    global passed, failed
    try:
        val = expr.eval() if isinstance(expr, Expr) else float(expr)
        if expected == 0:
            ok = abs(val) < 1e-12
        else:
            ok = math.isclose(val, expected, rel_tol=rel_tol)
        if ok:
            passed += 1
            print(f"  ✓ {name}")
        else:
            failed += 1
            print(f"  ✗ {name} (got {val}, expected {expected})")
    except Exception as e:
        failed += 1
        print(f"  ✗ {name} ({type(e).__name__}: {e})")

def test_raises(name, exc_type, fn):
    global passed, failed
    try:
        fn()
        failed += 1
        print(f"  ✗ {name} (no exception)")
    except exc_type:
        passed += 1
        print(f"  ✓ {name}")
    except Exception as e:
        failed += 1
        print(f"  ✗ {name} (got {type(e).__name__}: {e})")


# ─── Direct API tests (no interpreter) ──────────────────────────────────────

print("\n─── Expr construction ───")

x = Sym('x')
y = Sym('y')

test("Sym repr", repr(x) == "x")
test("Const repr", repr(Const(3)) == "3")
test("Const float repr", repr(Const(3.14)) == "3.14")
test("Const zero", Const(0).is_zero)
test("Const one", Const(1).is_one)

f = x**2 + 3*x + 2
test("polynomial type", isinstance(f, Add))
test_contains("polynomial repr", f, "x^2")

test("free_vars", x.free_vars() == {'x'})
test("free_vars compound", f.free_vars() == {'x'})
test("free_vars multi", (x + y).free_vars() == {'x', 'y'})


# ─── Differentiation ────────────────────────────────────────────────────────

print("\n─── Differentiation ───")

test_eq("d/dx[x] = 1", diff(x, x), "1")
test_eq("d/dx[5] = 0", diff(Const(5), x), "0")
test_eq("d/dx[y] = 0", diff(y, x), "0")

test_eq("d/dx[x²] = 2x", diff(x**2, x), "2*x")
test_eq("d/dx[x³] = 3x²", diff(x**3, x), "3*x^2")

f = x**2 + 3*x + 2
test_eq("d/dx[x²+3x+2] = 2x+3", diff(f, x), "2*x + 3")

# Second derivative
test_eq("d²/dx²[x³] = 6x", diff(x**3, x, 2), "6*x")
test_eq("d²/dx²[x²+3x] = 2", diff(x**2 + 3*x, x, 2), "2")

# Trig
test_eq("d/dx[sin(x)] = cos(x)", diff(Func('sin', x), x), "cos(x)")
test_eq("d/dx[cos(x)] = -sin(x)", diff(Func('cos', x), x), "-sin(x)")

# Exp/log
test_eq("d/dx[exp(x)] = exp(x)", diff(Func('exp', x), x), "exp(x)")
test_eq("d/dx[ln(x)] = 1/x", diff(Func('ln', x), x), "1/x")

# Chain rule
test_contains("d/dx[sin(x²)]", diff(Func('sin', x**2), x), "cos(x^2)")

# Product rule
f = x * Func('sin', x)
df = diff(f, x)
test_contains("product rule has sin", df, "sin(x)")
test_contains("product rule has cos", df, "cos(x)")


# ─── Simplification ─────────────────────────────────────────────────────────

print("\n─── Simplification ───")

test_eq("x + 0 → x", simplify(x + 0), "x")
test_eq("0 + x → x", simplify(Const(0) + x), "x")
test_eq("x * 1 → x", simplify(x * 1), "x")
test_eq("x * 0 → 0", simplify(x * 0), "0")
test_eq("x^0 → 1", simplify(x**0), "1")
test_eq("x^1 → x", simplify(x**1), "x")
test_eq("x + x → 2x", simplify(x + x), "2*x")
test_eq("3 + 4 → 7", simplify(Const(3) + Const(4)), "7")
test_eq("3 * 4 → 12", simplify(Const(3) * Const(4)), "12")
test_eq("2^3 → 8", simplify(Const(2) ** Const(3)), "8")
test_eq("ln(exp(x)) → x", simplify(Func('ln', Func('exp', x))), "x")
test_eq("exp(ln(x)) → x", simplify(Func('exp', Func('ln', x))), "x")


# ─── Expansion ───────────────────────────────────────────────────────────────

print("\n─── Expansion ───")

f = (x + 1) * (x + 2)
ef = expand(f)
test_contains("(x+1)(x+2) has x^2", ef, "x^2")

f2 = (x + y) * Const(3)
ef2 = expand(f2)
test_contains("3(x+y) has x", ef2, "x")
test_contains("3(x+y) has 3", ef2, "3")


# ─── Substitution ───────────────────────────────────────────────────────────

print("\n─── Substitution ───")

f = x**2 + 3*x + 2
test_eval("subs x=0", subs(f, x, 0), 2.0)
test_eval("subs x=1", subs(f, x, 1), 6.0)
test_eval("subs x=5", subs(f, x, 5), 42.0)
test_eval("subs x=-1", subs(f, x, -1), 0.0)

# Subs with another variable
g = subs(x**2 + y, x, y)
test("subs x→y", g.free_vars() == {'y'})


# ─── Integration ─────────────────────────────────────────────────────────────

print("\n─── Integration ───")

test_contains("∫x dx = x²/2", integrate(x, x), "0.5*x^2")
test_contains("∫x² dx = x³/3", integrate(x**2, x), "0.333333*x^3")

# ∫x^(-1) = ln(x)
test_eq("∫1/x dx = ln(x)", integrate(Pow(x, Const(-1)), x), "ln(x)")

# ∫sin(x) = -cos(x)
r = integrate(Func('sin', x), x)
test_contains("∫sin dx has cos", r, "cos(x)")

# ∫cos(x) = sin(x)
test_eq("∫cos dx = sin(x)", integrate(Func('cos', x), x), "sin(x)")

# ∫exp(x) = exp(x)
test_eq("∫exp(x) dx = exp(x)", integrate(Func('exp', x), x), "exp(x)")

# ∫(3x² + 2x) = x³ + x²
r = integrate(3*x**2 + 2*x, x)
test_contains("∫(3x²+2x) has x^3", r, "x^3")

# ∫constant dx = c*x
test_eq("∫5 dx = 5*x", integrate(Const(5), x), "5*x")

# ∫exp(2x) = exp(2x)/2
r = integrate(Func('exp', Const(2)*x), x)
test_contains("∫exp(2x) has exp", r, "exp(2*x)")


# ─── Solve ───────────────────────────────────────────────────────────────────

print("\n─── Solve ───")

# Linear: 2x + 6 = 0 → x = -3
roots = sym_solve(2*x + 6, x)
test("linear solve count", len(roots) == 1)
test_eval("linear solve value", roots[0], -3.0)

# Quadratic: x² - 5x + 6 = 0 → x = 3, 2
roots = sym_solve(x**2 - 5*x + 6, x)
test("quadratic solve count", len(roots) == 2)
vals = sorted([r.eval() for r in roots])
test_eval("quadratic root 1", Const(vals[0]), 2.0)
test_eval("quadratic root 2", Const(vals[1]), 3.0)

# x² - 4 = 0 → x = ±2
roots = sym_solve(x**2 - 4, x)
test("difference of squares count", len(roots) == 2)
vals = sorted([r.eval() for r in roots])
test_eval("root -2", Const(vals[0]), -2.0)
test_eval("root +2", Const(vals[1]), 2.0)

# Double root: x² - 4x + 4 = 0 → x = 2
roots = sym_solve(x**2 - 4*x + 4, x)
test("double root count", len(roots) == 1)
test_eval("double root value", roots[0], 2.0)


# ─── Eval ────────────────────────────────────────────────────────────────────

print("\n─── Eval ───")

test_eval("const eval", Const(42), 42.0)
test_eval("add eval", Const(3) + Const(4), 7.0)
test_eval("mul eval", Const(3) * Const(4), 12.0)
test_eval("pow eval", Const(2) ** Const(10), 1024.0)
test_eval("func eval", Func('sin', Const(0)), 0.0)
test_eval("complex eval", (Const(3)**2 + Const(4)**2), 25.0)
test_raises("eval with variable", ValueError, lambda: x.eval())


# ─── Interpreter integration ────────────────────────────────────────────────

print("\n─── Interpreter integration ───")

r = run('x = sym("x")\nx**2 + 3*x + 2')
test("build via interpreter", isinstance(r, Expr))
test_contains("interpreter poly repr", r, "x^2")

r = run('x = sym("x")\nf = x**2 + 3*x + 2\ndiff(f, x)')
test_eq("interpreter diff", r, "2*x + 3")

r = run('x = sym("x")\nf = x**2 - 5*x + 6\nsolve(f, x)')
test("interpreter solve", isinstance(r, list) and len(r) == 2)

r = run('x = sym("x")\nsubs(x**2, x, 4)')
test_eval("interpreter subs", r, 16.0)

r = run('x = sym("x")\nintegrate(x**3, x)')
test_contains("interpreter integrate", r, "x^4")

r = run('x = sym("x")\nsimplify(x + x + x)')
test_eq("interpreter simplify", r, "3*x")

r = run('x = sym("x")\nexpand((x + 1) * (x - 1))')
test_contains("interpreter expand", r, "x^2")

# Print symbolic
run('x = sym("x")\nprint diff(sin(x), x)')
test("print symbolic", "cos(x)" in output_capture[0])

# Symbolic + numeric coexistence
r = run("""x = sym("x")
f = x**2 + 1
val = subs(f, x, 3)
print val""")
test("sym→numeric via subs", output_capture[0] == "10")


# ─── Physics + symbolic ─────────────────────────────────────────────────────

print("\n─── Physics + symbolic ───")

# Symbolic derivative of attenuation
r = run("""x = sym("x")
mu = sym("mu")
f = exp(-mu * x)
df = diff(f, x)
print df""")
test_contains("atten derivative has exp", output_capture[0], "exp(")
test_contains("atten derivative has mu", output_capture[0], "μ")


# ─── Edge cases ──────────────────────────────────────────────────────────────

print("\n─── Edge cases ───")

test_eq("0 * x → 0", simplify(Const(0) * x), "0")
test_eq("1^x → 1", simplify(Const(1) ** x), "1")
test_eq("0^x → 0", simplify(Const(0) ** x), "0")
test_eq("--x → x", simplify(-(-x)), "x")

# Equality
test("Sym equality", Sym('x') == Sym('x'))
test("Sym inequality", Sym('x') != Sym('y'))
test("Const equality", Const(3) == Const(3))
test("Expr equality", (x + 1) == (x + 1))

test_raises("integrate unknown", ValueError,
    lambda: integrate(Func('tan', x), x))


# ─── Summary ─────────────────────────────────────────────────────────────────

print(f"\n{'='*50}")
print(f"  Results: {passed} passed, {failed} failed")
print(f"{'='*50}")
sys.exit(0 if failed == 0 else 1)
