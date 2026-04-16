"""
Kerma Parser
============
Pratt (top-down operator precedence) parser that transforms a token stream into an AST.

Precedence table (lowest to highest):
    1  or
    2  and
    3  not
    4  == != < > <= >=
    5  |  (pipe / unit conversion)
    6  + -
    7  * / %
    8  unary - +
    9  **
   10  call, index, attribute
   11  atoms (number, identifier, unit, paren group, list)
"""

from __future__ import annotations
from lexer import Token, TokenType, LexerError
from ast_nodes import *

# ─── Precedence levels ───────────────────────────────────────────────────────

PREC_NONE    = 0
PREC_OR      = 1
PREC_AND     = 2
PREC_NOT     = 3
PREC_COMPARE = 4
PREC_PIPE    = 5
PREC_SUM     = 6
PREC_PRODUCT = 7
PREC_UNARY   = 8
PREC_POWER   = 9
PREC_CALL    = 10


class ParseError(Exception):
    def __init__(self, message: str, token: Token = None):
        self.token = token
        loc = f"Line {token.line}, col {token.col}: " if token else ""
        super().__init__(f"{loc}{message}")


class Parser:
    """
    Pratt parser for the Kerma language.

    Usage:
        parser = Parser(tokens)
        program = parser.parse()
    """

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    # ── Token navigation ─────────────────────────────────────────────────

    def _current(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]  # EOF

    def _peek(self) -> Token:
        """Look ahead past NEWLINEs to find the next meaningful token."""
        i = self.pos + 1
        while i < len(self.tokens) and self.tokens[i].type == TokenType.NEWLINE:
            i += 1
        return self.tokens[i] if i < len(self.tokens) else self.tokens[-1]

    def _advance(self) -> Token:
        tok = self._current()
        self.pos += 1
        return tok

    def _expect(self, tt: TokenType, msg: str = None) -> Token:
        tok = self._current()
        if tok.type != tt:
            raise ParseError(msg or f"Expected {tt.name}, got {tok.type.name} ({tok.value!r})", tok)
        return self._advance()

    def _expect_any(self, types: tuple, msg: str = None) -> Token:
        tok = self._current()
        if tok.type not in types:
            raise ParseError(msg or f"Expected one of {[t.name for t in types]}, got {tok.type.name}", tok)
        return self._advance()

    def _match(self, *types: TokenType) -> Token | None:
        if self._current().type in types:
            return self._advance()
        return None

    def _skip_newlines(self):
        while self._current().type == TokenType.NEWLINE:
            self._advance()

    def _at_end(self) -> bool:
        return self._current().type == TokenType.EOF

    # ── Top-level parse ──────────────────────────────────────────────────

    def parse(self) -> Program:
        self._skip_newlines()
        stmts = []
        while not self._at_end():
            stmts.append(self._statement())
            self._skip_newlines()
        return Program(body=stmts, line=1, col=1)

    # ── Statements ───────────────────────────────────────────────────────

    def _statement(self) -> Node:
        cur = self._current()

        if cur.type == TokenType.DEF:
            return self._func_def()
        if cur.type == TokenType.IF:
            return self._if_statement()
        if cur.type == TokenType.WHILE:
            return self._while_statement()
        if cur.type == TokenType.FOR:
            return self._for_statement()
        if cur.type == TokenType.RETURN:
            return self._return_statement()
        if cur.type == TokenType.PRINT:
            return self._print_statement()

        # Assignment or expression statement
        # Look ahead: if IDENTIFIER/CONSTANT/UNIT followed by = (not ==), it's assignment
        if cur.type in (TokenType.IDENTIFIER, TokenType.CONSTANT, TokenType.UNIT):
            nxt = self._peek_raw()
            if nxt and nxt.type == TokenType.ASSIGN:
                return self._assignment()
            if nxt and nxt.type in (TokenType.PLUSEQ, TokenType.MINUSEQ,
                                     TokenType.STAREQ, TokenType.SLASHEQ):
                return self._aug_assignment()

        # Expression statement
        expr = self._expression()
        self._match(TokenType.NEWLINE)
        return ExprStatement(expr=expr, line=cur.line, col=cur.col)

    def _peek_raw(self) -> Token | None:
        """Peek one token ahead without skipping newlines."""
        i = self.pos + 1
        return self.tokens[i] if i < len(self.tokens) else None

    def _assignment(self) -> Assignment:
        name_tok = self._advance()  # IDENTIFIER or CONSTANT
        self._expect(TokenType.ASSIGN)
        value = self._expression()
        self._match(TokenType.NEWLINE)
        return Assignment(target=name_tok.value, value=value, line=name_tok.line, col=name_tok.col)

    def _aug_assignment(self) -> AugAssignment:
        name_tok = self._advance()  # IDENTIFIER or CONSTANT
        op_tok = self._advance()
        op_map = {
            TokenType.PLUSEQ: '+', TokenType.MINUSEQ: '-',
            TokenType.STAREQ: '*', TokenType.SLASHEQ: '/',
        }
        value = self._expression()
        self._match(TokenType.NEWLINE)
        return AugAssignment(target=name_tok.value, op=op_map[op_tok.type],
                             value=value, line=name_tok.line, col=name_tok.col)

    def _print_statement(self) -> PrintStatement:
        tok = self._advance()  # consume 'print'
        value = self._expression()
        self._match(TokenType.NEWLINE)
        return PrintStatement(value=value, line=tok.line, col=tok.col)

    def _return_statement(self) -> Return:
        tok = self._advance()  # consume 'return'
        value = None
        if self._current().type not in (TokenType.NEWLINE, TokenType.EOF, TokenType.DEDENT):
            value = self._expression()
        self._match(TokenType.NEWLINE)
        return Return(value=value, line=tok.line, col=tok.col)

    def _func_def(self) -> FuncDef:
        tok = self._advance()  # consume 'def'
        name = self._expect(TokenType.IDENTIFIER).value
        self._expect(TokenType.LPAREN)
        params = []
        param_types = (TokenType.IDENTIFIER, TokenType.UNIT, TokenType.CONSTANT)
        if self._current().type != TokenType.RPAREN:
            params.append(self._expect_any(param_types, "Expected parameter name").value)
            while self._match(TokenType.COMMA):
                params.append(self._expect_any(param_types, "Expected parameter name").value)
        self._expect(TokenType.RPAREN)
        self._expect(TokenType.COLON)
        body = self._block()
        return FuncDef(name=name, params=params, body=body, line=tok.line, col=tok.col)

    def _if_statement(self) -> IfStatement:
        tok = self._advance()  # consume 'if'
        condition = self._expression()
        self._expect(TokenType.COLON)
        body = self._block()
        elif_clauses = []
        else_body = []
        self._skip_newlines()
        while self._current().type == TokenType.ELIF:
            self._advance()
            econd = self._expression()
            self._expect(TokenType.COLON)
            ebody = self._block()
            elif_clauses.append((econd, ebody))
            self._skip_newlines()
        if self._current().type == TokenType.ELSE:
            self._advance()
            self._expect(TokenType.COLON)
            else_body = self._block()
        return IfStatement(condition=condition, body=body,
                           elif_clauses=elif_clauses, else_body=else_body,
                           line=tok.line, col=tok.col)

    def _while_statement(self) -> WhileStatement:
        tok = self._advance()  # consume 'while'
        condition = self._expression()
        self._expect(TokenType.COLON)
        body = self._block()
        return WhileStatement(condition=condition, body=body, line=tok.line, col=tok.col)

    def _for_statement(self) -> ForStatement:
        tok = self._advance()  # consume 'for'
        var = self._expect(TokenType.IDENTIFIER).value
        self._expect(TokenType.IN)
        iterable = self._expression()
        self._expect(TokenType.COLON)
        body = self._block()
        return ForStatement(var=var, iterable=iterable, body=body, line=tok.line, col=tok.col)

    def _block(self) -> list[Node]:
        """Parse an indented block of statements."""
        self._match(TokenType.NEWLINE)
        self._skip_newlines()
        self._expect(TokenType.INDENT, "Expected indented block")
        stmts = []
        self._skip_newlines()
        while self._current().type not in (TokenType.DEDENT, TokenType.EOF):
            stmts.append(self._statement())
            self._skip_newlines()
        self._match(TokenType.DEDENT)
        return stmts

    # ── Expression parsing (Pratt) ───────────────────────────────────────

    def _expression(self, min_prec: int = PREC_NONE) -> Node:
        left = self._prefix()
        # Try unit attachment only after atoms that can have units
        if self._can_attach_unit(left):
            left = self._try_unit_attach(left)
        while True:
            prec = self._infix_precedence(self._current())
            if prec <= min_prec:
                break
            left = self._infix(left)
        return left

    def _can_attach_unit(self, node: Node) -> bool:
        """Only attach units directly to number literals, lists, and grouped expressions."""
        return isinstance(node, (NumberLiteral, ListLiteral))

    def _prefix(self) -> Node:
        """Parse a prefix expression (atom, unary, grouped)."""
        tok = self._current()

        if tok.type == TokenType.NUMBER:
            return self._number()
        if tok.type == TokenType.STRING:
            self._advance()
            return StringLiteral(value=tok.value, line=tok.line, col=tok.col)
        if tok.type == TokenType.TRUE:
            self._advance()
            return BoolLiteral(value=True, line=tok.line, col=tok.col)
        if tok.type == TokenType.FALSE:
            self._advance()
            return BoolLiteral(value=False, line=tok.line, col=tok.col)
        if tok.type == TokenType.NONE:
            self._advance()
            return NoneLiteral(line=tok.line, col=tok.col)
        if tok.type == TokenType.IDENTIFIER:
            self._advance()
            node = Identifier(name=tok.value, line=tok.line, col=tok.col)
            return self._postfix(node)
        if tok.type == TokenType.CONSTANT:
            self._advance()
            node = ConstantRef(name=tok.value, line=tok.line, col=tok.col)
            return self._postfix(node)
        if tok.type == TokenType.LPAREN:
            return self._grouped()
        if tok.type == TokenType.LBRACKET:
            return self._list_literal()
        if tok.type == TokenType.MINUS:
            self._advance()
            operand = self._expression(PREC_UNARY)
            return UnaryOp(op='-', operand=operand, line=tok.line, col=tok.col)
        if tok.type == TokenType.PLUS:
            self._advance()
            return self._expression(PREC_UNARY)
        if tok.type == TokenType.NOT:
            self._advance()
            operand = self._expression(PREC_NOT)
            return UnaryOp(op='not', operand=operand, line=tok.line, col=tok.col)
        # Math keywords used as function calls: diff(f, x)
        if tok.type in (TokenType.DIFF, TokenType.INTEGRATE, TokenType.SIMPLIFY,
                        TokenType.SOLVE, TokenType.SUBS):
            self._advance()
            node = Identifier(name=tok.value, line=tok.line, col=tok.col)
            return self._postfix(node)
        # Bare unit token (e.g. eV inside .to(eV), or A[0] where A is a variable)
        if tok.type == TokenType.UNIT:
            self._advance()
            node = UnitLiteral(symbol=tok.value, line=tok.line, col=tok.col)
            return self._postfix(node)

        raise ParseError(f"Unexpected token: {tok.type.name} ({tok.value!r})", tok)

    def _number(self) -> Node:
        tok = self._advance()
        return NumberLiteral(value=float(tok.value), line=tok.line, col=tok.col)

    def _grouped(self) -> Node:
        self._advance()  # consume (
        expr = self._expression()
        self._expect(TokenType.RPAREN)
        node = self._postfix(expr)
        # Allow unit attachment: (2 + 3) MeV
        return self._try_unit_attach(node)

    def _list_literal(self) -> ListLiteral:
        tok = self._advance()  # consume [
        elements = []
        if self._current().type != TokenType.RBRACKET:
            elements.append(self._expression())
            while self._match(TokenType.COMMA):
                if self._current().type == TokenType.RBRACKET:
                    break  # trailing comma
                elements.append(self._expression())
        self._expect(TokenType.RBRACKET)
        node = ListLiteral(elements=elements, line=tok.line, col=tok.col)
        return node

    def _postfix(self, node: Node) -> Node:
        """Handle call, index, and attribute access after an atom."""
        while True:
            if self._current().type == TokenType.LPAREN:
                node = self._call(node)
            elif self._current().type == TokenType.LBRACKET:
                node = self._index(node)
            elif self._current().type == TokenType.DOT:
                node = self._attribute(node)
            else:
                break
        return node

    def _call(self, func: Node) -> Call:
        tok = self._advance()  # consume (
        args = []
        if self._current().type != TokenType.RPAREN:
            args.append(self._expression())
            while self._match(TokenType.COMMA):
                if self._current().type == TokenType.RPAREN:
                    break
                args.append(self._expression())
        self._expect(TokenType.RPAREN)
        node = Call(func=func, args=args, line=tok.line, col=tok.col)
        return self._postfix(node)

    def _index(self, obj: Node) -> Index:
        tok = self._advance()  # consume [
        index = self._expression()
        self._expect(TokenType.RBRACKET)
        node = Index(obj=obj, index=index, line=tok.line, col=tok.col)
        return self._postfix(node)

    def _attribute(self, obj: Node) -> Node:
        self._advance()  # consume .
        attr_tok = self._expect(TokenType.IDENTIFIER, "Expected attribute name after '.'")
        node = Attribute(obj=obj, attr=attr_tok.value, line=attr_tok.line, col=attr_tok.col)
        return self._postfix(node)

    # ── Infix parsing ────────────────────────────────────────────────────

    def _infix_precedence(self, tok: Token) -> int:
        return {
            TokenType.OR: PREC_OR,
            TokenType.AND: PREC_AND,
            TokenType.EQ: PREC_COMPARE, TokenType.NEQ: PREC_COMPARE,
            TokenType.LT: PREC_COMPARE, TokenType.GT: PREC_COMPARE,
            TokenType.LTE: PREC_COMPARE, TokenType.GTE: PREC_COMPARE,
            TokenType.PIPE: PREC_PIPE,
            TokenType.PLUS: PREC_SUM, TokenType.MINUS: PREC_SUM,
            TokenType.STAR: PREC_PRODUCT, TokenType.SLASH: PREC_PRODUCT,
            TokenType.PERCENT: PREC_PRODUCT,
            TokenType.DOUBLESTAR: PREC_POWER,
        }.get(tok.type, PREC_NONE)

    def _infix(self, left: Node) -> Node:
        tok = self._current()

        # Comparison operators
        if tok.type in (TokenType.EQ, TokenType.NEQ, TokenType.LT,
                        TokenType.GT, TokenType.LTE, TokenType.GTE):
            return self._comparison(left)

        # Boolean operators
        if tok.type == TokenType.AND:
            self._advance()
            right = self._expression(PREC_AND)
            return BoolOp(op='and', left=left, right=right, line=tok.line, col=tok.col)
        if tok.type == TokenType.OR:
            self._advance()
            right = self._expression(PREC_OR)
            return BoolOp(op='or', left=left, right=right, line=tok.line, col=tok.col)

        # Pipe (unit conversion)
        if tok.type == TokenType.PIPE:
            self._advance()
            unit_tok = self._expect(TokenType.UNIT, "Expected unit after '|'")
            return PipeConvert(value=left, target_unit=unit_tok.value,
                               line=tok.line, col=tok.col)

        # Power (right-associative)
        if tok.type == TokenType.DOUBLESTAR:
            self._advance()
            right = self._expression(PREC_POWER - 1)  # right-assoc
            return BinOp(op='**', left=left, right=right, line=tok.line, col=tok.col)

        # Standard binary operators
        op_str = {
            TokenType.PLUS: '+', TokenType.MINUS: '-',
            TokenType.STAR: '*', TokenType.SLASH: '/',
            TokenType.PERCENT: '%',
        }
        if tok.type in op_str:
            self._advance()
            prec = self._infix_precedence(tok)
            right = self._expression(prec)  # left-assoc
            return BinOp(op=op_str[tok.type], left=left, right=right,
                         line=tok.line, col=tok.col)

        raise ParseError(f"Unexpected infix token: {tok.type.name}", tok)

    def _comparison(self, left: Node) -> Compare:
        """Parse comparison, supporting chaining: a < b < c."""
        ops = []
        operands = [left]
        op_map = {
            TokenType.EQ: '==', TokenType.NEQ: '!=',
            TokenType.LT: '<', TokenType.GT: '>',
            TokenType.LTE: '<=', TokenType.GTE: '>=',
        }
        while self._current().type in op_map:
            tok = self._advance()
            ops.append(op_map[tok.type])
            operands.append(self._expression(PREC_COMPARE))
        return Compare(ops=ops, operands=operands, line=left.line, col=left.col)

    # ── Unit attachment ──────────────────────────────────────────────────

    def _try_unit_attach(self, node: Node) -> Node:
        """If the current token is a UNIT, attach it to the preceding expression."""
        if self._current().type == TokenType.UNIT:
            unit_tok = self._advance()
            unit_node = UnitLiteral(symbol=unit_tok.value, line=unit_tok.line, col=unit_tok.col)
            # Handle compound units: MeV/c², m/s², kg·m/s²
            while self._current().type in (TokenType.SLASH, TokenType.STAR):
                op_tok = self._advance()
                if self._current().type == TokenType.UNIT:
                    right_tok = self._advance()
                    right_unit = UnitLiteral(symbol=right_tok.value, line=right_tok.line, col=right_tok.col)
                    # Check for exponent: m/s² → s**2
                    if self._current().type == TokenType.DOUBLESTAR:
                        self._advance()
                        exp = self._number()
                        right_unit = BinOp(op='**', left=right_unit, right=exp,
                                           line=right_tok.line, col=right_tok.col)
                    unit_node = BinOp(op=op_tok.value, left=unit_node, right=right_unit,
                                      line=op_tok.line, col=op_tok.col)
                else:
                    # Not a unit after /, put the / back
                    self.pos -= 1
                    break
            return UnitAttach(value=node, unit=unit_node, line=node.line, col=node.col)
        return node


# ─── Convenience ─────────────────────────────────────────────────────────────

def parse(tokens: list[Token]) -> Program:
    return Parser(tokens).parse()
