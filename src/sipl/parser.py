from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from lark import (
    Lark,
    Token,
    Transformer,
    Tree,
    UnexpectedCharacters,
    UnexpectedInput,
    UnexpectedToken,
    v_args,
)
from lark.tree import Meta

from sipl.ast import (
    Aexp,
    ArithOp,
    Assign,
    Bexp,
    BinOp,
    Block,
    CmpOp,
    CompareOp,
    Diagnostic,
    If,
    NotOp,
    Num,
    OrOp,
    ParenAexp,
    ParenBexp,
    Program,
    Seq,
    SIPLSyntaxError,
    Skip,
    SourcePos,
    SourceSpan,
    Stm,
    Var,
    While,
)

RESERVED_KEYWORDS = {
    "begin",
    "end",
    "if",
    "then",
    "else",
    "while",
    "do",
    "skip",
    "div",
    "mod",
    "not",
    "or",
}


def _find_grammar_path() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    candidate = repo_root / "grammar" / "sipl.lark"
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"Grammar file not found: {candidate}")


@lru_cache(maxsize=1)
def get_lark_parser() -> Lark:
    grammar_path = _find_grammar_path()
    grammar_text = grammar_path.read_text(encoding="utf-8")
    return Lark(
        grammar_text,
        start="start",
        parser="lalr",
        propagate_positions=True,
        maybe_placeholders=False,
    )


def _meta_to_span(meta: Meta) -> SourceSpan:
    return SourceSpan(
        start=SourcePos(
            line=getattr(meta, "line", 1),
            column=getattr(meta, "column", 1),
            offset=getattr(meta, "start_pos", 0),
        ),
        end=SourcePos(
            line=getattr(meta, "end_line", getattr(meta, "line", 1)),
            column=getattr(meta, "end_column", getattr(meta, "column", 1)),
            offset=getattr(meta, "end_pos", 0),
        ),
    )


@v_args(meta=True)
class _ASTBuilder(Transformer[Token, Any]):
    def prog_rule(self, meta: Meta, children: list[Any]) -> Program:
        body = cast(Stm, children[1])
        return Program(body=body, span=_meta_to_span(meta))

    def seq_stm(self, meta: Meta, children: list[Any]) -> Seq:
        first = cast(Stm, children[0])
        second = cast(Stm, children[1])
        return Seq(first=first, second=second, span=_meta_to_span(meta))

    def assign_stm(self, meta: Meta, children: list[Any]) -> Assign:
        var = cast(Var, children[0])
        expr = cast(Aexp, children[1])
        return Assign(var=var, expr=expr, span=_meta_to_span(meta))

    def if_stm(self, meta: Meta, children: list[Any]) -> If:
        cond = cast(Bexp, children[1])
        then_branch = cast(Stm, children[3])
        else_branch = cast(Stm, children[5])
        return If(
            cond=cond,
            then_branch=then_branch,
            else_branch=else_branch,
            span=_meta_to_span(meta),
        )

    def while_stm(self, meta: Meta, children: list[Any]) -> While:
        cond = cast(Bexp, children[1])
        body = cast(Stm, children[3])
        return While(cond=cond, body=body, span=_meta_to_span(meta))

    def block_stm(self, meta: Meta, children: list[Any]) -> Block:
        body = cast(Stm, children[1])
        return Block(body=body, span=_meta_to_span(meta))

    def skip_stm(self, meta: Meta, children: list[Any]) -> Skip:
        return Skip(span=_meta_to_span(meta))

    def or_bexp(self, meta: Meta, children: list[Any]) -> OrOp:
        left = cast(Bexp, children[0])
        right = cast(Bexp, children[2])
        return OrOp(left=left, right=right, span=_meta_to_span(meta))

    def not_bexp(self, meta: Meta, children: list[Any]) -> NotOp:
        operand = cast(Bexp, children[1])
        return NotOp(operand=operand, span=_meta_to_span(meta))

    def cmp_bexp(self, meta: Meta, children: list[Any]) -> CmpOp:
        left = cast(Aexp, children[0])
        op_token = cast(Token, children[1])
        right = cast(Aexp, children[2])
        op = cast(CompareOp, str(op_token))
        return CmpOp(op=op, left=left, right=right, span=_meta_to_span(meta))

    def paren_bexp(self, meta: Meta, children: list[Any]) -> ParenBexp:
        cond = cast(Bexp, children[0])
        return ParenBexp(cond=cond, span=_meta_to_span(meta))

    def add_aexp(self, meta: Meta, children: list[Any]) -> BinOp:
        left = cast(Aexp, children[0])
        op_token = cast(Token, children[1])
        right = cast(Aexp, children[2])
        op = cast(ArithOp, str(op_token))
        return BinOp(op=op, left=left, right=right, span=_meta_to_span(meta))

    def mul_aexp(self, meta: Meta, children: list[Any]) -> BinOp:
        left = cast(Aexp, children[0])
        op_token = cast(Token, children[1])
        right = cast(Aexp, children[2])
        raw_op = str(op_token)
        norm_op: ArithOp = "*" if raw_op == "×" else cast(ArithOp, raw_op)
        return BinOp(op=norm_op, left=left, right=right, span=_meta_to_span(meta))

    def paren_aexp(self, meta: Meta, children: list[Any]) -> ParenAexp:
        expr = cast(Aexp, children[0])
        return ParenAexp(expr=expr, span=_meta_to_span(meta))

    def pos_num(self, meta: Meta, children: list[Any]) -> Num:
        token = cast(Token, children[0])
        return Num(value=int(str(token)), span=_meta_to_span(meta))

    def neg_num(self, meta: Meta, children: list[Any]) -> Num:
        token = cast(Token, children[0])
        return Num(value=-int(str(token)), span=_meta_to_span(meta))

    def var_node(self, meta: Meta, children: list[Any]) -> Var:
        token = cast(Token, children[0])
        name = str(token)
        span = _meta_to_span(meta)
        if name in RESERVED_KEYWORDS:
            raise SIPLSyntaxError(
                Diagnostic(
                    message=f"Keyword '{name}' cannot be used as a variable name.",
                    span=span,
                    hint="Choose another variable name (for example, X, Y, R, N).",
                )
            )
        return Var(name=name, span=span)


def _build_syntax_error(exc: UnexpectedInput, source: str) -> SIPLSyntaxError:
    lines = source.splitlines()
    line = max(1, getattr(exc, "line", 1))
    column = max(1, getattr(exc, "column", 1))
    pos_in_stream = getattr(exc, "pos_in_stream", 0) or 0
    source_line = lines[line - 1] if 1 <= line <= len(lines) else None

    span = SourceSpan(
        start=SourcePos(line=line, column=column, offset=pos_in_stream),
        end=SourcePos(line=line, column=column + 1, offset=pos_in_stream + 1),
    )

    hint: str | None = None
    if isinstance(exc, UnexpectedToken):
        token_val = str(exc.token) if exc.token else "<EOF>"
        expected = sorted(exc.expected)
        if token_val == "=":
            hint = "Assignment in SIPL uses ':=' (rule NS1); '=' is only allowed in boolean conditions."
        elif token_val == ":=":
            hint = "Operator ':=' cannot be used inside conditions or expressions (use '=' for comparison)."
        elif "KW_ELSE" in expected:
            hint = "In SIPL, the conditional statement always requires both branches: if <cond> then <stm> else <stm> (rule NS3)."
        elif "KW_END" in expected:
            hint = "Check the closing 'end' or a trailing ';' before 'end'."
        message = f"Unexpected token '{token_val}'. Expected one of: {', '.join(expected[:6])}."
    elif isinstance(exc, UnexpectedCharacters):
        char = source[pos_in_stream] if pos_in_stream < len(source) else "?"
        message = f"Invalid character or construct near '{char}'."
        hint = "Check SIPL operators and identifiers."
    else:
        message = "SIPL program syntax error."

    return SIPLSyntaxError(
        Diagnostic(
            message=message,
            span=span,
            code="SIPL-SYNTAX-ERR",
            hint=hint,
            source_line=source_line,
        )
    )


def parse_concrete_tree(source: str) -> Tree[Token]:
    if not source or not source.strip():
        raise SIPLSyntaxError(
            Diagnostic(
                message="Empty source code. A SIPL program must start with 'begin' and end with 'end'.",
                span=SourceSpan(SourcePos(1, 1, 0), SourcePos(1, 1, 0)),
                hint="Minimal program example: begin skip end",
            )
        )
    parser = get_lark_parser()
    try:
        return parser.parse(source)
    except SIPLSyntaxError:
        raise
    except UnexpectedInput as exc:
        raise _build_syntax_error(exc, source) from exc


def parse_program(source: str) -> Program:
    tree = parse_concrete_tree(source)
    builder = _ASTBuilder()
    try:
        result = builder.transform(tree)
    except SIPLSyntaxError:
        raise
    except Exception as exc:
        if isinstance(exc.__cause__, SIPLSyntaxError):
            raise exc.__cause__ from exc
        raise
    return cast(Program, result)
