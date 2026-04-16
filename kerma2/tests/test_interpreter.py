"""Tests for the Kerma interpreter."""

import sys, math
sys.path.insert(0, "/home/claude/kerma")

from interpreter import run_source, Interpreter, RuntimeError as KermaError
from units import Quantity, DimensionError
from linalg import Vec, REGISTRY

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

def test_close(name, result, expected, rel_tol=1e-6):
    """Compare raw SI .value of a Quantity (or plain number) to expected."""
    global passed, failed
    val = result.value if isinstance(result, Quantity) else float(result)
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

def test_display(name, result, expected_str):
    """Compare the display repr of a result to an expected string."""
    global passed, failed
    r = repr(result) if isinstance(result, Quantity) else str(result)
    if expected_str in r:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name} (got '{r}', expected '{expected_str}')")

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


# ─── Basic expressions (dimensionless, .value == display) ────────────────────

print("\n─── Basic expressions ───")

r = run("42")
test_close("integer", r, 42.0)

r = run("3.14")
test_close("float", r, 3.14)

r = run("2 + 3")
test_close("addition", r, 5.0)

r = run("10 - 4")
test_close("subtraction", r, 6.0)

r = run("3 * 7")
test_close("multiplication", r, 21.0)

r = run("20 / 4")
test_close("division", r, 5.0)

r = run("2 ** 10")
test_close("power", r, 1024.0)

r = run("(2 + 3) * 4")
test_close("grouped", r, 20.0)

r = run("-5")
test_close("unary minus", r, -5.0)

r = run("2 + 3 * 4")
test_close("precedence", r, 14.0)


# ─── Variables ───────────────────────────────────────────────────────────────

print("\n─── Variables ───")

r = run("x = 5\nx")
test_close("assignment and ref", r, 5.0)

r = run("x = 5\nx += 3\nx")
test_close("aug assign +=", r, 8.0)

r = run("x = 10\nx *= 2\nx")
test_close("aug assign *=", r, 20.0)


# ─── Unit quantities (compare via display repr) ─────────────────────────────

print("\n─── Unit quantities ───")

r = run("5 MeV")
test("5 MeV is Quantity", isinstance(r, Quantity))
test_display("5 MeV display", r, "5 MeV")
test("5 MeV has energy dim", r.dim == (2, 1, -2, 0, 0, 0, 0))

r = run("30 cm")
test_display("30 cm display", r, "30 cm")

r = run("3 MeV + 2 MeV")
test_display("add same units", r, "5 MeV")

r = run("5 MeV * 3")
test_display("scalar multiply", r, "15 MeV")

r = run("10 m / 2 s")
test_close("velocity SI value", r, 5.0)  # m/s, SI = direct
test("velocity dimensions", r.dim == (1, 0, -1, 0, 0, 0, 0))


# ─── Unit conversion (pipe returns display-scale value) ──────────────────────

print("\n─── Unit conversion ───")

r = run("1 MeV | eV")
test_display("MeV to eV", r, "1e+06 eV")

r = run("100 cm | m")
test_display("cm to m", r, "1 m")

r = run("E = 5 MeV\nE | keV")
test_display("variable pipe convert", r, "5000 keV")


# ─── Dimension errors ───────────────────────────────────────────────────────

print("\n─── Dimension errors ───")

test_raises("add MeV + cm", (KermaError, DimensionError),
    lambda: run("5 MeV + 3 cm"))

test_raises("convert MeV to m", (KermaError, DimensionError, ValueError),
    lambda: run("5 MeV | m"))


# ─── Physical constants ─────────────────────────────────────────────────────

print("\n─── Physical constants ───")

r = run("c")
test_close("speed of light SI", r, 299792458.0)

r = run("m_e")
test_close("electron mass SI", r, 9.1093837015e-31)

r = run("E_rest = m_e * c**2\nE_rest | MeV")
test_display("E = mc² ≈ 0.511 MeV", r, "0.51")


# ─── Math functions ──────────────────────────────────────────────────────────

print("\n─── Math functions ───")

r = run("exp(0)")
test_close("exp(0) = 1", r, 1.0)

r = run("exp(1)")
test_close("exp(1) ≈ e", r, math.e)

r = run("log(1)")
test_close("log(1) = 0", r, 0.0)

r = run("sqrt(4)")
test_close("sqrt(4) = 2", r, 2.0)

r = run("sin(0)")
test_close("sin(0) = 0", r, 0.0)

r = run("cos(0)")
test_close("cos(0) = 1", r, 1.0)

r = run("abs(-5)")
test_close("abs(-5) = 5", r, 5.0)

r = run("pi")
test_close("pi", r, math.pi)


# ─── Attenuation calculation ────────────────────────────────────────────────

print("\n─── Physics: attenuation ───")

src = """I0 = 5 MeV
mu = 0.0494
x = 30
atten = exp(-mu * x)
I = I0 * atten
I | MeV"""
r = run(src)
expected_mev = 5.0 * math.exp(-0.0494 * 30)
# r is in SI but displayed as MeV; extract display value from repr
display_val = float(repr(r).split()[0])
test_close("I = I₀·exp(-μx) display MeV", Quantity(display_val), expected_mev, rel_tol=1e-3)
test("result has energy dim", r.dim == (2, 1, -2, 0, 0, 0, 0))


# ─── Print ───────────────────────────────────────────────────────────────────

print("\n─── Print ───")

run("print 42")
test("print number", output_capture == ["42"])

run("print 5 MeV")
test("print quantity", output_capture == ["5 MeV"])

run("x = 3\nprint x * 2")
test("print expression", output_capture == ["6"])


# ─── Booleans and comparison ────────────────────────────────────────────────

print("\n─── Booleans and comparison ───")

r = run("3 < 5")
test("3 < 5", r is True)

r = run("5 == 5")
test("5 == 5", r is True)

r = run("3 > 5")
test("3 > 5", r is False)

r = run("True and False")
test("True and False", r is False)

r = run("True or False")
test("True or False", r is True)

r = run("not True")
test("not True", r is False)


# ─── If/else ─────────────────────────────────────────────────────────────────

print("\n─── If/else ───")

r = run("""x = 5
if x > 3:
    y = 1
else:
    y = 0
y""")
test_close("if true branch", r, 1.0)

r = run("""x = 1
if x > 3:
    y = 1
elif x > 0:
    y = 2
else:
    y = 3
y""")
test_close("elif branch", r, 2.0)


# ─── While loop ──────────────────────────────────────────────────────────────

print("\n─── While loop ───")

r = run("""x = 0
i = 0
while i < 10:
    x += i
    i += 1
x""")
test_close("while sum 0..9", r, 45.0)


# ─── For loop ────────────────────────────────────────────────────────────────

print("\n─── For loop ───")

r = run("""total = 0
for i in range(5):
    total += i
total""")
test_close("for range sum", r, 10.0)


# ─── Functions ───────────────────────────────────────────────────────────────

print("\n─── Functions ───")

r = run("""def double(x):
    return x * 2
double(5)""")
test_close("simple function", r, 10.0)

r = run("""def add(a, b):
    return a + b
add(3, 4)""")
test_close("two-arg function", r, 7.0)

r = run("""def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
factorial(5)""")
test_close("recursive function", r, 120.0)

# Function with physics — KE = 0.5 * 2kg * (3m/s)² = 9 J (SI)
r = run("""def kinetic_energy(m, v):
    return 0.5 * m * v**2
KE = kinetic_energy(2 kg, 3 m/s)
KE""")
test_close("physics function SI value", r, 9.0)
test("KE has energy dims", r.dim == (2, 1, -2, 0, 0, 0, 0))


# ─── Lists ───────────────────────────────────────────────────────────────────

print("\n─── Lists ───")

r = run("[1, 2, 3]")
test("list literal", (isinstance(r, list) or isinstance(r, Vec)) and len(r) == 3)

r = run("v = [1, 2, 3]\nv[0]")
test_close("list index", r, 1.0)

r = run("v = [10, 20, 30]\nlen(v)")
test("len", r == 3)


# ─── Method calls ───────────────────────────────────────────────────────────

print("\n─── Method calls ───")

r = run("E = 5 MeV\nE.to(keV)")
test_display(".to() conversion", r, "5000 keV")


# ─── Strings ─────────────────────────────────────────────────────────────────

print("\n─── Strings ───")

run('print "hello"')
test("print string", output_capture == ["hello"])


# ─── Multi-line physics program ──────────────────────────────────────────────

print("\n─── Full physics program ───")

src = """E = 5 MeV
mu = 0.0494
x = 30
t_half = 5.27
lambda_ = log(2) / t_half

atten = exp(-mu * x)
I = E * atten

print I | MeV
print lambda_"""
run(src)
test("multi-line runs", len(output_capture) == 2)

# Verify attenuated intensity (displayed in MeV)
first_val = float(output_capture[0].split()[0])
expected_atten = 5.0 * math.exp(-0.0494 * 30)
test_close("attenuated I display MeV", Quantity(first_val), expected_atten, rel_tol=1e-3)


# ─── Error handling ──────────────────────────────────────────────────────────

print("\n─── Errors ───")

test_raises("undefined variable", (NameError, KermaError),
    lambda: run("undefined_var"))

test_raises("wrong arg count", (KermaError, TypeError),
    lambda: run("def f(x):\n    return x\nf(1, 2)"))

test_raises("not callable", (KermaError, TypeError),
    lambda: run("x = 5\nx(3)"))


# ─── Summary ─────────────────────────────────────────────────────────────────

print(f"\n{'='*50}")
print(f"  Results: {passed} passed, {failed} failed")
print(f"{'='*50}")
sys.exit(0 if failed == 0 else 1)
