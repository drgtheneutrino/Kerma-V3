"""
Kerma Lexer
===========
Transforms source text into a stream of tokens.

Key features:
  - Python-style INDENT/DEDENT from whitespace
  - Unit literals recognized as distinct tokens (5 MeV, 3.7 cm)
  - Operator tokens for math, comparison, assignment
  - Identifier/keyword discrimination
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterator


class TokenType(Enum):
    # Literals
    NUMBER      = auto()  # 3.14, 1e-5, 42
    STRING      = auto()  # "hello", 'world'
    UNIT        = auto()  # MeV, cm, kg (resolved against registry)
    IDENTIFIER  = auto()  # variable/function names
    CONSTANT    = auto()  # built-in constant names (c, h, k_B, ...)

    # Keywords
    IF          = auto()
    ELIF        = auto()
    ELSE        = auto()
    WHILE       = auto()
    FOR         = auto()
    IN          = auto()
    DEF         = auto()
    RETURN      = auto()
    AND         = auto()
    OR          = auto()
    NOT         = auto()
    TRUE        = auto()
    FALSE       = auto()
    NONE        = auto()
    PRINT       = auto()
    LET         = auto()

    # Math / symbolic keywords
    DIFF        = auto()
    INTEGRATE   = auto()
    SIMPLIFY    = auto()
    SOLVE       = auto()
    SUBS        = auto()

    # Operators
    PLUS        = auto()  # +
    MINUS       = auto()  # -
    STAR        = auto()  # *
    SLASH       = auto()  # /
    DOUBLESTAR  = auto()  # **
    PERCENT     = auto()  # %
    DOT         = auto()  # .

    # Comparison
    EQ          = auto()  # ==
    NEQ         = auto()  # !=
    LT          = auto()  # <
    GT          = auto()  # >
    LTE         = auto()  # <=
    GTE         = auto()  # >=

    # Assignment
    ASSIGN      = auto()  # =
    PLUSEQ      = auto()  # +=
    MINUSEQ     = auto()  # -=
    STAREQ      = auto()  # *=
    SLASHEQ     = auto()  # /=

    # Delimiters
    LPAREN      = auto()  # (
    RPAREN      = auto()  # )
    LBRACKET    = auto()  # [
    RBRACKET    = auto()  # ]
    LBRACE      = auto()  # {
    RBRACE      = auto()  # }
    COMMA       = auto()  # ,
    COLON       = auto()  # :
    SEMICOLON   = auto()  # ;
    ARROW       = auto()  # ->
    PIPE        = auto()  # | (for unit conversion: x | MeV)

    # Structure
    NEWLINE     = auto()
    INDENT      = auto()
    DEDENT      = auto()
    EOF         = auto()


KEYWORDS = {
    "if": TokenType.IF, "elif": TokenType.ELIF, "else": TokenType.ELSE,
    "while": TokenType.WHILE, "for": TokenType.FOR, "in": TokenType.IN,
    "def": TokenType.DEF, "return": TokenType.RETURN,
    "and": TokenType.AND, "or": TokenType.OR, "not": TokenType.NOT,
    "True": TokenType.TRUE, "False": TokenType.FALSE, "None": TokenType.NONE,
    "print": TokenType.PRINT, "let": TokenType.LET,
    "diff": TokenType.DIFF, "integrate": TokenType.INTEGRATE,
    "simplify": TokenType.SIMPLIFY, "solve": TokenType.SOLVE, "subs": TokenType.SUBS,
}


@dataclass(frozen=True)
class Token:
    type: TokenType
    value: str
    line: int
    col: int

    def __repr__(self):
        if self.type in (TokenType.NEWLINE, TokenType.INDENT, TokenType.DEDENT, TokenType.EOF):
            return f"{self.type.name}"
        return f"{self.type.name}({self.value!r})"


class LexerError(Exception):
    def __init__(self, message: str, line: int, col: int):
        self.line = line
        self.col = col
        super().__init__(f"Line {line}, col {col}: {message}")


class Lexer:
    """
    Tokenizes Kerma source code.

    Usage:
        lexer = Lexer(source, unit_symbols={'MeV', 'cm', 'kg', ...})
        tokens = lexer.tokenize()
    """

    def __init__(self, source: str, unit_symbols: set[str] = None, constant_names: set[str] = None):
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.unit_symbols = unit_symbols or set()
        self.constant_names = constant_names or set()
        self.tokens: list[Token] = []

        # Indentation tracking
        self.indent_stack = [0]  # stack of indent levels
        self.at_line_start = True
        self.paren_depth = 0  # inside parens/brackets, ignore indentation

    def tokenize(self) -> list[Token]:
        """Tokenize the entire source and return a list of tokens."""
        self.tokens = []
        while self.pos < len(self.source):
            if self.at_line_start and self.paren_depth == 0:
                self._handle_indentation()
            self._skip_whitespace_inline()
            if self.pos >= len(self.source):
                break
            ch = self.source[self.pos]
            if ch == '\n':
                self._handle_newline()
            elif ch == '#':
                self._skip_comment()
            elif ch in ('"', "'"):
                self._read_string()
            elif ch.isdigit() or (ch == '.' and self._peek_next().isdigit()):
                self._read_number()
            elif ch.isalpha() or ch == '_' or ch in ('μ', 'Å', 'Ω'):
                self._read_identifier_or_unit()
            else:
                self._read_operator()

        # Emit final NEWLINE if needed
        if self.tokens and self.tokens[-1].type != TokenType.NEWLINE:
            self.tokens.append(Token(TokenType.NEWLINE, "\\n", self.line, self.col))

        # Close remaining indents
        while len(self.indent_stack) > 1:
            self.indent_stack.pop()
            self.tokens.append(Token(TokenType.DEDENT, "", self.line, self.col))

        self.tokens.append(Token(TokenType.EOF, "", self.line, self.col))
        return self.tokens

    # ── Indentation handling ─────────────────────────────────────────────

    def _handle_indentation(self):
        """Process leading whitespace at the start of a line."""
        indent = 0
        while self.pos < len(self.source) and self.source[self.pos] in (' ', '\t'):
            if self.source[self.pos] == '\t':
                indent += 4  # treat tab as 4 spaces
            else:
                indent += 1
            self._advance()

        # Skip blank lines and comment-only lines
        if self.pos >= len(self.source) or self.source[self.pos] in ('\n', '#'):
            self.at_line_start = True
            return

        self.at_line_start = False
        current = self.indent_stack[-1]

        if indent > current:
            self.indent_stack.append(indent)
            self.tokens.append(Token(TokenType.INDENT, "", self.line, 1))
        elif indent < current:
            while self.indent_stack[-1] > indent:
                self.indent_stack.pop()
                self.tokens.append(Token(TokenType.DEDENT, "", self.line, 1))
            if self.indent_stack[-1] != indent:
                raise LexerError(f"Inconsistent indentation (got {indent}, expected {self.indent_stack[-1]})",
                                 self.line, 1)

    def _handle_newline(self):
        """Emit NEWLINE token and set up for indentation processing."""
        if self.paren_depth > 0:
            # Inside parens/brackets — treat newline as whitespace
            self._advance()
            return
        # Only emit NEWLINE if the previous token isn't already NEWLINE or INDENT
        if self.tokens and self.tokens[-1].type not in (TokenType.NEWLINE, TokenType.INDENT, TokenType.DEDENT):
            self.tokens.append(Token(TokenType.NEWLINE, "\\n", self.line, self.col))
        self._advance()  # consume \n
        self.at_line_start = True

    # ── Token readers ────────────────────────────────────────────────────

    def _read_number(self):
        """Read an integer or float literal, including scientific notation."""
        start = self.pos
        start_col = self.col
        has_dot = False
        has_exp = False

        while self.pos < len(self.source):
            ch = self.source[self.pos]
            if ch == '.' and not has_dot and not has_exp:
                # Check it's not a method call like 5.to(...)
                nxt = self._peek_at(self.pos + 1)
                if nxt.isdigit():
                    has_dot = True
                    self._advance()
                else:
                    break
            elif ch in ('e', 'E') and not has_exp:
                has_exp = True
                self._advance()
                if self.pos < len(self.source) and self.source[self.pos] in ('+', '-'):
                    self._advance()
            elif ch.isdigit():
                self._advance()
            elif ch == '_':  # allow 1_000_000
                self._advance()
            else:
                break

        value = self.source[start:self.pos].replace('_', '')
        self.tokens.append(Token(TokenType.NUMBER, value, self.line, start_col))
        self.at_line_start = False

    def _read_string(self):
        """Read a single or double quoted string."""
        quote = self.source[self.pos]
        start_col = self.col
        self._advance()  # consume opening quote
        chars = []

        while self.pos < len(self.source):
            ch = self.source[self.pos]
            if ch == '\\':
                self._advance()
                if self.pos >= len(self.source):
                    raise LexerError("Unterminated string escape", self.line, self.col)
                esc = self.source[self.pos]
                escape_map = {'n': '\n', 't': '\t', '\\': '\\', "'": "'", '"': '"'}
                chars.append(escape_map.get(esc, '\\' + esc))
                self._advance()
            elif ch == quote:
                self._advance()  # consume closing quote
                self.tokens.append(Token(TokenType.STRING, ''.join(chars), self.line, start_col))
                self.at_line_start = False
                return
            elif ch == '\n':
                raise LexerError("Unterminated string literal", self.line, self.col)
            else:
                chars.append(ch)
                self._advance()

        raise LexerError("Unterminated string literal", self.line, self.col)

    def _read_identifier_or_unit(self):
        """Read an identifier, keyword, unit symbol, or constant name."""
        start = self.pos
        start_col = self.col

        # Handle special unicode chars that are single-char units
        ch = self.source[self.pos]
        if ch in ('Å', 'Ω'):
            self._advance()
            self.tokens.append(Token(TokenType.UNIT, ch, self.line, start_col))
            self.at_line_start = False
            return

        # Handle μ — could be μm, μA, etc.
        if ch == 'μ':
            self._advance()
            while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] == '_'):
                self._advance()
            word = self.source[start:self.pos]
            if word in self.unit_symbols:
                self.tokens.append(Token(TokenType.UNIT, word, self.line, start_col))
            else:
                self.tokens.append(Token(TokenType.IDENTIFIER, word, self.line, start_col))
            self.at_line_start = False
            return

        # Standard alphanumeric identifier
        while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] == '_'):
            self._advance()

        word = self.source[start:self.pos]

        # Check keywords first
        if word in KEYWORDS:
            self.tokens.append(Token(KEYWORDS[word], word, self.line, start_col))
        # Then unit symbols
        elif word in self.unit_symbols:
            self.tokens.append(Token(TokenType.UNIT, word, self.line, start_col))
        # Then constants
        elif word in self.constant_names:
            self.tokens.append(Token(TokenType.CONSTANT, word, self.line, start_col))
        else:
            self.tokens.append(Token(TokenType.IDENTIFIER, word, self.line, start_col))
        self.at_line_start = False

    def _read_operator(self):
        """Read operator and delimiter tokens."""
        ch = self.source[self.pos]
        start_col = self.col
        nxt = self._peek_next()

        # Two-character operators
        two_char = ch + nxt if nxt else ch
        two_char_ops = {
            '**': TokenType.DOUBLESTAR,
            '==': TokenType.EQ,
            '!=': TokenType.NEQ,
            '<=': TokenType.LTE,
            '>=': TokenType.GTE,
            '+=': TokenType.PLUSEQ,
            '-=': TokenType.MINUSEQ,
            '*=': TokenType.STAREQ,
            '/=': TokenType.SLASHEQ,
            '->': TokenType.ARROW,
        }
        if two_char in two_char_ops:
            self._advance()
            self._advance()
            self.tokens.append(Token(two_char_ops[two_char], two_char, self.line, start_col))
            self.at_line_start = False
            return

        # Single-character operators
        one_char_ops = {
            '+': TokenType.PLUS, '-': TokenType.MINUS,
            '*': TokenType.STAR, '/': TokenType.SLASH,
            '%': TokenType.PERCENT, '.': TokenType.DOT,
            '<': TokenType.LT, '>': TokenType.GT,
            '=': TokenType.ASSIGN,
            ',': TokenType.COMMA, ':': TokenType.COLON,
            ';': TokenType.SEMICOLON, '|': TokenType.PIPE,
        }
        if ch in one_char_ops:
            self._advance()
            self.tokens.append(Token(one_char_ops[ch], ch, self.line, start_col))
            self.at_line_start = False
            return

        # Bracket-type delimiters (track paren depth)
        if ch == '(':
            self.paren_depth += 1
            self._advance()
            self.tokens.append(Token(TokenType.LPAREN, ch, self.line, start_col))
            self.at_line_start = False
            return
        if ch == ')':
            self.paren_depth = max(0, self.paren_depth - 1)
            self._advance()
            self.tokens.append(Token(TokenType.RPAREN, ch, self.line, start_col))
            self.at_line_start = False
            return
        if ch == '[':
            self.paren_depth += 1
            self._advance()
            self.tokens.append(Token(TokenType.LBRACKET, ch, self.line, start_col))
            self.at_line_start = False
            return
        if ch == ']':
            self.paren_depth = max(0, self.paren_depth - 1)
            self._advance()
            self.tokens.append(Token(TokenType.RBRACKET, ch, self.line, start_col))
            self.at_line_start = False
            return
        if ch == '{':
            self.paren_depth += 1
            self._advance()
            self.tokens.append(Token(TokenType.LBRACE, ch, self.line, start_col))
            self.at_line_start = False
            return
        if ch == '}':
            self.paren_depth = max(0, self.paren_depth - 1)
            self._advance()
            self.tokens.append(Token(TokenType.RBRACE, ch, self.line, start_col))
            self.at_line_start = False
            return

        raise LexerError(f"Unexpected character: {ch!r}", self.line, self.col)

    # ── Helpers ──────────────────────────────────────────────────────────

    def _advance(self):
        if self.pos < len(self.source):
            if self.source[self.pos] == '\n':
                self.line += 1
                self.col = 1
            else:
                self.col += 1
            self.pos += 1

    def _peek_next(self) -> str:
        return self.source[self.pos + 1] if self.pos + 1 < len(self.source) else ''

    def _peek_at(self, idx: int) -> str:
        return self.source[idx] if idx < len(self.source) else ''

    def _skip_whitespace_inline(self):
        """Skip spaces and tabs (not newlines) within a line."""
        while self.pos < len(self.source) and self.source[self.pos] in (' ', '\t') and not self.at_line_start:
            self._advance()

    def _skip_comment(self):
        """Skip from # to end of line."""
        while self.pos < len(self.source) and self.source[self.pos] != '\n':
            self._advance()


# ─── Convenience ─────────────────────────────────────────────────────────────

def lex(source: str, unit_symbols: set[str] = None, constant_names: set[str] = None) -> list[Token]:
    """Tokenize source code and return a list of tokens."""
    return Lexer(source, unit_symbols, constant_names).tokenize()
