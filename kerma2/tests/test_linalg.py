"""Tests for Kerma Vec/Mat types and linear algebra."""

import sys, math
sys.path.insert(0, "/home/claude/kerma")

from interpreter import run_source
from units import Quantity, DimensionError
from linalg import Vec, Mat

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


# ─── Vec creation ────────────────────────────────────────────────────────────

print("\n─── Vec creation ───")

r = run("[1, 2, 3]")
test("auto-promote to Vec", isinstance(r, Vec))
test("Vec size", r.size == 3)
test_display("Vec display", r, "[1, 2, 3]")

r = run("[1, 2, 3] m")
test("Vec with unit", isinstance(r, Vec))
test("Vec dim is length", r.dim == (1, 0, 0, 0, 0, 0, 0))
test_display("Vec m display", r, "[1, 2, 3] m")

r = run("[5, 10] MeV")
test("Vec MeV", isinstance(r, Vec))
test("Vec MeV dim", r.dim == (2, 1, -2, 0, 0, 0, 0))
test_display("Vec MeV display", r, "[5, 10] MeV")

r = run("[0, -9.81, 0] m/s")
test("Vec compound unit", isinstance(r, Vec))
test("Vec m/s dim", r.dim == (1, 0, -1, 0, 0, 0, 0))


# ─── Vec arithmetic ─────────────────────────────────────────────────────────

print("\n─── Vec arithmetic ───")

r = run("a = [1, 2, 3] m\nb = [4, 5, 6] m\na + b")
test("Vec addition", isinstance(r, Vec))
test_display("Vec add values", r, "[5, 7, 9] m")

r = run("a = [10, 20] m\nb = [3, 5] m\na - b")
test_display("Vec subtraction", r, "[7, 15] m")

r = run("v = [1, 2, 3] m\nv * 2")
test_display("Vec scalar multiply", r, "[2, 4, 6] m")

r = run("v = [10, 20] m\nv / 2")
test_display("Vec scalar divide", r, "[5, 10] m")

r = run("-[1, 2, 3]")
test("Vec negate", isinstance(r, Vec))
test_display("Vec negate values", r, "[-1, -2, -3]")

# Unit propagation: m * s⁻¹ = m/s ... not easy in Kerma syntax yet
# But we can test via Quantity multiply
r = run("v = [3, 4] m\nt = 2 s\nv / t")
test("Vec / Quantity dims", r.dim == (1, 0, -1, 0, 0, 0, 0))

test_raises("Vec add incompatible", (Exception,),
    lambda: run("[1, 2] m + [1, 2] s"))


# ─── Vec operations ──────────────────────────────────────────────────────────

print("\n─── Vec operations ───")

r = run("v = [3, 4] m\nnorm(v)")
test("norm type", isinstance(r, Quantity))
test_close("norm value", r, 5.0)
test("norm dim", r.dim == (1, 0, 0, 0, 0, 0, 0))

r = run("a = [1, 0, 0] m\nb = [0, 1, 0] m\ndot(a, b)")
test_close("dot orthogonal", r, 0.0)

r = run("a = [3, 4] m\nb = [3, 4] m\ndot(a, b)")
test_close("dot parallel", r, 25.0)
test("dot dim is area", r.dim == (2, 0, 0, 0, 0, 0, 0))

# Dot with different units: N · m = J
r = run("F = [10, 0, 0] N\nd = [5, 0, 0] m\ndot(F, d)")
test_close("work = F·d SI", r, 50.0)
test("work dim is energy", r.dim == (2, 1, -2, 0, 0, 0, 0))

r = run("a = [1, 0, 0]\nb = [0, 1, 0]\ncross(a, b)")
test("cross product", isinstance(r, Vec))
test_display("cross result", r, "[0, 0, 1]")

r = run("a = [1, 0, 0] m\nb = [0, 1, 0] N\ncross(a, b)")
test("cross mixed units dim", r.dim == (2, 1, -2, 0, 0, 0, 0))


# ─── Vec indexing ────────────────────────────────────────────────────────────

print("\n─── Vec indexing ───")

r = run("v = [10, 20, 30] m\nv[0]")
test("Vec index type", isinstance(r, Quantity))
test("Vec index dim", r.dim == (1, 0, 0, 0, 0, 0, 0))
test_display("Vec index display", r, "10 m")

r = run("v = [10, 20, 30]\nv[2]")
test_close("Vec index value", r, 30.0)

r = run("v = [10, 20, 30]\nlen(v)")
test("Vec len", r == 3)


# ─── Mat creation ────────────────────────────────────────────────────────────

print("\n─── Mat creation ───")

r = run("[[1, 2], [3, 4]]")
test("auto-promote to Mat", isinstance(r, Mat))
test("Mat shape", r.shape == (2, 2))
test_display("Mat display", r, "[[1, 2], [3, 4]]")

r = run("[[1, 0, 0], [0, 1, 0], [0, 0, 1]]")
test("3x3 identity", isinstance(r, Mat) and r.shape == (3, 3))


# ─── Mat arithmetic ─────────────────────────────────────────────────────────

print("\n─── Mat arithmetic ───")

r = run("A = [[1, 2], [3, 4]]\nB = [[5, 6], [7, 8]]\nA + B")
test("Mat addition", isinstance(r, Mat))
test_display("Mat add", r, "[[6, 8], [10, 12]]")

r = run("A = [[1, 2], [3, 4]]\nA * 2")
test_display("Mat scalar multiply", r, "[[2, 4], [6, 8]]")

r = run("-[[1, 2], [3, 4]]")
test_display("Mat negate", r, "[[-1, -2], [-3, -4]]")


# ─── Mat operations ──────────────────────────────────────────────────────────

print("\n─── Mat operations ───")

r = run("A = [[1, 2], [3, 4]]\ntranspose(A)")
test("transpose", isinstance(r, Mat))
test_display("transpose values", r, "[[1, 3], [2, 4]]")

r = run("A = [[1, 2], [3, 4]]\ndet(A)")
test("det type", isinstance(r, Quantity))
test_close("det value", r, -2.0)

r = run("A = [[1, 0], [0, 1]]\ninv(A)")
test("inv identity", isinstance(r, Mat))
test_display("inv identity values", r, "[[1, 0], [0, 1]]")

r = run("A = [[2, 0], [0, 3]]\ninv(A)")
test_display("inv diagonal", r, "[[0.5, 0], [0, 0.333333]]")

r = run("M = [[1, 2], [3, 4]]\nM[0]")
test("Mat row index", isinstance(r, Vec))
test_display("Mat row", r, "[1, 2]")


# ─── Linear solve ───────────────────────────────────────────────────────────

print("\n─── Linear solve ───")

# Solve: 2x + y = 5, x + 3y = 10 → x=1, y=3
r = run("A = [[2, 1], [1, 3]]\nb = [5, 10]\nx = linsolve(A, b)\nx")
test("linsolve type", isinstance(r, Vec))
test("linsolve size", r.size == 2)
# Check values
r0 = run("A = [[2, 1], [1, 3]]\nb = [5, 10]\nx = linsolve(A, b)\nx[0]")
test_close("linsolve x[0] = 1", r0, 1.0)
r1 = run("A = [[2, 1], [1, 3]]\nb = [5, 10]\nx = linsolve(A, b)\nx[1]")
test_close("linsolve x[1] = 3", r1, 3.0)

# Identity matrix
r = run("eye(3)")
test("eye type", isinstance(r, Mat))
test("eye shape", r.shape == (3, 3))


# ─── Physics with vectors ───────────────────────────────────────────────────

print("\n─── Physics with vectors ───")

# Kinematics: v_f = v_i + a*t
# Note: m/s parses as a compound unit, but m/s/s won't chain well.
# Use explicit multiplication: a = [0, -9.81, 0] * 1 m / (1 s * 1 s)
# Simpler: just use dimensionless for this test
r = run("""v_i = [10, 0, 0]
a = [0, -9.81, 0]
t = 2
v_f = v_i + a * t
v_f""")
test("kinematics type", isinstance(r, Vec))
r0 = run("""v_i = [10, 0, 0]
a = [0, -9.81, 0]
t = 2
v_f = v_i + a * t
v_f[0]""")
test_close("vf_x", r0, 10.0)

r1 = run("""v_i = [10, 0, 0]
a = [0, -9.81, 0]
t = 2
v_f = v_i + a * t
v_f[1]""")
test_close("vf_y", r1, -19.62)

# Work done: W = F · d
run("""F = [100, 0, 50] N
d = [3, 0, 0] m
W = dot(F, d)
print W | J""")
test("work output", len(output_capture) == 1)
test("work display", "300" in output_capture[0])

# Cross product: torque = r × F
r = run("""r = [0, 0, 2] m
F = [10, 0, 0] N
tau = cross(r, F)
tau""")
test("torque type", isinstance(r, Vec))
test("torque dim", r.dim == (2, 1, -2, 0, 0, 0, 0))


# ─── Print Vec/Mat ──────────────────────────────────────────────────────────

print("\n─── Print Vec/Mat ───")

run("print [1, 2, 3] m")
test("print Vec", "1, 2, 3" in output_capture[0] and "m" in output_capture[0])

run("print [[1, 0], [0, 1]]")
test("print Mat", "1" in output_capture[0] and "0" in output_capture[0])


# ─── Error handling ──────────────────────────────────────────────────────────

print("\n─── Errors ───")

test_raises("add incompatible Vec", (Exception,),
    lambda: run("[1,2] m + [1,2] s"))

test_raises("dot size mismatch", (Exception,),
    lambda: run("dot([1,2], [1,2,3])"))

test_raises("cross not 3D", (Exception,),
    lambda: run("cross([1,2], [3,4])"))

test_raises("inv non-square", (Exception,),
    lambda: run("inv([[1,2,3],[4,5,6]])"))


# ─── Summary ─────────────────────────────────────────────────────────────────

print(f"\n{'='*50}")
print(f"  Results: {passed} passed, {failed} failed")
print(f"{'='*50}")
sys.exit(0 if failed == 0 else 1)
