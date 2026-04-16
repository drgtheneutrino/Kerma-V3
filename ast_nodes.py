"""
Kerma AST Nodes
===============
Every node in the abstract syntax tree is a dataclass with a line/col for error reporting.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


# ─── Base ────────────────────────────────────────────────────────────────────

@dataclass
class Node:
    line: int = 0
    col: int = 0


# ─── Expressions ─────────────────────────────────────────────────────────────

@dataclass
class NumberLiteral(Node):
    value: float = 0.0

@dataclass
class StringLiteral(Node):
    value: str = ""

@dataclass
class BoolLiteral(Node):
    value: bool = False

@dataclass
class NoneLiteral(Node):
    pass

@dataclass
class Identifier(Node):
    name: str = ""

@dataclass
class ConstantRef(Node):
    """Reference to a built-in physical constant (c, h, m_e, ...)."""
    name: str = ""

@dataclass
class UnitLiteral(Node):
    """A unit symbol appearing after a number: 5 MeV → UnitAttach(NumberLiteral(5), UnitLiteral('MeV'))."""
    symbol: str = ""

@dataclass
class UnitAttach(Node):
    """A value with a unit attached: 5 MeV, [1,2,3] m/s."""
    value: Node = None
    unit: Node = None  # UnitLiteral or BinOp of unit expressions

@dataclass
class BinOp(Node):
    op: str = ""
    left: Node = None
    right: Node = None

@dataclass
class UnaryOp(Node):
    op: str = ""      # '-', 'not'
    operand: Node = None

@dataclass
class Compare(Node):
    """Comparison: a < b, a == b, etc. Supports chaining: a < b < c."""
    ops: list[str] = field(default_factory=list)
    operands: list[Node] = field(default_factory=list)

@dataclass
class BoolOp(Node):
    """Logical: a and b, a or b."""
    op: str = ""       # 'and', 'or'
    left: Node = None
    right: Node = None

@dataclass
class Call(Node):
    func: Node = None
    args: list[Node] = field(default_factory=list)

@dataclass
class Index(Node):
    """Indexing: a[0], A[1][2]."""
    obj: Node = None
    index: Node = None

@dataclass
class Attribute(Node):
    """Attribute access: x.to(MeV), v.norm()."""
    obj: Node = None
    attr: str = ""

@dataclass
class ListLiteral(Node):
    elements: list[Node] = field(default_factory=list)

@dataclass
class PipeConvert(Node):
    """Unit conversion via pipe: E | MeV."""
    value: Node = None
    target_unit: str = ""


# ─── Statements ──────────────────────────────────────────────────────────────

@dataclass
class Assignment(Node):
    target: str = ""
    value: Node = None

@dataclass
class AugAssignment(Node):
    """Augmented assignment: x += 1, x *= 2."""
    target: str = ""
    op: str = ""       # '+', '-', '*', '/'
    value: Node = None

@dataclass
class ExprStatement(Node):
    """An expression used as a statement (e.g. function call, print)."""
    expr: Node = None

@dataclass
class PrintStatement(Node):
    value: Node = None

@dataclass
class IfStatement(Node):
    condition: Node = None
    body: list[Node] = field(default_factory=list)
    elif_clauses: list[tuple[Node, list[Node]]] = field(default_factory=list)
    else_body: list[Node] = field(default_factory=list)

@dataclass
class WhileStatement(Node):
    condition: Node = None
    body: list[Node] = field(default_factory=list)

@dataclass
class ForStatement(Node):
    var: str = ""
    iterable: Node = None
    body: list[Node] = field(default_factory=list)

@dataclass
class FuncDef(Node):
    name: str = ""
    params: list[str] = field(default_factory=list)
    body: list[Node] = field(default_factory=list)

@dataclass
class Return(Node):
    value: Optional[Node] = None

@dataclass
class Block(Node):
    """A sequence of statements (program or block body)."""
    statements: list[Node] = field(default_factory=list)


# ─── Program (top-level) ────────────────────────────────────────────────────

@dataclass
class Program(Node):
    body: list[Node] = field(default_factory=list)
