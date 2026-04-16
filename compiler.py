"""
Kerma Compiler
==============
Walks the AST and emits bytecode instructions into a CodeObject.
"""

from __future__ import annotations
from typing import Any

from ast_nodes import *
from bytecode import Op, CodeObject


class CompileError(Exception):
    def __init__(self, message: str, node: Node = None):
        self.node = node
        loc = f"Line {node.line}: " if node else ""
        super().__init__(f"{loc}{message}")


class Compiler:
    """
    Compiles a Kerma AST into a CodeObject.

    Usage:
        compiler = Compiler()
        code = compiler.compile(program)
    """

    def __init__(self):
        self.code: CodeObject = None

    def compile(self, program: Program) -> CodeObject:
        self.code = CodeObject(name="<module>")
        for stmt in program.body:
            self._compile_stmt(stmt)
        # Implicit return of last expression
        self.code.add(Op.RETURN)
        return self.code

    # ── Statements ───────────────────────────────────────────────────────

    def _compile_stmt(self, node: Node):
        if isinstance(node, Assignment):
            self._compile_expr(node.value)
            self.code.add(Op.STORE_NAME, node.target)

        elif isinstance(node, AugAssignment):
            self.code.add(Op.LOAD_NAME, node.target)
            self._compile_expr(node.value)
            op_map = {'+': Op.ADD, '-': Op.SUB, '*': Op.MUL, '/': Op.DIV}
            self.code.add(op_map[node.op])
            self.code.add(Op.STORE_NAME, node.target)

        elif isinstance(node, ExprStatement):
            self._compile_expr(node.expr)
            # Keep last value on stack for implicit return

        elif isinstance(node, PrintStatement):
            self._compile_expr(node.value)
            self.code.add(Op.PRINT)

        elif isinstance(node, IfStatement):
            self._compile_if(node)

        elif isinstance(node, WhileStatement):
            self._compile_while(node)

        elif isinstance(node, ForStatement):
            self._compile_for(node)

        elif isinstance(node, FuncDef):
            self._compile_funcdef(node)

        elif isinstance(node, Return):
            if node.value:
                self._compile_expr(node.value)
            else:
                idx = self.code.add_const(None)
                self.code.add(Op.LOAD_CONST, idx)
            self.code.add(Op.RETURN)

        else:
            raise CompileError(f"Unknown statement: {type(node).__name__}", node)

    def _compile_if(self, node: IfStatement):
        # Compile condition
        self._compile_expr(node.condition)
        jump_false = self.code.add(Op.JUMP_IF_FALSE, None)  # patch later

        # True body
        for stmt in node.body:
            self._compile_stmt(stmt)
        jump_end = self.code.add(Op.JUMP, None)  # skip else/elif

        # Elif clauses
        elif_end_jumps = []
        self.code.patch_jump(jump_false, self.code.current_offset())
        for cond, body in node.elif_clauses:
            self._compile_expr(cond)
            elif_jump_false = self.code.add(Op.JUMP_IF_FALSE, None)
            for stmt in body:
                self._compile_stmt(stmt)
            elif_end_jumps.append(self.code.add(Op.JUMP, None))
            self.code.patch_jump(elif_jump_false, self.code.current_offset())

        # Else body
        if node.else_body:
            for stmt in node.else_body:
                self._compile_stmt(stmt)

        # Patch all end jumps
        end = self.code.current_offset()
        self.code.patch_jump(jump_end, end)
        for j in elif_end_jumps:
            self.code.patch_jump(j, end)

    def _compile_while(self, node: WhileStatement):
        loop_start = self.code.current_offset()
        self._compile_expr(node.condition)
        jump_exit = self.code.add(Op.JUMP_IF_FALSE, None)

        for stmt in node.body:
            self._compile_stmt(stmt)
        self.code.add(Op.JUMP, loop_start)

        self.code.patch_jump(jump_exit, self.code.current_offset())

    def _compile_for(self, node: ForStatement):
        # Compile the iterable and store an iterator
        # Strategy: compile iterable, call iter(), then loop with next()
        # Simpler approach: we'll use the same CALL mechanism
        # For now, compile the iterable, then use a special FOR_ITER pattern

        # Push iterable onto stack
        self._compile_expr(node.iterable)

        # Convert to list/iterator — we'll call __iter__ at the VM level
        iter_var = f"__iter_{id(node)}"
        idx_var = f"__idx_{id(node)}"
        len_var = f"__len_{id(node)}"

        self.code.add(Op.STORE_NAME, iter_var)

        # __idx = 0
        self.code.add(Op.LOAD_CONST, self.code.add_const(0))
        self.code.add(Op.STORE_NAME, idx_var)

        # __len = len(iterable)
        self.code.add(Op.LOAD_NAME, 'len')
        self.code.add(Op.LOAD_NAME, iter_var)
        self.code.add(Op.CALL, 1)
        self.code.add(Op.STORE_NAME, len_var)

        # Loop start
        loop_start = self.code.current_offset()

        # if __idx >= __len: break
        self.code.add(Op.LOAD_NAME, idx_var)
        self.code.add(Op.LOAD_NAME, len_var)
        self.code.add(Op.CMP_GE)
        jump_exit = self.code.add(Op.JUMP_IF_TRUE, None)

        # var = iterable[__idx]
        self.code.add(Op.LOAD_NAME, iter_var)
        self.code.add(Op.LOAD_NAME, idx_var)
        self.code.add(Op.INDEX)
        self.code.add(Op.STORE_NAME, node.var)

        # Body
        for stmt in node.body:
            self._compile_stmt(stmt)

        # __idx += 1
        self.code.add(Op.LOAD_NAME, idx_var)
        self.code.add(Op.LOAD_CONST, self.code.add_const(1))
        self.code.add(Op.ADD)
        self.code.add(Op.STORE_NAME, idx_var)

        self.code.add(Op.JUMP, loop_start)
        self.code.patch_jump(jump_exit, self.code.current_offset())

    def _compile_funcdef(self, node: FuncDef):
        # Compile function body into a separate CodeObject
        outer_code = self.code
        func_code = CodeObject(name=node.name, params=node.params)
        self.code = func_code

        for stmt in node.body:
            self._compile_stmt(stmt)

        # Implicit return None if no explicit return
        none_idx = self.code.add_const(None)
        self.code.add(Op.LOAD_CONST, none_idx)
        self.code.add(Op.RETURN)

        self.code = outer_code

        # Store the CodeObject as a constant and create function
        code_idx = self.code.add_const(func_code)
        self.code.add(Op.MAKE_FUNCTION, code_idx)
        self.code.add(Op.STORE_NAME, node.name)

    # ── Expressions ──────────────────────────────────────────────────────

    def _compile_expr(self, node: Node):
        if isinstance(node, NumberLiteral):
            idx = self.code.add_const(node.value)
            self.code.add(Op.LOAD_CONST, idx)

        elif isinstance(node, StringLiteral):
            idx = self.code.add_const(node.value)
            self.code.add(Op.LOAD_CONST, idx)

        elif isinstance(node, BoolLiteral):
            idx = self.code.add_const(node.value)
            self.code.add(Op.LOAD_CONST, idx)

        elif isinstance(node, NoneLiteral):
            idx = self.code.add_const(None)
            self.code.add(Op.LOAD_CONST, idx)

        elif isinstance(node, Identifier):
            self.code.add(Op.LOAD_NAME, node.name)

        elif isinstance(node, ConstantRef):
            self.code.add(Op.LOAD_NAME, node.name)

        elif isinstance(node, UnitLiteral):
            self.code.add(Op.RESOLVE_UNIT, node.symbol)

        elif isinstance(node, UnitAttach):
            self._compile_expr(node.value)
            self.code.add(Op.ATTACH_UNIT, self._compile_unit_info(node.unit))

        elif isinstance(node, BinOp):
            self._compile_expr(node.left)
            self._compile_expr(node.right)
            op_map = {
                '+': Op.ADD, '-': Op.SUB, '*': Op.MUL,
                '/': Op.DIV, '%': Op.MOD, '**': Op.POW,
            }
            if node.op in op_map:
                self.code.add(op_map[node.op])
            else:
                raise CompileError(f"Unknown operator: {node.op}", node)

        elif isinstance(node, UnaryOp):
            self._compile_expr(node.operand)
            if node.op == '-':
                self.code.add(Op.NEG)
            elif node.op == 'not':
                self.code.add(Op.BOOL_NOT)
            else:
                raise CompileError(f"Unknown unary op: {node.op}", node)

        elif isinstance(node, Compare):
            # Compile chained comparisons: a < b < c → (a < b) and (b < c)
            self._compile_expr(node.operands[0])
            cmp_map = {
                '==': Op.CMP_EQ, '!=': Op.CMP_NE,
                '<': Op.CMP_LT, '>': Op.CMP_GT,
                '<=': Op.CMP_LE, '>=': Op.CMP_GE,
            }
            if len(node.ops) == 1:
                self._compile_expr(node.operands[1])
                self.code.add(cmp_map[node.ops[0]])
            else:
                # Chained: a < b < c → compile as (a<b) && (b<c)
                for i, op in enumerate(node.ops):
                    self._compile_expr(node.operands[i + 1])
                    if i < len(node.ops) - 1:
                        self.code.add(Op.DUP)  # keep b for next comparison
                    self.code.add(cmp_map[op])
                    if i > 0:
                        self.code.add(Op.BOOL_AND)

        elif isinstance(node, BoolOp):
            self._compile_expr(node.left)
            self._compile_expr(node.right)
            if node.op == 'and':
                self.code.add(Op.BOOL_AND)
            elif node.op == 'or':
                self.code.add(Op.BOOL_OR)

        elif isinstance(node, Call):
            self._compile_expr(node.func)
            for arg in node.args:
                self._compile_expr(arg)
            self.code.add(Op.CALL, len(node.args))

        elif isinstance(node, Index):
            self._compile_expr(node.obj)
            self._compile_expr(node.index)
            self.code.add(Op.INDEX)

        elif isinstance(node, Attribute):
            self._compile_expr(node.obj)
            self.code.add(Op.LOAD_ATTR, node.attr)

        elif isinstance(node, ListLiteral):
            for elem in node.elements:
                self._compile_expr(elem)
            self.code.add(Op.BUILD_LIST, len(node.elements))

        elif isinstance(node, PipeConvert):
            self._compile_expr(node.value)
            self.code.add(Op.PIPE_CONVERT, node.target_unit)

        else:
            raise CompileError(f"Unknown expression: {type(node).__name__}", node)

    def _compile_unit_info(self, unit_node: Node) -> Any:
        """Compile unit expression to a serializable descriptor."""
        if isinstance(unit_node, UnitLiteral):
            return ('unit', unit_node.symbol)
        if isinstance(unit_node, BinOp):
            left = self._compile_unit_info(unit_node.left)
            right = self._compile_unit_info(unit_node.right)
            return ('compound', unit_node.op, left, right)
        raise CompileError(f"Cannot compile unit from {type(unit_node).__name__}")


# ─── Convenience ─────────────────────────────────────────────────────────────

def compile_program(program: Program) -> CodeObject:
    return Compiler().compile(program)
