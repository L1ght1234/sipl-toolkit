import json

from sipl.semantics import build_semantic_term
from sipl.visualization import build_parse_tree


def test_vis_01_variant_08_leaf_traversal_matches_notebook():
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
    tree = build_parse_tree(code)
    leaves = tree.collect_leaves()
    assert len(leaves) == 34

    expected_numbered = (
        "1 begin 2 R 3 := 4 1 5 ; 6 T 7 := 8 1 9 ; 10 while 11 N 12 > 13 0 14 do "
        "15 begin 16 T 17 := 18 T 19 * 20 2 21 ; 22 R 23 := 24 R 25 + 26 T 27 ; "
        "28 N 29 := 30 N 31 - 32 1 33 end 34 end"
    )
    assert tree.numbered_leaves_text() == expected_numbered


def test_vis_01_practicum_power_xy_24_leaves():
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
    tree = build_parse_tree(code)
    leaves = tree.collect_leaves()
    assert len(leaves) == 24
    expected = (
        "1 begin 2 R 3 := 4 1 5 ; 6 while 7 Y 8 > 9 0 10 do 11 begin 12 R 13 := 14 R "
        "15 * 16 X 17 ; 18 Y 19 := 20 Y 21 - 22 1 23 end 24 end"
    )
    assert tree.numbered_leaves_text() == expected


def test_vis_01_exporters_text_json_dot_svg():
    code = """
    begin
      if ¬ (A = 0 ∨ B > 1) then
        R := (A + B) * 2
      else
        skip
    end
    """
    tree = build_parse_tree(code)

    text_out = tree.to_text()
    assert "<program> (NP1)" in text_out
    assert "<statement> (NS3)" in text_out
    assert "<condition> (NB4)" in text_out
    assert "Left-to-right leaf traversal:" in text_out

    json_str = tree.to_json()
    parsed_json = json.loads(json_str)
    assert parsed_json["parse_tree"]["label"] == "<program>"
    assert len(parsed_json["leaf_traversal"]) > 10

    dot_out = tree.to_dot()
    assert "digraph SIPLParseTree" in dot_out
    assert "<program>" in dot_out

    svg_out = tree.to_svg()
    assert svg_out.startswith("<svg")
    assert svg_out.endswith("</svg>")
    assert "&lt;program&gt;" in svg_out


def test_sem_01_golden_variant_08_lab1_pdf():
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
    res = build_semantic_term(code)

    expected_term = (
        "AS^R(1\u0305) \u00b7 AS^T(1\u0305) \u00b7 WH(S^2(gr, N\u21d2, 0\u0305), "
        "AS^T(S^2(mult, T\u21d2, 2\u0305)) \u00b7 AS^R(S^2(add, R\u21d2, T\u21d2)) \u00b7 AS^N(S^2(sub, N\u21d2, 1\u0305)))"
    )
    assert res.term == expected_term

    expected_latex = (
        "AS^{R}(\\overline{1}) \\cdot AS^{T}(\\overline{1}) \\cdot WH(S^2(gr, N\\Rightarrow, \\overline{0}), "
        "AS^{T}(S^2(mult, T\\Rightarrow, \\overline{2})) \\cdot AS^{R}(S^2(add, R\\Rightarrow, T\\Rightarrow)) "
        "\\cdot AS^{N}(S^2(sub, N\\Rightarrow, \\overline{1})))"
    )
    assert res.latex == expected_latex

    rules_used = [step.rule for step in res.steps]
    assert "NS_Prog" in rules_used
    assert "NS_Stm_Seq" in rules_used
    assert "NS_Stm_As" in rules_used
    assert "NS_Stm_Wh" in rules_used
    assert "NS_Stm_BE" in rules_used
    assert "NS_A_Mult" in rules_used
    assert "NS_A_Add" in rules_used
    assert "NS_A_Sub" in rules_used
    assert "NS_B_gr" in rules_used


def test_sem_01_golden_practicum_power_xy():
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
    res = build_semantic_term(code)
    expected = (
        "AS^R(1\u0305) \u00b7 WH(S^2(gr, Y\u21d2, 0\u0305), "
        "AS^R(S^2(mult, R\u21d2, X\u21d2)) \u00b7 AS^Y(S^2(sub, Y\u21d2, 1\u0305)))"
    )
    assert res.term == expected


def test_sem_01_golden_nikitchenko_gcd():
    code = """
    begin
      while ¬ M = N do
        if M > N then M := M - N else N := N - M
    end
    """
    res = build_semantic_term(code)
    expected = (
        "WH(S^1(neg, S^2(eq, M\u21d2, N\u21d2)), "
        "IF(S^2(gr, M\u21d2, N\u21d2), "
        "AS^M(S^2(sub, M\u21d2, N\u21d2)), "
        "AS^N(S^2(sub, N\u21d2, M\u21d2))))"
    )
    assert res.term == expected


def test_sem_01_golden_mkr1_integer_division():
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
    res = build_semantic_term(code)
    expected = (
        "AS^R(0\u0305) \u00b7 WH(S^2(gre, X\u21d2, Y\u21d2), "
        "AS^X(S^2(sub, X\u21d2, Y\u21d2)) \u00b7 AS^R(S^2(add, R\u21d2, 1\u0305)))"
    )
    assert res.term == expected


def test_sem_01_all_remaining_rules_and_serialization():
    code = """
    begin
      if (X < 10) ∨ (Y <= 5) then
        R := (X div 2) mod 3
      else
        skip
    end
    """
    res = build_semantic_term(code)
    assert "S^2(or, S^2(less, X\u21d2, 1\u03050\u0305), S^2(le, Y\u21d2, 5\u0305))" in res.term
    assert "S^2(mod, S^2(div, X\u21d2, 2\u0305), 3\u0305)" in res.term
    assert ", id)" in res.term
    data = res.to_dict()
    assert data["term"] == res.term
    assert len(data["steps"]) > 0