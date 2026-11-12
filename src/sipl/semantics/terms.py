from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sipl.ast import (
    Aexp,
    Assign,
    Bexp,
    BinOp,
    Block,
    CmpOp,
    If,
    NotOp,
    Num,
    OrOp,
    ParenAexp,
    ParenBexp,
    Program,
    Seq,
    Skip,
    Stm,
    Var,
    While,
)
from sipl.parser import parse_program

ARITH_FUNC_MAP: dict[str, tuple[str, str]] = {
    "+": ("add", "NS_A_Add"),
    "-": ("sub", "NS_A_Sub"),
    "*": ("mult", "NS_A_Mult"),
    "div": ("div", "NS_A_Div"),
    "mod": ("mod", "NS_A_Mod"),
}

CMP_FUNC_MAP: dict[str, tuple[str, str]] = {
    "=": ("eq", "NS_B_eq"),
    ">": ("gr", "NS_B_gr"),
    ">=": ("gre", "NS_B_gre"),
    "<": ("less", "NS_B_less"),
    "<=": ("le", "NS_B_le"),
}


def format_overline_num(value: int) -> str:
    text = str(value)
    return "".join(f"{ch}\u0305" for ch in text)


@dataclass(frozen=True, slots=True)
class DerivationStep:
    step: int
    rule: str
    category: str
    source_syntax: str
    semantic_term: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "rule": self.rule,
            "category": self.category,
            "source_syntax": self.source_syntax,
            "semantic_term": self.semantic_term,
        }


@dataclass(frozen=True, slots=True)
class SemanticTermResult:
    term: str
    latex: str
    steps: list[DerivationStep] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "term": self.term,
            "latex": self.latex,
            "steps": [s.to_dict() for s in self.steps],
        }


def _syntax_str_aexp(expr: Aexp) -> str:
    if isinstance(expr, Num):
        return str(expr.value)
    if isinstance(expr, Var):
        return expr.name
    if isinstance(expr, ParenAexp):
        return f"({_syntax_str_aexp(expr.expr)})"
    if isinstance(expr, BinOp):
        return f"{_syntax_str_aexp(expr.left)} {expr.op} {_syntax_str_aexp(expr.right)}"
    raise TypeError(f"Unsupported Aexp: {type(expr)!r}")


def _syntax_str_bexp(cond: Bexp) -> str:
    if isinstance(cond, CmpOp):
        return f"{_syntax_str_aexp(cond.left)} {cond.op} {_syntax_str_aexp(cond.right)}"
    if isinstance(cond, NotOp):
        return f"\u00ac{_syntax_str_bexp(cond.operand)}"
    if isinstance(cond, OrOp):
        return f"{_syntax_str_bexp(cond.left)} \u2228 {_syntax_str_bexp(cond.right)}"
    if isinstance(cond, ParenBexp):
        return f"({_syntax_str_bexp(cond.cond)})"
    raise TypeError(f"Unsupported Bexp: {type(cond)!r}")


def _syntax_str_stm(stm: Stm) -> str:
    if isinstance(stm, Skip):
        return "skip"
    if isinstance(stm, Assign):
        return f"{stm.var.name} := {_syntax_str_aexp(stm.expr)}"
    if isinstance(stm, Seq):
        return f"{_syntax_str_stm(stm.first)}; {_syntax_str_stm(stm.second)}"
    if isinstance(stm, Block):
        return f"begin {_syntax_str_stm(stm.body)} end"
    if isinstance(stm, If):
        return (
            f"if {_syntax_str_bexp(stm.cond)} "
            f"then {_syntax_str_stm(stm.then_branch)} "
            f"else {_syntax_str_stm(stm.else_branch)}"
        )
    if isinstance(stm, While):
        return f"while {_syntax_str_bexp(stm.cond)} do {_syntax_str_stm(stm.body)}"
    raise TypeError(f"Unsupported Stm: {type(stm)!r}")


class SemanticTermBuilder:
    def __init__(self) -> None:
        self._steps: list[DerivationStep] = []

    def _record(self, rule: str, category: str, syntax: str, term: str) -> None:
        self._steps.append(
            DerivationStep(
                step=len(self._steps) + 1,
                rule=rule,
                category=category,
                source_syntax=syntax,
                semantic_term=term,
            )
        )

    def sem_A(self, expr: Aexp) -> tuple[str, str]:
        syntax = _syntax_str_aexp(expr)
        if isinstance(expr, Num):
            term = format_overline_num(expr.value)
            latex = f"\\overline{{{expr.value}}}"
            self._record("NS_A_Num", "sem_A", syntax, term)
            return term, latex

        if isinstance(expr, Var):
            term = f"{expr.name}\u21d2"
            latex = f"{expr.name}\\Rightarrow"
            self._record("NS_A_Var", "sem_A", syntax, term)
            return term, latex

        if isinstance(expr, ParenAexp):
            inner_term, inner_latex = self.sem_A(expr.expr)
            self._record("NS_A_Par", "sem_A", syntax, inner_term)
            return inner_term, inner_latex

        if isinstance(expr, BinOp):
            func_name, rule_name = ARITH_FUNC_MAP[expr.op]
            left_t, left_l = self.sem_A(expr.left)
            right_t, right_l = self.sem_A(expr.right)
            term = f"S^2({func_name}, {left_t}, {right_t})"
            latex = f"S^2({func_name}, {left_l}, {right_l})"
            self._record(rule_name, "sem_A", syntax, term)
            return term, latex

        raise TypeError(f"Unsupported Aexp: {type(expr)!r}")

    def sem_B(self, cond: Bexp) -> tuple[str, str]:
        syntax = _syntax_str_bexp(cond)
        if isinstance(cond, ParenBexp):
            inner_t, inner_l = self.sem_B(cond.cond)
            self._record("NS_B_Par", "sem_B", syntax, inner_t)
            return inner_t, inner_l

        if isinstance(cond, NotOp):
            op_t, op_l = self.sem_B(cond.operand)
            term = f"S^1(neg, {op_t})"
            latex = f"S^1(neg, {op_l})"
            self._record("NS_B_neg", "sem_B", syntax, term)
            return term, latex

        if isinstance(cond, OrOp):
            left_t, left_l = self.sem_B(cond.left)
            right_t, right_l = self.sem_B(cond.right)
            term = f"S^2(or, {left_t}, {right_t})"
            latex = f"S^2(or, {left_l}, {right_l})"
            self._record("NS_B_or", "sem_B", syntax, term)
            return term, latex

        if isinstance(cond, CmpOp):
            func_name, rule_name = CMP_FUNC_MAP[cond.op]
            left_t, left_l = self.sem_A(cond.left)
            right_t, right_l = self.sem_A(cond.right)
            term = f"S^2({func_name}, {left_t}, {right_t})"
            latex = f"S^2({func_name}, {left_l}, {right_l})"
            self._record(rule_name, "sem_B", syntax, term)
            return term, latex

        raise TypeError(f"Unsupported Bexp: {type(cond)!r}")

    def sem_S(self, stm: Stm) -> tuple[str, str]:
        syntax = _syntax_str_stm(stm)
        if isinstance(stm, Skip):
            self._record("NS_Stm_skip", "sem_S", syntax, "id")
            return "id", "id"

        if isinstance(stm, Block):
            inner_t, inner_l = self.sem_S(stm.body)
            self._record("NS_Stm_BE", "sem_S", syntax, inner_t)
            return inner_t, inner_l

        if isinstance(stm, Assign):
            a_t, a_l = self.sem_A(stm.expr)
            term = f"AS^{stm.var.name}({a_t})"
            latex = f"AS^{{{stm.var.name}}}({a_l})"
            self._record("NS_Stm_As", "sem_S", syntax, term)
            return term, latex

        if isinstance(stm, Seq):
            s1_t, s1_l = self.sem_S(stm.first)
            s2_t, s2_l = self.sem_S(stm.second)
            term = f"{s1_t} \u00b7 {s2_t}"
            latex = f"{s1_l} \\cdot {s2_l}"
            self._record("NS_Stm_Seq", "sem_S", syntax, term)
            return term, latex

        if isinstance(stm, If):
            b_t, b_l = self.sem_B(stm.cond)
            s1_t, s1_l = self.sem_S(stm.then_branch)
            s2_t, s2_l = self.sem_S(stm.else_branch)
            term = f"IF({b_t}, {s1_t}, {s2_t})"
            latex = f"IF({b_l}, {s1_l}, {s2_l})"
            self._record("NS_Stm_If", "sem_S", syntax, term)
            return term, latex

        if isinstance(stm, While):
            b_t, b_l = self.sem_B(stm.cond)
            body_t, body_l = self.sem_S(stm.body)
            term = f"WH({b_t}, {body_t})"
            latex = f"WH({b_l}, {body_l})"
            self._record("NS_Stm_Wh", "sem_S", syntax, term)
            return term, latex

        raise TypeError(f"Unsupported Stm: {type(stm)!r}")

    def sem_P(self, program: Program) -> SemanticTermResult:
        self._steps = []
        body_t, body_l = self.sem_S(program.body)
        prog_syntax = f"begin {_syntax_str_stm(program.body)} end"
        self._record("NS_Prog", "sem_P", prog_syntax, body_t)
        return SemanticTermResult(
            term=body_t,
            latex=body_l,
            steps=list(self._steps),
        )


def build_semantic_term(program: Program | str) -> SemanticTermResult:
    ast_prog = parse_program(program) if isinstance(program, str) else program
    builder = SemanticTermBuilder()
    return builder.sem_P(ast_prog)