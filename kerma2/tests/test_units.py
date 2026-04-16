"""Tests for kerma.units"""

from units import (
    Quantity, DimensionError, REGISTRY, Constants,
    sqrt, exp, log, sin, cos, dim_str, DIMENSIONLESS,
)
import math

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


def test_raises(name, exc_type, func):
    global passed, failed
    try:
        func()
        failed += 1
        print(f"  ✗ {name} (no exception raised)")
    except exc_type:
        passed += 1
        print(f"  ✓ {name}")
    except Exception as e:
        failed += 1
        print(f"  ✗ {name} (wrong exception: {type(e).__name__}: {e})")


# ── Construction ──
print("\n── Construction ──")
E = Quantity.from_unit(5, "MeV")
test("5 MeV value in SI", math.isclose(E.value, 5 * 1.602176634e-19 * 1e6, rel_tol=1e-9))
test("5 MeV dimension is energy", E.dim == (2, 1, -2, 0, 0, 0, 0))

x = Quantity.from_unit(30, "cm")
test("30 cm value in SI", math.isclose(x.value, 0.30, rel_tol=1e-9))
test("30 cm dimension is length", x.dim == (1, 0, 0, 0, 0, 0, 0))

# ── Addition / subtraction ──
print("\n── Addition / subtraction ──")
a = Quantity.from_unit(3, "MeV")
b = Quantity.from_unit(2, "MeV")
c = a + b
test("3 MeV + 2 MeV = 5 MeV", math.isclose(c.value, E.value, rel_tol=1e-9))

d = a - b
test("3 MeV - 2 MeV = 1 MeV",
     math.isclose(d.value, 1 * 1.602176634e-19 * 1e6, rel_tol=1e-9))

test_raises("MeV + cm raises DimensionError", DimensionError,
            lambda: Quantity.from_unit(5, "MeV") + Quantity.from_unit(3, "cm"))

# ── Multiplication / division ──
print("\n── Multiplication / division ──")
force = Quantity.from_unit(10, "N")
dist = Quantity.from_unit(5, "m")
work = force * dist
test("10 N * 5 m has energy dimensions", work.dim == (2, 1, -2, 0, 0, 0, 0))
test("10 N * 5 m = 50 J", math.isclose(work.value, 50.0, rel_tol=1e-9))

speed = dist / Quantity.from_unit(2, "s")
test("5 m / 2 s has velocity dimensions", speed.dim == (1, 0, -1, 0, 0, 0, 0))
test("5 m / 2 s = 2.5 m/s", math.isclose(speed.value, 2.5, rel_tol=1e-9))

test("3 * (2 MeV) = 6 MeV",
     math.isclose((3 * b).value, 3 * b.value, rel_tol=1e-9))

# ── Power ──
print("\n── Power ──")
length = Quantity.from_unit(4, "m")
area = length ** 2
test("(4 m)^2 has area dimensions", area.dim == (2, 0, 0, 0, 0, 0, 0))
test("(4 m)^2 = 16 m²", math.isclose(area.value, 16.0))

# ── Unit conversion ──
print("\n── Unit conversion ──")
E_keV = E.to("keV")
test("5 MeV → 5000 keV", "5000 keV" in repr(E_keV))

E_J = E.to("J")
test("5 MeV → joules", math.isclose(E_J.value, 5 * 1.602176634e-13, rel_tol=1e-9))

test_raises("MeV → cm raises DimensionError", DimensionError, lambda: E.to("cm"))

dist_m = Quantity.from_unit(150, "cm").to("m")
test("150 cm → 1.5 m", math.isclose(dist_m.value, 1.5, rel_tol=1e-9))

# ── Comparison ──
print("\n── Comparison ──")
test("3 MeV < 5 MeV", Quantity.from_unit(3, "MeV") < Quantity.from_unit(5, "MeV"))
test("5 MeV >= 5 MeV", Quantity.from_unit(5, "MeV") >= Quantity.from_unit(5, "MeV"))
test("5 MeV == 5 MeV", Quantity.from_unit(5, "MeV") == Quantity.from_unit(5, "MeV"))
test_raises("5 MeV < 3 cm raises DimensionError", DimensionError,
            lambda: Quantity.from_unit(5, "MeV") < Quantity.from_unit(3, "cm"))

# ── Math functions ──
print("\n── Math functions ──")
test("sqrt(4 m²) = 2 m",
     sqrt(Quantity(4.0, (2,0,0,0,0,0,0))) == Quantity(2.0, (1,0,0,0,0,0,0)))
test("exp(0) = 1", exp(Quantity(0.0)) == Quantity(1.0))
test("log(e) ≈ 1", math.isclose(log(Quantity(math.e)).value, 1.0, rel_tol=1e-9))
test("sin(0) = 0", math.isclose(sin(Quantity(0.0)).value, 0.0, abs_tol=1e-15))
test("cos(0) = 1", math.isclose(cos(Quantity(0.0)).value, 1.0, rel_tol=1e-9))
test_raises("exp(5 MeV) raises DimensionError", DimensionError,
            lambda: exp(Quantity.from_unit(5, "MeV")))

# ── Physics scenario: attenuation ──
print("\n── Physics: attenuation ──")
mu = Quantity.from_unit(0.0494, "cm⁻¹")
thickness = Quantity.from_unit(30, "cm")
exponent = mu * thickness
test("mu * x is dimensionless", exponent.is_dimensionless)
atten = exp(-exponent)
test("exp(-mu*x) is dimensionless", atten.is_dimensionless)
test("exp(-0.0494*30) ≈ 0.2276",
     math.isclose(atten.value, math.exp(-0.0494 * 30), rel_tol=1e-4))

# ── Nuclear units ──
print("\n── Nuclear units ──")
activity = Quantity.from_unit(1, "Ci")
activity_Bq = activity.to("Bq")
test("1 Ci = 3.7e10 Bq", math.isclose(activity_Bq.value, 3.7e10, rel_tol=1e-6))

dose_rad = Quantity.from_unit(100, "rad")
dose_Gy = dose_rad.to("Gy")
test("100 rad = 1 Gy", math.isclose(dose_Gy.value, 1.0, rel_tol=1e-9))

xs = Quantity.from_unit(585, "barn")
test("585 barn has area dimensions", xs.dim == (2, 0, 0, 0, 0, 0, 0))

# ── Constants ──
print("\n── Physical constants ──")
E_rest = Constants.m_e * Constants.c ** 2
E_rest_MeV = E_rest.to("MeV")
test("m_e * c² ≈ 0.511 MeV", "0.51" in repr(E_rest_MeV))
test("c has velocity dimensions", Constants.c.dim == (1, 0, -1, 0, 0, 0, 0))
test("h has action dimensions", Constants.h.dim == (2, 1, -1, 0, 0, 0, 0))
test("k_B has J/K dimensions", Constants.k_B.dim == (2, 1, -2, 0, -1, 0, 0))

# ── Display ──
print("\n── Display ──")
print(f"  repr(5 MeV)    = {repr(Quantity.from_unit(5, 'MeV'))}")
print(f"  repr(30 cm)    = {repr(Quantity.from_unit(30, 'cm'))}")
print(f"  repr(m_e*c²)   = {repr(E_rest_MeV)}")
print(f"  repr(585 barn) = {repr(xs)}")
print(f"  repr(1 Ci)     = {repr(activity)}")
print(f"  repr(atten)    = {repr(atten)}")

# ── Summary ──
print(f"\n{'='*50}")
print(f"Results: {passed} passed, {failed} failed, {passed+failed} total")
if failed == 0:
    print("All tests passed! ✓")
else:
    print(f"{failed} test(s) FAILED ✗")
