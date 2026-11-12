import json
from pathlib import Path

from sipl.cli import EXIT_OK, EXIT_RUNTIME_ERROR, EXIT_SYNTAX_OR_USAGE_ERROR, main


def test_cli_check_and_parse_json(tmp_path: Path, capsys):
    sipl_file = tmp_path / "prog.sipl"
    sipl_file.write_text("begin R := 1; T := R + 2 end", encoding="utf-8")

    code = main(["check", str(sipl_file), "--json"])
    assert code == EXIT_OK
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "ok"
    assert out["valid"] is True
    assert out["leaf_count"] == 11

    code_parse = main(["parse", str(sipl_file), "--json"])
    assert code_parse == EXIT_OK
    out_parse = json.loads(capsys.readouterr().out)
    assert out_parse["ast"]["type"] == "Program"


def test_cli_run_and_trace_variant_08(tmp_path: Path, capsys):
    sipl_file = tmp_path / "var08.sipl"
    sipl_file.write_text(
        """
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
        """,
        encoding="utf-8",
    )

    code_run = main(["run", str(sipl_file), "-v", "N=3", "--json"])
    assert code_run == EXIT_OK
    run_payload = json.loads(capsys.readouterr().out)
    assert run_payload["final_state"] == {"N": 0, "R": 15, "T": 8}
    assert run_payload["loop_iterations"] == 3

    code_trace = main(["trace", str(sipl_file), "--state", '{"N": 3}', "--json"])
    assert code_trace == EXIT_OK
    trace_payload = json.loads(capsys.readouterr().out)
    assert trace_payload["final_state"] == {"N": 0, "R": 15, "T": 8}
    assert len(trace_payload["trace"]) > 10


def test_cli_term_and_visualize_svg(tmp_path: Path, capsys):
    sipl_file = tmp_path / "power.sipl"
    sipl_file.write_text(
        """
        begin
          R := 1;
          while Y > 0 do
          begin
            R := R * X;
            Y := Y - 1
          end
        end
        """,
        encoding="utf-8",
    )

    code_term = main(["term", str(sipl_file), "--json"])
    assert code_term == EXIT_OK
    term_payload = json.loads(capsys.readouterr().out)
    assert "WH(" in term_payload["term"]
    assert len(term_payload["steps"]) > 5

    svg_file = tmp_path / "tree.svg"
    code_vis = main(["visualize", str(sipl_file), "-f", "svg", "-o", str(svg_file)])
    assert code_vis == EXIT_OK
    capsys.readouterr()
    assert svg_file.exists()
    assert svg_file.read_text(encoding="utf-8").startswith("<svg")


def test_cli_text_mode_outputs(tmp_path: Path, capsys):
    sipl_file = tmp_path / "simple.sipl"
    sipl_file.write_text("begin X := 5 end", encoding="utf-8")

    assert main(["check", str(sipl_file)]) == EXIT_OK
    assert "Syntax check: OK" in capsys.readouterr().out

    assert main(["run", str(sipl_file)]) == EXIT_OK
    assert "[X \u21a6 5]" in capsys.readouterr().out

    assert main(["trace", str(sipl_file)]) == EXIT_OK
    assert "Execution trace:" in capsys.readouterr().out

    assert main(["term", str(sipl_file)]) == EXIT_OK
    assert "AS^X" in capsys.readouterr().out


def test_cli_error_exit_codes(tmp_path: Path, capsys):
    bad_file = tmp_path / "bad.sipl"
    bad_file.write_text("begin R = 1 end", encoding="utf-8")

    code_syn = main(["check", str(bad_file), "--json"])
    assert code_syn == EXIT_SYNTAX_OR_USAGE_ERROR
    err_syn = json.loads(capsys.readouterr().out)
    assert err_syn["error_type"] == "SyntaxError"

    rt_file = tmp_path / "rt.sipl"
    rt_file.write_text("begin R := UNKNOWN + 1 end", encoding="utf-8")
    code_rt = main(["run", str(rt_file), "--json"])
    assert code_rt == EXIT_RUNTIME_ERROR
    err_rt = json.loads(capsys.readouterr().out)
    assert err_rt["error_type"] == "RuntimeError"

    code_missing = main(["check", str(tmp_path / "nope.sipl"), "--json"])
    assert code_missing == EXIT_SYNTAX_OR_USAGE_ERROR