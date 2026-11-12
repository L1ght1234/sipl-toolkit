from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class SourcePos:
    line: int
    column: int
    offset: int = 0

    def to_dict(self) -> dict[str, int]:
        return {"line": self.line, "column": self.column, "offset": self.offset}


@dataclass(frozen=True, slots=True)
class SourceSpan:
    start: SourcePos
    end: SourcePos

    def to_dict(self) -> dict[str, Any]:
        return {"start": self.start.to_dict(), "end": self.end.to_dict()}

    def __str__(self) -> str:
        return f"{self.start.line}:{self.start.column}-{self.end.line}:{self.end.column}"


@dataclass(frozen=True, slots=True)
class Diagnostic:
    message: str
    span: SourceSpan
    code: str = "SIPL-SYNTAX-ERR"
    hint: str | None = None
    source_line: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "span": self.span.to_dict(),
            "hint": self.hint,
            "source_line": self.source_line,
        }

    def format_pretty(self) -> str:
        loc = f"line {self.span.start.line}, column {self.span.start.column}"
        parts = [f"[{self.code}] Error ({loc}): {self.message}"]
        if self.source_line is not None:
            parts.append(f"  | {self.source_line}")
            pointer_pad = " " * max(0, self.span.start.column - 1)
            parts.append(f"  | {pointer_pad}^")
        if self.hint:
            parts.append(f"  Hint: {self.hint}")
        return "\n".join(parts)


class SIPLSyntaxError(Exception):
    def __init__(self, diagnostic: Diagnostic) -> None:
        super().__init__(diagnostic.format_pretty())
        self.diagnostic = diagnostic


@dataclass(frozen=True)
class ASTNode:
    span: SourceSpan

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError


@dataclass(frozen=True)
class Aexp(ASTNode):
    pass


@dataclass(frozen=True)
class Num(Aexp):
    value: int

    def to_dict(self) -> dict[str, Any]:
        return {"type": "Num", "value": self.value, "span": self.span.to_dict()}


@dataclass(frozen=True)
class Var(Aexp):
    name: str

    def to_dict(self) -> dict[str, Any]:
        return {"type": "Var", "name": self.name, "span": self.span.to_dict()}


ArithOp = Literal["+", "-", "*", "div", "mod"]


@dataclass(frozen=True)
class BinOp(Aexp):
    op: ArithOp
    left: Aexp
    right: Aexp

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "BinOp",
            "op": self.op,
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class ParenAexp(Aexp):
    expr: Aexp

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "ParenAexp",
            "expr": self.expr.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class Bexp(ASTNode):
    pass


CompareOp = Literal["=", ">", ">=", "<", "<="]


@dataclass(frozen=True)
class CmpOp(Bexp):
    op: CompareOp
    left: Aexp
    right: Aexp

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "CmpOp",
            "op": self.op,
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class NotOp(Bexp):
    operand: Bexp

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "NotOp",
            "operand": self.operand.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class OrOp(Bexp):
    left: Bexp
    right: Bexp

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "OrOp",
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class ParenBexp(Bexp):
    cond: Bexp

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "ParenBexp",
            "cond": self.cond.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class Stm(ASTNode):
    pass


@dataclass(frozen=True)
class Assign(Stm):
    var: Var
    expr: Aexp

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "Assign",
            "var": self.var.to_dict(),
            "expr": self.expr.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class Seq(Stm):
    first: Stm
    second: Stm

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "Seq",
            "first": self.first.to_dict(),
            "second": self.second.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class If(Stm):
    cond: Bexp
    then_branch: Stm
    else_branch: Stm

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "If",
            "cond": self.cond.to_dict(),
            "then_branch": self.then_branch.to_dict(),
            "else_branch": self.else_branch.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class While(Stm):
    cond: Bexp
    body: Stm

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "While",
            "cond": self.cond.to_dict(),
            "body": self.body.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class Block(Stm):
    body: Stm

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "Block",
            "body": self.body.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class Skip(Stm):
    def to_dict(self) -> dict[str, Any]:
        return {"type": "Skip", "span": self.span.to_dict()}


@dataclass(frozen=True)
class Program(ASTNode):
    body: Stm

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "Program",
            "body": self.body.to_dict(),
            "span": self.span.to_dict(),
        }
