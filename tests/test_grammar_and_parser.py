import pytest

from sipl.ast import (
    Assign,
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
    SIPLSyntaxError,
    Var,
    While,
)
from sipl.parser import parse_program


def test_pos_01_variant_08_geometric_progression():
    code = """
    begin
    R:=1;
    T:=1;
    while N>0 do
    begin
    T:=T*2;
    R:=R+T;
    N:=N-1
    end
    end
    """
    prog = parse_program(code)
    assert isinstance(prog, Program)
    assert isinstance(prog.body, Seq)
    assert isinstance(prog.body.first, Assign)
    assert prog.body.first.var.name == "R"
    assert isinstance(prog.body.first.expr, Num)
    assert prog.body.first.expr.value == 1

    seq2 = prog.body.second
    assert isinstance(seq2, Seq)
    while_node = seq2.second
    assert isinstance(while_node, While)
    assert isinstance(while_node.body, Block)


def test_pos_02_variant_08_unicode_multiply():
    code = """
    begin
      R := 1;
      T := 1;
      while N > 0 do
      begin
        T := T × 2;
        R := R + T;
        N := N - 1
      end
    end
    """
    prog = parse_program(code)
    while_node = prog.body.second.second
    first_in_loop = while_node.body.body.first
    assert isinstance(first_in_loop, Assign)
    assert isinstance(first_in_loop.expr, BinOp)
    assert first_in_loop.expr.op == "*"


def test_pos_03_practicum_power_xy():
    code = """
    begin
      R := 1;
      while Y > 0 do
      begin
        R := R * X;
        Y := Y - 1
      end
    end
    """
    prog = parse_program(code)
    assert isinstance(prog, Program)
    assert isinstance(prog.body, Seq)


def test_pos_04_nikitchenko_gcd():
    code = """
    begin
      while ¬ M = N do
        if M > N then M := M - N else N := N - M
    end
    """
    prog = parse_program(code)
    assert isinstance(prog.body, While)
    assert isinstance(prog.body.cond, NotOp)
    assert isinstance(prog.body.cond.operand, CmpOp)
    assert isinstance(prog.body.body, If)


def test_pos_05_mkr1_integer_division():
    code = """
    begin
      R := 0;
      while X >= Y do
      begin
        X := X - Y;
        R := R + 1
      end
    end
    """
    prog = parse_program(code)
    assert isinstance(prog.body, Seq)
    assert isinstance(prog.body.second, While)
    assert prog.body.second.cond.op == ">="


def test_pos_06_operator_precedence_mul_over_add():
    code = "begin R := X + Y * Z end"
    prog = parse_program(code)
    assert isinstance(prog.body, Assign)
    expr = prog.body.expr
    assert isinstance(expr, BinOp)
    assert expr.op == "+"
    assert isinstance(expr.left, Var) and expr.left.name == "X"
    assert isinstance(expr.right, BinOp) and expr.right.op == "*"


def test_pos_07_left_associativity_subtraction():
    code = "begin R := A - B - C end"
    prog = parse_program(code)
    assert isinstance(prog.body, Assign)
    expr = prog.body.expr
    assert isinstance(expr, BinOp) and expr.op == "-"
    assert isinstance(expr.left, BinOp) and expr.left.op == "-"
    assert isinstance(expr.right, Var) and expr.right.name == "C"


def test_pos_08_boolean_precedence_not_over_or():
    code = "begin if ¬ A = 1 ∨ B > 2 then skip else skip end"
    prog = parse_program(code)
    assert isinstance(prog.body, If)
    cond = prog.body.cond
    assert isinstance(cond, OrOp)
    assert isinstance(cond.left, NotOp)
    assert isinstance(cond.right, CmpOp)


def test_pos_09_parentheses_in_aexp_and_bexp():
    code = "begin if ¬ (A = 1 ∨ B = 2) then R := (X + Y) * Z else skip end"
    prog = parse_program(code)
    assert isinstance(prog.body, If)
    assert isinstance(prog.body.cond, NotOp)
    assert isinstance(prog.body.cond.operand, ParenBexp)
    then_assign = prog.body.then_branch
    assert isinstance(then_assign, Assign)
    assert isinstance(then_assign.expr, BinOp)
    assert isinstance(then_assign.expr.left, ParenAexp)


def test_pos_10_negative_numbers_and_zero():
    code = "begin X := -1; Y := 0; Z := -42 + 10 end"
    prog = parse_program(code)
    assert isinstance(prog.body, Seq)
    assert isinstance(prog.body.first, Assign)
    assert isinstance(prog.body.first.expr, Num)
    assert prog.body.first.expr.value == -1


def test_pos_11_div_and_mod_operators():
    code = "begin Q := N div 10; M := N mod 2 end"
    prog = parse_program(code)
    assert isinstance(prog.body, Seq)
    assert isinstance(prog.body.first, Assign)
    assert isinstance(prog.body.first.expr, BinOp)
    assert prog.body.first.expr.op == "div"


def test_pos_12_source_spans_and_serialization():
    code = "begin\n  R := 10\nend"
    prog = parse_program(code)
    assert prog.span.start.line == 1
    assert prog.span.end.line == 3
    assert isinstance(prog.body, Assign)
    assert prog.body.span.start.line == 2
    assert prog.body.var.span.start.column == 3
    ast_dict = prog.to_dict()
    assert ast_dict["type"] == "Program"
    assert ast_dict["body"]["type"] == "Assign"


@pytest.mark.parametrize(
    "invalid_code, expected_line",
    [
        ("", 1),
        ("R := 1 end", 1),
        ("begin R := 1", 1),
        ("begin end", 1),
        ("begin\n  R = 1\nend", 2),
        ("begin\n  while X := 0 do skip\nend", 2),
        ("begin\n  if X > 0 then X := 1\nend", 3),
        ("begin\n  if X > 0 X := 1 else X := 2\nend", 2),
        ("begin\n  while X > 0 X := X - 1\nend", 2),
        ("begin\n  R := 1;\nend", 3),
        ("begin\n  R := (X + 1 * 2\nend", 3),
        ("begin\n  while := 5\nend", 2),
    ],
)
def test_negative_invalid_programs_raise_syntax_error(invalid_code: str, expected_line: int):
    with pytest.raises(SIPLSyntaxError) as exc_info:
        parse_program(invalid_code)
    diag = exc_info.value.diagnostic
    assert diag.code == "SIPL-SYNTAX-ERR"
    assert diag.span.start.line == expected_line
    assert len(diag.format_pretty()) > 0
