import pytest

from sipl.interpreter import (
    DivisionByZeroSIPL,
    Interpreter,
    State,
    StepLimitExceededError,
    UndefinedVariableError,
    execute_program,
)
from sipl.parser import parse_program


def test_state_overlay_and_formatting():
    st1 = State({"M": 8, "N": 16})
    st2 = State({"M": 3, "X": 4, "Y": 2})
    merged = st1.overlay(st2)
    assert merged.to_dict() == {"M": 3, "N": 16, "X": 4, "Y": 2}
    assert st1.to_dict() == {"M": 8, "N": 16}
    assert State({"N": 0, "R": 15, "T": 8}).format_sipl() == "[N \u21a6 0, R \u21a6 15, T \u21a6 8]"
    assert "M" in merged
    assert merged["M"] == 3


def test_variant_08_geometric_progression_execution():
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
    result = execute_program(code, {"N": 3})
    assert result.final_state.to_dict() == {"N": 0, "R": 15, "T": 8}
    assert result.loop_iterations == 3
    assert result.final_state.format_sipl() == "[N \u21a6 0, R \u21a6 15, T \u21a6 8]"


def test_practicum_power_xy_execution():
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
    result = execute_program(code, {"X": 5, "Y": 2})
    assert result.final_state.to_dict() == {"X": 5, "Y": 0, "R": 25}
    assert result.loop_iterations == 2


def test_nikitchenko_gcd_execution():
    code = """
    begin
      while ¬ M = N do
        if M > N then M := M - N else N := N - M
    end
    """
    result = execute_program(code, {"M": 8, "N": 16})
    assert result.final_state.to_dict() == {"M": 8, "N": 8}
    assert result.loop_iterations == 1


def test_mkr1_integer_division_execution():
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
    result = execute_program(code, {"X": 7, "Y": 4})
    assert result.final_state.to_dict() == {"X": 3, "Y": 4, "R": 1}
    assert result.loop_iterations == 1


def test_if_branches_and_skip():
    code = """
    begin
      if (X <= 10) ∨ (Y < 0) then
        if ¬ (X = 10) then R := (X + 2) div 3 else R := X mod 4
      else
        skip
    end
    """
    res_then = execute_program(code, {"X": 7, "Y": 5})
    assert res_then.final_state["R"] == 3

    res_mod = execute_program(code, {"X": 10, "Y": 5})
    assert res_mod.final_state["R"] == 2

    res_else = execute_program(code, {"X": 20, "Y": 5})
    assert res_else.final_state.to_dict() == {"X": 20, "Y": 5}


def test_equitonicity_and_monotonicity_theorem_1_2():
    code = """
    begin
      while ¬ M = N do
        if M > N then M := M - N else N := N - M
    end
    """
    prog = parse_program(code)
    interp = Interpreter()
    st_base = State({"M": 8, "N": 16})
    st_extended = State({"M": 8, "N": 16, "L": 9})

    assert st_base.is_substate_of(st_extended)
    res_base = interp.run(prog, st_base)
    res_ext = interp.run(prog, st_extended)

    assert res_base.final_state.is_substate_of(res_ext.final_state)
    assert res_ext.final_state.to_dict() == {"M": 8, "N": 8, "L": 9}


def test_trace_events_structure_for_variant_08():
    code = """
    begin
      R := 1;
      T := 1;
      while N > 0 do
      begin
        T := T * 2;
        R := R + T;
        N := N - 1
      end
    end
    """
    result = execute_program(code, {"N": 3})
    kinds = [e.kind for e in result.trace]
    assert "BeforeStatement" in kinds
    assert "AfterStatement" in kinds
    assert "VariableChanged" in kinds
    assert "ConditionEvaluated" in kinds
    assert result.trace[-1].kind == "ExecutionFinished"

    while_cond_events = [
        e for e in result.trace if e.kind == "ConditionEvaluated" and e.rule == "AF_WH"
    ]
    assert len(while_cond_events) == 4
    assert [e.details["result"] for e in while_cond_events] == [True, True, True, False]
    assert [e.details["state_label"] for e in while_cond_events] == [
        "st_0",
        "st_1",
        "st_2",
        "st_3",
    ]
    assert while_cond_events[0].state_before == {"N": 3, "R": 1, "T": 1}
    assert while_cond_events[1].state_before == {"N": 2, "R": 3, "T": 2}
    assert while_cond_events[2].state_before == {"N": 1, "R": 7, "T": 4}
    assert while_cond_events[3].state_before == {"N": 0, "R": 15, "T": 8}

    serialized = result.to_dict()
    assert serialized["final_state"] == {"N": 0, "R": 15, "T": 8}
    assert isinstance(serialized["trace"], list)


def test_undefined_variable_raises_error():
    code = "begin R := UNDEFINED_VAR + 1 end"
    with pytest.raises(UndefinedVariableError) as exc_info:
        execute_program(code, {})
    assert exc_info.value.diagnostic.code == "SIPL-UNDEFINED-VAR"


def test_division_by_zero_raises_error():
    code = "begin R := 10 div 0 end"
    with pytest.raises(DivisionByZeroSIPL) as exc_info:
        execute_program(code, {})
    assert exc_info.value.diagnostic.code == "SIPL-DIV-ZERO"


def test_infinite_loop_hits_step_limit():
    code = """
    begin
      X := 1;
      while X > 0 do
        X := X + 1
    end
    """
    with pytest.raises(StepLimitExceededError) as exc_info:
        execute_program(code, {}, max_steps=50)
    assert exc_info.value.diagnostic.code == "SIPL-STEP-LIMIT"