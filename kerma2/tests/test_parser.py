"""Tests for the Kerma parser."""

import sys
sys.path.insert(0, "/home/claude/kerma")

from lexer import lex, TokenType
from parser import parse, ParseError
from ast_nodes import *
from units import REGISTRY, Constants

UNIT_SYMS = set(REGISTRY._units.keys())
CONST_NAMES = {a for a in dir(Constants) if not a.startswith('_')}

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

def test_raises(name, exc_type, fn):
    global passed, failed
    try:
        fn()
        failed += 1
        print(f"  ✗ {name} (no exception raised)")
    except exc_type:
        passed += 1
        print(f"  ✓ {name}")
    except Exception as e:
        failed += 1
        print(f"  ✗ {name} (got {type(e).__name__}: {e})")

def p(source):
    tokens = lex(source, UNIT_SYMS, CONST_NAMES)
    return parse(tokens)


# ─── Simple expressions ─────────────────────────────────────────────────────

print("\n─── Atoms ───")

prog = p("42")
test("number literal", isinstance(prog.body[0], ExprStatement)
     and isinstance(prog.body[0].expr, NumberLiteral)
     and prog.body[0].expr.value == 42.0)

prog = p('"hello"')
test("string literal", isinstance(prog.body[0].expr, StringLiteral)
     and prog.body[0].expr.value == "hello")

prog = p("True")
test("bool true", isinstance(prog.body[0].expr, BoolLiteral) and prog.body[0].expr.value is True)

prog = p("False")
test("bool false", isinstance(prog.body[0].expr, BoolLiteral) and prog.body[0].expr.value is False)

prog = p("None")
test("none", isinstance(prog.body[0].expr, NoneLiteral))

prog = p("x")
test("identifier", isinstance(prog.body[0].expr, Identifier) and prog.body[0].expr.name == "x")

prog = p("c")
test("constant ref", isinstance(prog.body[0].expr, ConstantRef) and prog.body[0].expr.name == "c")


# ─── Arithmetic ──────────────────────────────────────────────────────────────

print("\n─── Arithmetic ───")

prog = p("1 + 2")
expr = prog.body[0].expr
test("addition", isinstance(expr, BinOp) and expr.op == '+')

prog = p("3 * 4 + 5")
expr = prog.body[0].expr
test("precedence: * before +", expr.op == '+' and expr.left.op == '*')

prog = p("2 ** 3 ** 2")
expr = prog.body[0].expr
test("power right-associative", expr.op == '**' and expr.right.op == '**')

prog = p("(1 + 2) * 3")
expr = prog.body[0].expr
test("grouped expression", expr.op == '*' and isinstance(expr.left, BinOp) and expr.left.op == '+')

prog = p("-5")
expr = prog.body[0].expr
test("unary minus", isinstance(expr, UnaryOp) and expr.op == '-')

prog = p("a % b")
expr = prog.body[0].expr
test("modulo", isinstance(expr, BinOp) and expr.op == '%')


# ─── Comparison ──────────────────────────────────────────────────────────────

print("\n─── Comparison ───")

prog = p("a < b")
expr = prog.body[0].expr
test("less than", isinstance(expr, Compare) and expr.ops == ['<'])

prog = p("a == b")
expr = prog.body[0].expr
test("equality", isinstance(expr, Compare) and expr.ops == ['=='])

prog = p("a < b < d")
expr = prog.body[0].expr
test("chained comparison", isinstance(expr, Compare) and expr.ops == ['<', '<'] and len(expr.operands) == 3)

prog = p("a != b")
expr = prog.body[0].expr
test("not equal", isinstance(expr, Compare) and expr.ops == ['!='])


# ─── Boolean ─────────────────────────────────────────────────────────────────

print("\n─── Boolean ───")

prog = p("a and b")
expr = prog.body[0].expr
test("and", isinstance(expr, BoolOp) and expr.op == 'and')

prog = p("a or b")
expr = prog.body[0].expr
test("or", isinstance(expr, BoolOp) and expr.op == 'or')

prog = p("not a")
expr = prog.body[0].expr
test("not", isinstance(expr, UnaryOp) and expr.op == 'not')

prog = p("a and b or d")
expr = prog.body[0].expr
test("or lower than and", isinstance(expr, BoolOp) and expr.op == 'or')


# ─── Unit attachment ─────────────────────────────────────────────────────────

print("\n─── Unit attachment ───")

prog = p("5 MeV")
expr = prog.body[0].expr
test("5 MeV", isinstance(expr, UnitAttach)
     and isinstance(expr.value, NumberLiteral) and expr.value.value == 5.0
     and isinstance(expr.unit, UnitLiteral) and expr.unit.symbol == "MeV")

prog = p("3.7 cm")
expr = prog.body[0].expr
test("3.7 cm", isinstance(expr, UnitAttach) and expr.unit.symbol == "cm")

prog = p("[1, 2, 3] m")
expr = prog.body[0].expr
test("vector with unit", isinstance(expr, UnitAttach) and isinstance(expr.value, ListLiteral))

# Compound unit: m/s
prog = p("10 m/s")
expr = prog.body[0].expr
test("compound unit m/s", isinstance(expr, UnitAttach)
     and isinstance(expr.unit, BinOp) and expr.unit.op == '/')


# ─── Pipe conversion ────────────────────────────────────────────────────────

print("\n─── Pipe conversion ───")

prog = p("E | eV")
expr = prog.body[0].expr
test("pipe convert", isinstance(expr, PipeConvert) and expr.target_unit == "eV")

prog = p("5 MeV | J")
expr = prog.body[0].expr
test("value pipe convert", isinstance(expr, PipeConvert) and expr.target_unit == "J")


# ─── Function calls ─────────────────────────────────────────────────────────

print("\n─── Function calls ───")

prog = p("f(x)")
expr = prog.body[0].expr
test("simple call", isinstance(expr, Call) and isinstance(expr.func, Identifier)
     and expr.func.name == "f" and len(expr.args) == 1)

prog = p("exp(-mu * x)")
expr = prog.body[0].expr
test("exp call", isinstance(expr, Call) and expr.func.name == "exp")
test("exp arg is binop with unary", isinstance(expr.args[0], BinOp)
     and isinstance(expr.args[0].left, UnaryOp))

prog = p("f(1, 2, 3)")
expr = prog.body[0].expr
test("multi-arg call", isinstance(expr, Call) and len(expr.args) == 3)

prog = p("diff(f, x)")
expr = prog.body[0].expr
test("diff call", isinstance(expr, Call) and expr.func.name == "diff")

# Method call
prog = p("E.to(eV)")
expr = prog.body[0].expr
test("method call", isinstance(expr, Call)
     and isinstance(expr.func, Attribute)
     and expr.func.attr == "to")


# ─── Indexing ────────────────────────────────────────────────────────────────

print("\n─── Indexing ───")

prog = p("v[0]")
expr = prog.body[0].expr
test("index", isinstance(expr, Index) and isinstance(expr.obj, Identifier))

prog = p("mat[1][2]")
expr = prog.body[0].expr
test("double index", isinstance(expr, Index) and isinstance(expr.obj, Index))


# ─── Lists ──────────────────────────────────────────────────────────────────

print("\n─── Lists ───")

prog = p("[1, 2, 3]")
expr = prog.body[0].expr
test("list literal", isinstance(expr, ListLiteral) and len(expr.elements) == 3)

prog = p("[[1, 2], [3, 4]]")
expr = prog.body[0].expr
test("nested list", isinstance(expr, ListLiteral) and isinstance(expr.elements[0], ListLiteral))

prog = p("[]")
expr = prog.body[0].expr
test("empty list", isinstance(expr, ListLiteral) and len(expr.elements) == 0)


# ─── Assignment ──────────────────────────────────────────────────────────────

print("\n─── Assignment ───")

prog = p("x = 5")
stmt = prog.body[0]
test("simple assignment", isinstance(stmt, Assignment) and stmt.target == "x")

prog = p("E = 5 MeV")
stmt = prog.body[0]
test("unit assignment", isinstance(stmt, Assignment)
     and isinstance(stmt.value, UnitAttach))

prog = p("x += 1")
stmt = prog.body[0]
test("aug assign +=", isinstance(stmt, AugAssignment) and stmt.op == '+')

prog = p("x *= 2")
stmt = prog.body[0]
test("aug assign *=", isinstance(stmt, AugAssignment) and stmt.op == '*')


# ─── Print ───────────────────────────────────────────────────────────────────

print("\n─── Print ───")

prog = p("print x")
stmt = prog.body[0]
test("print statement", isinstance(stmt, PrintStatement)
     and isinstance(stmt.value, Identifier))

prog = p("print 5 MeV")
stmt = prog.body[0]
test("print unit", isinstance(stmt, PrintStatement)
     and isinstance(stmt.value, UnitAttach))


# ─── If/elif/else ────────────────────────────────────────────────────────────

print("\n─── If/elif/else ───")

prog = p("""if x > 0:
    y = 1""")
stmt = prog.body[0]
test("simple if", isinstance(stmt, IfStatement) and len(stmt.body) == 1)

prog = p("""if x > 0:
    y = 1
else:
    y = 0""")
stmt = prog.body[0]
test("if-else", isinstance(stmt, IfStatement) and len(stmt.else_body) == 1)

prog = p("""if x > 0:
    y = 1
elif x == 0:
    y = 0
else:
    y = -1""")
stmt = prog.body[0]
test("if-elif-else", isinstance(stmt, IfStatement) and len(stmt.elif_clauses) == 1)


# ─── While ───────────────────────────────────────────────────────────────────

print("\n─── While ───")

prog = p("""while x > 0:
    x -= 1""")
stmt = prog.body[0]
test("while loop", isinstance(stmt, WhileStatement) and len(stmt.body) == 1)


# ─── For ─────────────────────────────────────────────────────────────────────

print("\n─── For ───")

prog = p("""for i in items:
    print i""")
stmt = prog.body[0]
test("for loop", isinstance(stmt, ForStatement) and stmt.var == "i")


# ─── Function definition ────────────────────────────────────────────────────

print("\n─── Function definition ───")

prog = p("""def f(x):
    return x * 2""")
stmt = prog.body[0]
test("func def", isinstance(stmt, FuncDef) and stmt.name == "f" and stmt.params == ["x"])
test("func body", len(stmt.body) == 1 and isinstance(stmt.body[0], Return))

prog = p("""def cross_section(E, Z):
    sigma = 585 barn
    return sigma""")
stmt = prog.body[0]
test("multi-param func", stmt.params == ["E", "Z"])
test("multi-stmt body", len(stmt.body) == 2)


# ─── Nested blocks ──────────────────────────────────────────────────────────

print("\n─── Nested blocks ───")

prog = p("""def f(x):
    if x > 0:
        return x
    else:
        return -x""")
stmt = prog.body[0]
test("nested blocks", isinstance(stmt, FuncDef)
     and isinstance(stmt.body[0], IfStatement))


# ─── Multi-statement program ────────────────────────────────────────────────

print("\n─── Multi-statement program ───")

prog = p("""E = 5 MeV
mu = 0.0494
x = 30 cm
dose = E * exp(-mu * x)
print dose""")
test("5-statement program", len(prog.body) == 5)
test("stmt types correct",
     isinstance(prog.body[0], Assignment) and
     isinstance(prog.body[3], Assignment) and
     isinstance(prog.body[4], PrintStatement))


# ─── Physics expression: E = mc² ────────────────────────────────────────────

print("\n─── Physics: E = mc² ───")

prog = p("E_rest = m_e * c**2")
stmt = prog.body[0]
test("E=mc² is assignment", isinstance(stmt, Assignment))
expr = stmt.value
test("E=mc² is multiplication", isinstance(expr, BinOp) and expr.op == '*')
test("left is m_e constant", isinstance(expr.left, ConstantRef) and expr.left.name == "m_e")
test("right is c**2", isinstance(expr.right, BinOp) and expr.right.op == '**'
     and isinstance(expr.right.left, ConstantRef) and expr.right.left.name == "c")


# ─── Error handling ──────────────────────────────────────────────────────────

print("\n─── Errors ───")

test_raises("missing rparen", ParseError, lambda: p("f(x"))
test_raises("missing colon", ParseError, lambda: p("if x\n    y = 1"))
test_raises("missing indent", ParseError, lambda: p("if x:\ny = 1"))


# ─── Summary ─────────────────────────────────────────────────────────────────

print(f"\n{'='*50}")
print(f"  Results: {passed} passed, {failed} failed")
print(f"{'='*50}")
sys.exit(0 if failed == 0 else 1)
