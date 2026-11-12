from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from sipl.ast import (
    Aexp,
    Assign,
    Bexp,
    BinOp,
    Block,
    CmpOp,
    Diagnostic,
    If,
    NotOp,
    Num,
    OrOp,
    ParenAexp,
    ParenBexp,
    Program,
    Seq,
    Skip,
    SourcePos,
    SourceSpan,
    Stm,
    Var,
    While,
)
from sipl.parser import parse_program


class SIPLRuntimeError(Exception):
    def __init__(self, diagnostic: Diagnostic) -> None:
        super().__init__(diagnostic.format_pretty())
        self.diagnostic = diagnostic


class UndefinedVariableError(SIPLRuntimeError):
    pass


class DivisionByZeroSIPL(SIPLRuntimeError):
    pass


class StepLimitExceededError(SIPLRuntimeError):
    pass


def _default_span() -> SourceSpan:
    return SourceSpan(SourcePos(1, 1, 0), SourcePos(1, 1, 0))


@dataclass(frozen=True, slots=True)
class State:
    values: dict[str, int] = field(default_factory=dict)

    def __init__(self, initial: Mapping[str, int] | None = None) -> None:
        copied = {str(k): int(v) for k, v in (initial or {}).items()}
        object.__setattr__(self, "values", copied)

    def overlay(self, other: State | Mapping[str, int]) -> State:
        other_map = other.values if isinstance(other, State) else other
        merged = dict(self.values)
        for k, v in other_map.items():
            merged[str(k)] = int(v)
        return State(merged)

    def deref(self, name: str, span: SourceSpan | None = None) -> int:
        if name not in self.values:
            err_span = span or _default_span()
            raise UndefinedVariableError(
                Diagnostic(
                    message=f"Variable '{name}' is undefined in the current state st (AF_DNM).",
                    span=err_span,
                    code="SIPL-UNDEFINED-VAR",
                    hint=f"Provide an initial value for '{name}' in the input state or initialize it with ':='.",
                )
            )
        return self.values[name]

    def is_substate_of(self, other: State) -> bool:
        return all(k in other.values and other.values[k] == v for k, v in self.values.items())

    def to_dict(self) -> dict[str, int]:
        return dict(self.values)

    def format_sipl(self) -> str:
        items = ", ".join(f"{k} \u21a6 {v}" for k, v in self.values.items())
        return f"[{items}]"

    def __getitem__(self, key: str) -> int:
        return self.deref(key)

    def __contains__(self, key: object) -> bool:
        return key in self.values

    def __eq__(self, other: object) -> bool:
        if isinstance(other, State):
            return self.values == other.values
        if isinstance(other, Mapping):
            return self.values == dict(other)
        return False


EventKind = Literal[
    "BeforeStatement",
    "AfterStatement",
    "VariableChanged",
    "ConditionEvaluated",
    "ExecutionFinished",
]


@dataclass(frozen=True, slots=True)
class TraceEvent:
    step: int
    kind: EventKind
    rule: str
    statement_type: str
    state_before: dict[str, int]
    state_after: dict[str, int]
    span: SourceSpan | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "kind": self.kind,
            "rule": self.rule,
            "statement_type": self.statement_type,
            "state_before": dict(self.state_before),
            "state_after": dict(self.state_after),
            "span": self.span.to_dict() if self.span else None,
            "details": dict(self.details),
        }


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    initial_state: State
    final_state: State
    steps_executed: int
    loop_iterations: int
    trace: list[TraceEvent]

    def to_dict(self) -> dict[str, Any]:
        return {
            "initial_state": self.initial_state.to_dict(),
            "final_state": self.final_state.to_dict(),
            "final_state_formatted": self.final_state.format_sipl(),
            "steps_executed": self.steps_executed,
            "loop_iterations": self.loop_iterations,
            "trace": [event.to_dict() for event in self.trace],
        }


class Interpreter:
    def __init__(self, max_steps: int = 10_000) -> None:
        if max_steps <= 0:
            raise ValueError("max_steps must be positive")
        self.max_steps = max_steps
        self._steps = 0
        self._loop_iterations = 0
        self._trace: list[TraceEvent] = []

    def eval_aexp(self, expr: Aexp, state: State) -> int:
        if isinstance(expr, Num):
            return expr.value
        if isinstance(expr, Var):
            return state.deref(expr.name, expr.span)
        if isinstance(expr, ParenAexp):
            return self.eval_aexp(expr.expr, state)
        if isinstance(expr, BinOp):
            left_val = self.eval_aexp(expr.left, state)
            right_val = self.eval_aexp(expr.right, state)
            if expr.op == "+":
                return left_val + right_val
            if expr.op == "-":
                return left_val - right_val
            if expr.op == "*":
                return left_val * right_val
            if expr.op in ("div", "mod"):
                if right_val == 0:
                    raise DivisionByZeroSIPL(
                        Diagnostic(
                            message=f"Division by zero in operation '{expr.op}'.",
                            span=expr.span,
                            code="SIPL-DIV-ZERO",
                            hint="The right operand must be non-zero.",
                        )
                    )
                if expr.op == "div":
                    return left_val // right_val
                return left_val % right_val
        raise TypeError(f"Unsupported Aexp node: {type(expr)!r}")

    def eval_bexp(self, cond: Bexp, state: State) -> bool:
        if isinstance(cond, ParenBexp):
            return self.eval_bexp(cond.cond, state)
        if isinstance(cond, NotOp):
            return not self.eval_bexp(cond.operand, state)
        if isinstance(cond, OrOp):
            left_res = self.eval_bexp(cond.left, state)
            right_res = self.eval_bexp(cond.right, state)
            return left_res or right_res
        if isinstance(cond, CmpOp):
            left_val = self.eval_aexp(cond.left, state)
            right_val = self.eval_aexp(cond.right, state)
            if cond.op == "=":
                return left_val == right_val
            if cond.op == ">":
                return left_val > right_val
            if cond.op == ">=":
                return left_val >= right_val
            if cond.op == "<":
                return left_val < right_val
            if cond.op == "<=":
                return left_val <= right_val
        raise TypeError(f"Unsupported Bexp node: {type(cond)!r}")

    def _tick(self, span: SourceSpan) -> int:
        self._steps += 1
        if self._steps > self.max_steps:
            raise StepLimitExceededError(
                Diagnostic(
                    message=f"Execution step limit ({self.max_steps}) exceeded. Possible infinite loop.",
                    span=span,
                    code="SIPL-STEP-LIMIT",
                    hint="Check the while loop termination condition or increase max_steps.",
                )
            )
        return self._steps

    def _emit(
        self,
        kind: EventKind,
        rule: str,
        statement_type: str,
        state_before: State,
        state_after: State,
        span: SourceSpan | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self._trace.append(
            TraceEvent(
                step=self._steps,
                kind=kind,
                rule=rule,
                statement_type=statement_type,
                state_before=state_before.to_dict(),
                state_after=state_after.to_dict(),
                span=span,
                details=details or {},
            )
        )

    def _exec_stm(self, stm: Stm, state: State) -> State:
        if isinstance(stm, Skip):
            self._tick(stm.span)
            self._emit("BeforeStatement", "AF_ID", "Skip", state, state, stm.span)
            self._emit("AfterStatement", "AF_ID", "Skip", state, state, stm.span)
            return state

        if isinstance(stm, Block):
            return self._exec_stm(stm.body, state)

        if isinstance(stm, Seq):
            self._emit("BeforeStatement", "AF_SEQ", "Seq", state, state, stm.span)
            mid_state = self._exec_stm(stm.first, state)
            out_state = self._exec_stm(stm.second, mid_state)
            self._emit("AfterStatement", "AF_SEQ", "Seq", state, out_state, stm.span)
            return out_state

        if isinstance(stm, Assign):
            self._tick(stm.span)
            self._emit(
                "BeforeStatement",
                "AF_AS",
                "Assign",
                state,
                state,
                stm.span,
                {"variable": stm.var.name},
            )
            val = self.eval_aexp(stm.expr, state)
            old_val = state.values.get(stm.var.name)
            new_state = state.overlay({stm.var.name: val})
            self._emit(
                "VariableChanged",
                "AF_AS",
                "Assign",
                state,
                new_state,
                stm.span,
                {
                    "variable": stm.var.name,
                    "old_value": old_val,
                    "new_value": val,
                    "overlay": f"st \u2207 [{stm.var.name} \u21a6 {val}]",
                },
            )
            self._emit(
                "AfterStatement",
                "AF_AS",
                "Assign",
                state,
                new_state,
                stm.span,
                {"variable": stm.var.name, "value": val},
            )
            return new_state

        if isinstance(stm, If):
            self._tick(stm.span)
            self._emit("BeforeStatement", "AF_IF", "If", state, state, stm.span)
            cond_val = self.eval_bexp(stm.cond, state)
            self._emit(
                "ConditionEvaluated",
                "AF_IF",
                "If",
                state,
                state,
                stm.cond.span,
                {"result": cond_val, "branch": "then" if cond_val else "else"},
            )
            branch = stm.then_branch if cond_val else stm.else_branch
            out_state = self._exec_stm(branch, state)
            self._emit(
                "AfterStatement",
                "AF_IF",
                "If",
                state,
                out_state,
                stm.span,
                {"branch_taken": "then" if cond_val else "else"},
            )
            return out_state

        if isinstance(stm, While):
            self._emit("BeforeStatement", "AF_WH", "While", state, state, stm.span)
            curr_state = state
            local_iter = 0
            while True:
                self._tick(stm.cond.span)
                cond_val = self.eval_bexp(stm.cond, curr_state)
                self._emit(
                    "ConditionEvaluated",
                    "AF_WH",
                    "While",
                    curr_state,
                    curr_state,
                    stm.cond.span,
                    {
                        "result": cond_val,
                        "iteration": local_iter,
                        "state_label": f"st_{local_iter}",
                    },
                )
                if not cond_val:
                    break
                local_iter += 1
                self._loop_iterations += 1
                curr_state = self._exec_stm(stm.body, curr_state)
            self._emit(
                "AfterStatement",
                "AF_WH",
                "While",
                state,
                curr_state,
                stm.span,
                {"iterations": local_iter},
            )
            return curr_state

        raise TypeError(f"Unsupported Stm node: {type(stm)!r}")

    def run(
        self,
        program: Program | str,
        initial_state: State | Mapping[str, int] | None = None,
    ) -> ExecutionResult:
        ast_prog = parse_program(program) if isinstance(program, str) else program
        init_st = initial_state if isinstance(initial_state, State) else State(initial_state)
        self._steps = 0
        self._loop_iterations = 0
        self._trace = []

        final_st = self._exec_stm(ast_prog.body, init_st)
        self._emit(
            "ExecutionFinished",
            "NS_Prog",
            "Program",
            init_st,
            final_st,
            ast_prog.span,
            {
                "steps_executed": self._steps,
                "loop_iterations": self._loop_iterations,
                "final_state_formatted": final_st.format_sipl(),
            },
        )
        return ExecutionResult(
            initial_state=init_st,
            final_state=final_st,
            steps_executed=self._steps,
            loop_iterations=self._loop_iterations,
            trace=list(self._trace),
        )


def execute_program(
    program: Program | str,
    initial_state: State | Mapping[str, int] | None = None,
    *,
    max_steps: int = 10_000,
) -> ExecutionResult:
    interpreter = Interpreter(max_steps=max_steps)
    return interpreter.run(program, initial_state)