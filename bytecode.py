"""
Kerma Bytecode
==============
Opcodes for the Kerma stack-based VM.

Code objects hold a flat list of (opcode, arg) instructions plus a constant pool.
The VM executes by stepping through instructions, manipulating a value stack.
"""

from __future__ import annotations
from enum import IntEnum, auto
from dataclasses import dataclass, field
from typing import Any


class Op(IntEnum):
    """Bytecode opcodes."""
    # Stack manipulation
    LOAD_CONST      = auto()  # arg: index into constants pool
    LOAD_NAME       = auto()  # arg: variable name (string)
    STORE_NAME      = auto()  # arg: variable name
    LOAD_FAST       = auto()  # arg: local slot index (for functions)
    STORE_FAST      = auto()  # arg: local slot index

    # Arithmetic
    ADD             = auto()
    SUB             = auto()
    MUL             = auto()
    DIV             = auto()
    MOD             = auto()
    POW             = auto()
    NEG             = auto()  # unary minus

    # Comparison
    CMP_EQ          = auto()
    CMP_NE          = auto()
    CMP_LT          = auto()
    CMP_GT          = auto()
    CMP_LE          = auto()
    CMP_GE          = auto()

    # Boolean
    BOOL_AND        = auto()
    BOOL_OR         = auto()
    BOOL_NOT        = auto()

    # Control flow
    JUMP            = auto()  # arg: absolute target
    JUMP_IF_FALSE   = auto()  # arg: absolute target (pops condition)
    JUMP_IF_TRUE    = auto()  # arg: absolute target

    # Functions
    CALL            = auto()  # arg: number of arguments
    RETURN          = auto()
    MAKE_FUNCTION   = auto()  # arg: index into constants (CodeObject)

    # Collections
    BUILD_LIST      = auto()  # arg: number of elements
    INDEX           = auto()  # TOS1[TOS]
    STORE_INDEX     = auto()  # TOS2[TOS1] = TOS

    # Attribute
    LOAD_ATTR       = auto()  # arg: attribute name
    CALL_METHOD     = auto()  # arg: (attr_name, nargs)

    # Units
    ATTACH_UNIT     = auto()  # arg: unit resolution info
    PIPE_CONVERT    = auto()  # arg: target unit symbol
    RESOLVE_UNIT    = auto()  # arg: unit symbol string

    # Special
    PRINT           = auto()
    POP             = auto()  # discard TOS
    DUP             = auto()  # duplicate TOS
    NOP             = auto()


@dataclass
class CodeObject:
    """
    A compiled chunk of Kerma bytecode.

    Attributes:
        name: function name or '<module>' for top-level
        instructions: list of (Op, arg) tuples
        constants: pool of literal values
        names: variable names referenced
        params: parameter names (for functions)
        local_count: number of local slots
    """
    name: str = "<module>"
    instructions: list[tuple[Op, Any]] = field(default_factory=list)
    constants: list[Any] = field(default_factory=list)
    names: list[str] = field(default_factory=list)
    params: list[str] = field(default_factory=list)
    local_count: int = 0

    def add(self, op: Op, arg: Any = None) -> int:
        """Append an instruction, return its index."""
        idx = len(self.instructions)
        self.instructions.append((op, arg))
        return idx

    def add_const(self, value: Any) -> int:
        """Add a constant to the pool, return its index. Reuses existing entries."""
        # Don't deduplicate CodeObjects or complex types
        if isinstance(value, (int, float, str, bool, type(None))):
            for i, c in enumerate(self.constants):
                if type(c) == type(value) and c == value:
                    return i
        idx = len(self.constants)
        self.constants.append(value)
        return idx

    def patch_jump(self, instr_idx: int, target: int):
        """Patch a jump instruction's target after emitting the destination."""
        op, _ = self.instructions[instr_idx]
        self.instructions[instr_idx] = (op, target)

    def current_offset(self) -> int:
        return len(self.instructions)

    def disassemble(self) -> str:
        """Human-readable disassembly."""
        lines = [f"=== {self.name} ==="]
        if self.params:
            lines.append(f"  params: {', '.join(self.params)}")
        lines.append(f"  constants: {self.constants}")
        lines.append("")
        for i, (op, arg) in enumerate(self.instructions):
            if arg is not None:
                if isinstance(arg, tuple):
                    lines.append(f"  {i:4d}  {op.name:<20s} {arg}")
                else:
                    lines.append(f"  {i:4d}  {op.name:<20s} {arg!r}")
            else:
                lines.append(f"  {i:4d}  {op.name}")
        return "\n".join(lines)
