"""Tests for the Kerma lexer."""

import sys
sys.path.insert(0, "/home/claude/kerma")

from lexer import lex, Token, TokenType, LexerError
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

def types(tokens):
    """Extract token types, excluding final EOF."""
    return [t.type for t in tokens if t.type != TokenType.EOF]

def values(tokens):
    """Extract token values, excluding NEWLINE/INDENT/DEDENT/EOF."""
    skip = {TokenType.NEWLINE, TokenType.INDENT, TokenType.DEDENT, TokenType.EOF}
    return [t.value for t in tokens if t.type not in skip]

def tok(source):
    return lex(source, UNIT_SYMS, CONST_NAMES)


# ─── Numbers ─────────────────────────────────────────────────────────────────

print("\n─── Numbers ───")

tokens = tok("42")
test("integer", tokens[0].type == TokenType.NUMBER and tokens[0].value == "42")

tokens = tok("3.14")
test("float", tokens[0].type == TokenType.NUMBER and tokens[0].value == "3.14")

tokens = tok("1e-5")
test("scientific notation", tokens[0].type == TokenType.NUMBER and tokens[0].value == "1e-5")

tokens = tok("6.022e23")
test("scientific float", tokens[0].type == TokenType.NUMBER and tokens[0].value == "6.022e23")

tokens = tok("1_000_000")
test("underscored integer", tokens[0].type == TokenType.NUMBER and tokens[0].value == "1000000")

# ─── Strings ─────────────────────────────────────────────────────────────────

print("\n─── Strings ───")

tokens = tok('"hello world"')
test("double quoted", tokens[0].type == TokenType.STRING and tokens[0].value == "hello world")

tokens = tok("'single'")
test("single quoted", tokens[0].type == TokenType.STRING and tokens[0].value == "single")

tokens = tok(r'"escape\n"')
test("escape sequence", tokens[0].value == "escape\n")

test_raises("unterminated string", LexerError, lambda: tok('"no end'))

# ─── Units ───────────────────────────────────────────────────────────────────

print("\n─── Units ───")

tokens = tok("5 MeV")
test("number then unit", tokens[0].type == TokenType.NUMBER and tokens[1].type == TokenType.UNIT)
test("unit value is MeV", tokens[1].value == "MeV")

tokens = tok("3.7 cm")
test("float then unit", tokens[0].value == "3.7" and tokens[1].value == "cm")

tokens = tok("100 keV")
test("keV recognized", tokens[1].type == TokenType.UNIT and tokens[1].value == "keV")

tokens = tok("1 Sv")
test("Sv recognized", tokens[1].type == TokenType.UNIT)

tokens = tok("585 barn")
# barn's symbol is 'b' but 'barn' isn't in the registry as a symbol
# let's check what the registry says
tokens2 = tok("585 barn")
test("barn symbol", tokens2[1].type == TokenType.UNIT and tokens2[1].value == "barn")

tokens = tok("μg")
test("μg recognized", tokens[0].type == TokenType.UNIT and tokens[0].value == "μg")

tokens = tok("Å")
test("angstrom recognized", tokens[0].type == TokenType.UNIT)

# ─── Constants ───────────────────────────────────────────────────────────────

print("\n─── Constants ───")

tokens = tok("c")
test("speed of light", tokens[0].type == TokenType.CONSTANT and tokens[0].value == "c")

tokens = tok("m_e")
test("electron mass", tokens[0].type == TokenType.CONSTANT)

tokens = tok("k_B")
test("Boltzmann constant", tokens[0].type == TokenType.CONSTANT)

tokens = tok("hbar")
test("hbar", tokens[0].type == TokenType.CONSTANT)

tokens = tok("N_A")
test("Avogadro", tokens[0].type == TokenType.CONSTANT)

# ─── Keywords ────────────────────────────────────────────────────────────────

print("\n─── Keywords ───")

for kw, tt in [("if", TokenType.IF), ("else", TokenType.ELSE), ("while", TokenType.WHILE),
               ("for", TokenType.FOR), ("def", TokenType.DEF), ("return", TokenType.RETURN),
               ("and", TokenType.AND), ("or", TokenType.OR), ("not", TokenType.NOT),
               ("True", TokenType.TRUE), ("False", TokenType.FALSE), ("None", TokenType.NONE),
               ("diff", TokenType.DIFF), ("solve", TokenType.SOLVE), ("print", TokenType.PRINT)]:
    tokens = tok(kw)
    test(f"keyword '{kw}'", tokens[0].type == tt)

# Identifiers that aren't keywords or units
tokens = tok("my_var")
test("identifier", tokens[0].type == TokenType.IDENTIFIER)

tokens = tok("flux_density")
test("underscore identifier", tokens[0].type == TokenType.IDENTIFIER)

# ─── Operators ───────────────────────────────────────────────────────────────

print("\n─── Operators ───")

for op, tt in [("+", TokenType.PLUS), ("-", TokenType.MINUS), ("*", TokenType.STAR),
               ("/", TokenType.SLASH), ("**", TokenType.DOUBLESTAR), ("%", TokenType.PERCENT),
               ("==", TokenType.EQ), ("!=", TokenType.NEQ), ("<", TokenType.LT),
               (">", TokenType.GT), ("<=", TokenType.LTE), (">=", TokenType.GTE),
               ("=", TokenType.ASSIGN), ("+=", TokenType.PLUSEQ), ("-=", TokenType.MINUSEQ),
               ("->", TokenType.ARROW), ("|", TokenType.PIPE)]:
    tokens = tok(f"x {op} y")
    # Find the operator token (skip identifier)
    op_tok = [t for t in tokens if t.type == tt]
    test(f"operator '{op}'", len(op_tok) == 1)

# ─── Delimiters ──────────────────────────────────────────────────────────────

print("\n─── Delimiters ───")

tokens = tok("(1, 2)")
ttypes = types(tokens)
test("parens and comma", TokenType.LPAREN in ttypes and TokenType.RPAREN in ttypes and TokenType.COMMA in ttypes)

tokens = tok("[1, 2, 3]")
ttypes = types(tokens)
test("brackets", TokenType.LBRACKET in ttypes and TokenType.RBRACKET in ttypes)

tokens = tok("{a: 1}")
ttypes = types(tokens)
test("braces and colon", TokenType.LBRACE in ttypes and TokenType.RBRACE in ttypes and TokenType.COLON in ttypes)

# ─── Comments ────────────────────────────────────────────────────────────────

print("\n─── Comments ───")

tokens = tok("x = 5 # this is a comment")
vals = values(tokens)
test("comment stripped", "this" not in vals and "comment" not in vals)
test("code before comment kept", "x" in vals and "5" in vals)

tokens = tok("# full line comment\nx = 1")
vals = values(tokens)
test("full line comment", "x" in vals and "full" not in vals)

# ─── Indentation ─────────────────────────────────────────────────────────────

print("\n─── Indentation ───")

src = """if x:
    y = 1
    z = 2
w = 3"""
tokens = tok(src)
ttypes = types(tokens)
test("INDENT emitted", TokenType.INDENT in ttypes)
test("DEDENT emitted", TokenType.DEDENT in ttypes)
test("one INDENT", ttypes.count(TokenType.INDENT) == 1)
test("one DEDENT", ttypes.count(TokenType.DEDENT) == 1)

src2 = """if x:
    if y:
        z = 1
    w = 2
v = 3"""
tokens = tok(src2)
ttypes = types(tokens)
test("nested indent: 2 INDENTs", ttypes.count(TokenType.INDENT) == 2)
test("nested indent: 2 DEDENTs", ttypes.count(TokenType.DEDENT) == 2)

# Blank lines shouldn't affect indentation
src3 = """if x:
    y = 1

    z = 2
w = 3"""
tokens = tok(src3)
ttypes = types(tokens)
test("blank line doesn't break indent", ttypes.count(TokenType.INDENT) == 1)
test("blank line: still one DEDENT", ttypes.count(TokenType.DEDENT) == 1)

# ─── Implicit line continuation in parens ────────────────────────────────────

print("\n─── Implicit line continuation ───")

src = """x = (1 +
     2 +
     3)"""
tokens = tok(src)
# Should NOT have INDENT/DEDENT inside parens
ttypes = types(tokens)
test("no INDENT inside parens", TokenType.INDENT not in ttypes)
test("no DEDENT inside parens", TokenType.DEDENT not in ttypes)
# Should have the numbers
vals = values(tokens)
test("all values present", "1" in vals and "2" in vals and "3" in vals)

src2 = """v = [1, 2,
     3, 4]"""
tokens = tok(src2)
ttypes = types(tokens)
test("no INDENT inside brackets", TokenType.INDENT not in ttypes)

# ─── Full Kerma expression ──────────────────────────────────────────────────

print("\n─── Full expressions ───")

src = "E = 5 MeV"
tokens = tok(src)
vals = values(tokens)
test("E = 5 MeV tokens", vals == ["E", "=", "5", "MeV"])
test("E is identifier", tokens[0].type == TokenType.IDENTIFIER)
test("= is assign", tokens[1].type == TokenType.ASSIGN)
test("5 is number", tokens[2].type == TokenType.NUMBER)
test("MeV is unit", tokens[3].type == TokenType.UNIT)

src = "dose = E * exp(-mu * x)"
tokens = tok(src)
vals = values(tokens)
test("attenuation expr", vals == ["dose", "=", "E", "*", "exp", "(", "-", "mu", "*", "x", ")"])

src = "v_final = v + a * t"
tokens = tok(src)
vals = values(tokens)
test("kinematics expr", vals == ["v_final", "=", "v", "+", "a", "*", "t"])

src = "E_rest = m_e * c**2"
tokens = tok(src)
vals = values(tokens)
test("E=mc² tokens", vals == ["E_rest", "=", "m_e", "*", "c", "**", "2"])
test("m_e is constant", tokens[2].type == TokenType.CONSTANT)
test("c is constant", tokens[4].type == TokenType.CONSTANT)

# Unit conversion pipe
src = "E | eV"
tokens = tok(src)
test("pipe operator", tokens[1].type == TokenType.PIPE)
test("target unit", tokens[2].type == TokenType.UNIT)

# ─── Matrix/vector literal ──────────────────────────────────────────────────

print("\n─── Matrix/vector literal ───")

src = "v = [1, 2, 3] m"
tokens = tok(src)
vals = values(tokens)
test("vector with unit", vals == ["v", "=", "[", "1", ",", "2", ",", "3", "]", "m"])

src = "A = [[1, 2], [3, 4]]"
tokens = tok(src)
vals = values(tokens)
test("matrix literal", "[[" not in vals)  # brackets are separate tokens
test("matrix has 4 numbers", sum(1 for t in tokens if t.type == TokenType.NUMBER) == 4)

# ─── Function definition ────────────────────────────────────────────────────

print("\n─── Function definition ───")

src = """def cross_section(E):
    sigma = 585 b
    return sigma"""
tokens = tok(src)
ttypes = types(tokens)
test("def keyword", TokenType.DEF in ttypes)
test("return keyword", TokenType.RETURN in ttypes)
test("indent in function", TokenType.INDENT in ttypes)
test("dedent after function", TokenType.DEDENT in ttypes)

# ─── Error handling ──────────────────────────────────────────────────────────

print("\n─── Errors ───")

test_raises("unexpected character", LexerError, lambda: tok("x = 5 `"))
test_raises("unterminated string", LexerError, lambda: tok("'no end"))

# Bad indentation
src_bad = """if x:
    y = 1
  z = 2"""
test_raises("inconsistent indentation", LexerError, lambda: tok(src_bad))

# ─── Line/col tracking ──────────────────────────────────────────────────────

print("\n─── Position tracking ───")

src = "x = 5\ny = 10"
tokens = tok(src)
test("first token line 1", tokens[0].line == 1)
test("first token col 1", tokens[0].col == 1)
# y should be on line 2
y_tok = [t for t in tokens if t.value == "y"][0]
test("y on line 2", y_tok.line == 2)


# ─── Summary ─────────────────────────────────────────────────────────────────

print(f"\n{'='*50}")
print(f"  Results: {passed} passed, {failed} failed")
print(f"{'='*50}")
sys.exit(0 if failed == 0 else 1)
