"""Tests for the Kerma bytecode compiler and VM.
Mirrors test_interpreter.py to verify parity with the tree-walker."""

import sys, math
sys.path.insert(0, "/home/claude/kerma")

from vm import vm_run_source, VM, VMError
from compiler import compile_program, Compiler
from bytecode import CodeObject, Op
from units import Quantity, DimensionError
from linalg import Vec, Mat
from symbolic import Expr as SymExpr

passed = 0
failed = 0
output_capture = []

def capture(text):
    output_capture.append(text)

def run(source):
    output_capture.clear()
    return vm_run_source(source, output_fn=capture)

def test(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name}")

def test_close(name, result, expected, rel_tol=1e-6):
    global passed, failed
    if isinstance(result, Quantity):
        val = result.value
    elif isinstance(result, SymExpr):
        try:
            val = result.eval()
        except:
            failed += 1; print(f"  ✗ {name} (cannot eval symbolic)"); return
    else:
        val = float(result)
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
    global passed, failed
    r = repr(result)
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


# ─── Basic expressions ──────────────────────────────────────────────────────

print("\n─── VM: Basic expressions ───")

test_close("integer", run("42"), 42.0)
test_close("float", run("3.14"), 3.14)
test_close("addition", run("2 + 3"), 5.0)
test_close("subtraction", run("10 - 4"), 6.0)
test_close("multiplication", run("3 * 7"), 21.0)
test_close("division", run("20 / 4"), 5.0)
test_close("power", run("2 ** 10"), 1024.0)
test_close("grouped", run("(2 + 3) * 4"), 20.0)
test_close("unary minus", run("-5"), -5.0)
test_close("precedence", run("2 + 3 * 4"), 14.0)


# ─── Variables ───────────────────────────────────────────────────────────────

print("\n─── VM: Variables ───")

test_close("assignment", run("x = 5\nx"), 5.0)
test_close("aug +=", run("x = 5\nx += 3\nx"), 8.0)
test_close("aug *=", run("x = 10\nx *= 2\nx"), 20.0)


# ─── Units ───────────────────────────────────────────────────────────────────

print("\n─── VM: Units ───")

r = run("5 MeV")
test("5 MeV is Quantity", isinstance(r, Quantity))
test_display("5 MeV display", r, "5 MeV")

test_display("30 cm", run("30 cm"), "30 cm")
test_display("add units", run("3 MeV + 2 MeV"), "5 MeV")
test_display("scalar mul", run("5 MeV * 3"), "15 MeV")

r = run("10 m / 2 s")
test_close("velocity SI", r, 5.0)
test("velocity dim", r.dim == (1, 0, -1, 0, 0, 0, 0))


# ─── Conversion ──────────────────────────────────────────────────────────────

print("\n─── VM: Conversion ───")

test_display("MeV→eV", run("1 MeV | eV"), "1e+06 eV")
test_display("cm→m", run("100 cm | m"), "1 m")
test_display("pipe var", run("E = 5 MeV\nE | keV"), "5000 keV")


# ─── Dimension errors ───────────────────────────────────────────────────────

print("\n─── VM: Dimension errors ───")

test_raises("add incompatible", (VMError, DimensionError),
    lambda: run("5 MeV + 3 cm"))
test_raises("convert incompatible", (VMError, DimensionError, ValueError),
    lambda: run("5 MeV | m"))


# ─── Constants ───────────────────────────────────────────────────────────────

print("\n─── VM: Constants ───")

test_close("c", run("c"), 299792458.0)
test_close("m_e", run("m_e"), 9.1093837015e-31)
test_display("E=mc²", run("m_e * c**2 | MeV"), "0.51")


# ─── Math functions ──────────────────────────────────────────────────────────

print("\n─── VM: Math ───")

test_close("exp(0)", run("exp(0)"), 1.0)
test_close("exp(1)", run("exp(1)"), math.e)
test_close("log(1)", run("log(1)"), 0.0)
test_close("sqrt(4)", run("sqrt(4)"), 2.0)
test_close("sin(0)", run("sin(0)"), 0.0)
test_close("cos(0)", run("cos(0)"), 1.0)
test_close("pi", run("pi"), math.pi)


# ─── Print ───────────────────────────────────────────────────────────────────

print("\n─── VM: Print ───")

run("print 42")
test("print number", output_capture == ["42"])
run("print 5 MeV")
test("print quantity", output_capture == ["5 MeV"])
run("x = 3\nprint x * 2")
test("print expr", output_capture == ["6"])


# ─── Booleans ────────────────────────────────────────────────────────────────

print("\n─── VM: Booleans ───")

test("3 < 5", run("3 < 5") is True)
test("5 == 5", run("5 == 5") is True)
test("3 > 5", run("3 > 5") is False)
test("and", run("True and False") is False)
test("or", run("True or False") is True)
test("not", run("not True") is False)


# ─── If/else ─────────────────────────────────────────────────────────────────

print("\n─── VM: If/else ───")

test_close("if true", run("x = 5\nif x > 3:\n    y = 1\nelse:\n    y = 0\ny"), 1.0)
test_close("elif", run("x = 1\nif x > 3:\n    y = 1\nelif x > 0:\n    y = 2\nelse:\n    y = 3\ny"), 2.0)


# ─── While ───────────────────────────────────────────────────────────────────

print("\n─── VM: While ───")

test_close("while sum", run("x = 0\ni = 0\nwhile i < 10:\n    x += i\n    i += 1\nx"), 45.0)


# ─── For ─────────────────────────────────────────────────────────────────────

print("\n─── VM: For ───")

test_close("for range", run("total = 0\nfor i in range(5):\n    total += i\ntotal"), 10.0)


# ─── Functions ───────────────────────────────────────────────────────────────

print("\n─── VM: Functions ───")

test_close("simple func", run("def double(x):\n    return x * 2\ndouble(5)"), 10.0)
test_close("two-arg", run("def add(a, b):\n    return a + b\nadd(3, 4)"), 7.0)
test_close("recursion", run("def factorial(n):\n    if n <= 1:\n        return 1\n    return n * factorial(n - 1)\nfactorial(5)"), 120.0)


# ─── Vec/Mat ─────────────────────────────────────────────────────────────────

print("\n─── VM: Vec/Mat ───")

r = run("[1, 2, 3]")
test("vec auto-promote", isinstance(r, Vec))

r = run("[1, 2, 3] m")
test("vec with unit", isinstance(r, Vec))
test_display("vec m display", r, "[1, 2, 3] m")

r = run("norm([3, 4] m)")
test_close("norm SI", r, 5.0)

r = run("dot([1,0,0], [0,1,0])")
test_close("dot orthogonal", r, 0.0)

r = run("dot([10, 0, 0] N, [5, 0, 0] m)")
test_close("work SI", r, 50.0)

r = run("[[1, 2], [3, 4]]")
test("mat auto-promote", isinstance(r, Mat))

test_close("det", run("det([[1, 2], [3, 4]])"), -2.0)

r = run("linsolve([[2,1],[1,3]], [5,10])")
test("linsolve type", isinstance(r, Vec))


# ─── Symbolic ────────────────────────────────────────────────────────────────

print("\n─── VM: Symbolic ───")

r = run('x = sym("x")\nx**2 + 3*x + 2')
test("sym expr", isinstance(r, SymExpr))

r = run('x = sym("x")\ndiff(x**2, x)')
test_display("diff", r, "2*x")

r = run('x = sym("x")\nsubs(x**2, x, 4)')
test_close("subs", r, 16.0)

r = run('x = sym("x")\nsolve(x**2 - 4, x)')
test("solve", isinstance(r, list) and len(r) == 2)

r = run('x = sym("x")\nintegrate(x**2, x)')
test_display("integrate", r, "x^3")

r = run('x = sym("x")\nsin(x)')
test("sin symbolic", isinstance(r, SymExpr))


# ─── Strings ─────────────────────────────────────────────────────────────────

print("\n─── VM: Strings ───")

run('print "hello"')
test("print string", output_capture == ["hello"])


# ─── Disassembly ─────────────────────────────────────────────────────────────

print("\n─── Disassembly ───")

from lexer import lex
from parser import parse
from units import REGISTRY, Constants
UNIT_SYMS = set(REGISTRY._units.keys())
CONST_NAMES = {a for a in dir(Constants) if not a.startswith('_')}

tokens = lex("x = 5\ny = x + 3", UNIT_SYMS, CONST_NAMES)
prog = parse(tokens)
code = compile_program(prog)
disasm = code.disassemble()
test("disasm has LOAD_CONST", "LOAD_CONST" in disasm)
test("disasm has STORE_NAME", "STORE_NAME" in disasm)
test("disasm has ADD", "ADD" in disasm)


# ─── Error handling ──────────────────────────────────────────────────────────

print("\n─── VM: Errors ───")

test_raises("undefined var", (VMError, NameError),
    lambda: run("undefined_var"))
test_raises("wrong argc", (VMError, TypeError),
    lambda: run("def f(x):\n    return x\nf(1, 2)"))


# ─── Physics program ────────────────────────────────────────────────────────

print("\n─── VM: Physics program ───")

src = """E = 5 MeV
mu = 0.0494
x = 30
atten = exp(-mu * x)
I = E * atten
print I | MeV"""
run(src)
test("physics output", len(output_capture) == 1)
val = float(output_capture[0].split()[0])
expected = 5.0 * math.exp(-0.0494 * 30)
test_close("physics value", Quantity(val), expected, rel_tol=1e-3)


# ─── Summary ─────────────────────────────────────────────────────────────────

print(f"\n{'='*50}")
print(f"  Results: {passed} passed, {failed} failed")
print(f"{'='*50}")
sys.exit(0 if failed == 0 else 1)
