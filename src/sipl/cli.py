from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sipl.ast import SIPLSyntaxError
from sipl.interpreter import SIPLRuntimeError, State, execute_program
from sipl.parser import parse_program
from sipl.semantics import build_semantic_term
from sipl.visualization import build_parse_tree

EXIT_OK = 0
EXIT_SYNTAX_OR_USAGE_ERROR = 1
EXIT_RUNTIME_ERROR = 2


def _parse_initial_state(
    state_json: str | None,
    var_items: list[str] | None,
) -> State:
    data: dict[str, int] = {}
    if state_json:
        loaded = json.loads(state_json)
        if not isinstance(loaded, dict):
            raise ValueError('State JSON must be an object like {"N": 3}.')
        for k, v in loaded.items():
            data[str(k)] = int(v)
    if var_items:
        for item in var_items:
            if "=" not in item:
                raise ValueError(f"Invalid variable format '{item}'. Use NAME=VALUE.")
            name, raw_val = item.split("=", 1)
            data[name.strip()] = int(raw_val.strip())
    return State(data)


def _read_source(path_str: str) -> str:
    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path_str}")
    return path.read_text(encoding="utf-8")


def _print_output(payload: dict[str, Any], as_json: bool, text_view: str) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(text_view)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sipl",
        description="SIPL Language Toolkit CLI: syntax, interpreter, trace, visualization, and semantic terms.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_parse = subparsers.add_parser("parse", help="Build a typed AST of a SIPL program.")
    p_parse.add_argument("file", help="Path to the .sipl file.")
    p_parse.add_argument("--json", action="store_true", help="Output result in JSON format.")

    p_check = subparsers.add_parser(
        "check",
        help="Check program syntax and parse tree leaf traversal.",
    )
    p_check.add_argument("file", help="Path to the .sipl file.")
    p_check.add_argument("--json", action="store_true", help="Output result in JSON format.")

    p_run = subparsers.add_parser("run", help="Execute a SIPL program on an initial state.")
    p_run.add_argument("file", help="Path to the .sipl file.")
    p_run.add_argument(
        "-v",
        "--var",
        action="append",
        default=[],
        help="Set initial variable value (e.g., -v N=3).",
    )
    p_run.add_argument("--state", help='Initial state in JSON format (e.g., \'{"N": 3}\').')
    p_run.add_argument("--max-steps", type=int, default=10_000, help="Execution step limit.")
    p_run.add_argument("--json", action="store_true", help="Output result in JSON format.")

    p_trace = subparsers.add_parser(
        "trace",
        help="Execute a SIPL program and print step-by-step state trace (AF_*).",
    )
    p_trace.add_argument("file", help="Path to the .sipl file.")
    p_trace.add_argument(
        "-v",
        "--var",
        action="append",
        default=[],
        help="Set initial variable value (e.g., -v N=3).",
    )
    p_trace.add_argument("--state", help="Initial state in JSON format.")
    p_trace.add_argument("--max-steps", type=int, default=10_000, help="Execution step limit.")
    p_trace.add_argument("--json", action="store_true", help="Output result in JSON format.")

    p_term = subparsers.add_parser(
        "term",
        help="Build the semantic term of a SIPL program in course notation (SEM-01).",
    )
    p_term.add_argument("file", help="Path to the .sipl file.")
    p_term.add_argument("--json", action="store_true", help="Output result in JSON format.")

    p_vis = subparsers.add_parser(
        "visualize",
        help="Visualize the parse tree (VIS-01: text, json, dot, svg).",
    )
    p_vis.add_argument("file", help="Path to the .sipl file.")
    p_vis.add_argument(
        "-f",
        "--format",
        choices=["text", "json", "dot", "svg"],
        default="text",
        help="Parse tree export format.",
    )
    p_vis.add_argument("-o", "--output", help="Path to save the output file.")

    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = build_arg_parser()
    args = parser.parse_args(argv)
    as_json = getattr(args, "json", False)

    try:
        source = _read_source(args.file)

        if args.command == "parse":
            prog = parse_program(source)
            payload = {"status": "ok", "command": "parse", "ast": prog.to_dict()}
            text_out = json.dumps(prog.to_dict(), ensure_ascii=False, indent=2)
            _print_output(payload, as_json, text_out)
            return EXIT_OK

        if args.command == "check":
            prog = parse_program(source)
            tree = build_parse_tree(source)
            leaves = tree.collect_leaves()
            payload = {
                "status": "ok",
                "command": "check",
                "valid": True,
                "leaf_count": len(leaves),
                "numbered_leaves": tree.numbered_leaves_text(),
                "reconstructed_program": tree.reconstructed_program(),
                "span": prog.span.to_dict(),
            }
            text_out = (
                f"Syntax check: OK (parse tree leaves: {len(leaves)})\n"
                f"Left-to-right leaf traversal:\n  {tree.numbered_leaves_text()}"
            )
            _print_output(payload, as_json, text_out)
            return EXIT_OK

        if args.command in ("run", "trace"):
            init_state = _parse_initial_state(args.state, args.var)
            res = execute_program(source, init_state, max_steps=args.max_steps)
            if args.command == "run":
                payload = {
                    "status": "ok",
                    "command": "run",
                    "initial_state": res.initial_state.to_dict(),
                    "final_state": res.final_state.to_dict(),
                    "final_state_formatted": res.final_state.format_sipl(),
                    "steps_executed": res.steps_executed,
                    "loop_iterations": res.loop_iterations,
                }
                text_out = (
                    f"Initial state st: {res.initial_state.format_sipl()}\n"
                    f"Final state st': {res.final_state.format_sipl()}\n"
                    f"Steps executed: {res.steps_executed} (loop iterations: {res.loop_iterations})"
                )
                _print_output(payload, as_json, text_out)
                return EXIT_OK

            payload = {
                "status": "ok",
                "command": "trace",
                **res.to_dict(),
            }
            lines = [
                f"Initial state: {res.initial_state.format_sipl()}",
                "Execution trace:",
            ]
            for ev in res.trace:
                st_after = State(ev.state_after).format_sipl()
                lines.append(
                    f"  [step {ev.step:02d}] {ev.kind} ({ev.rule}, {ev.statement_type}) -> {st_after} | {ev.details}"
                )
            lines.append(f"Final state: {res.final_state.format_sipl()}")
            _print_output(payload, as_json, "\n".join(lines))
            return EXIT_OK

        if args.command == "term":
            term_res = build_semantic_term(source)
            payload = {
                "status": "ok",
                "command": "term",
                **term_res.to_dict(),
            }
            lines = ["Step-by-step semantic term derivation (NS_* rules):"]
            for s in term_res.steps:
                lines.append(f"  {s.step:02d}. [{s.rule}] {s.category}({s.source_syntax}) = {s.semantic_term}")
            lines.append("")
            lines.append(f"Full semantic term:\n  {term_res.term}")
            lines.append(f"LaTeX:\n  {term_res.latex}")
            _print_output(payload, as_json, "\n".join(lines))
            return EXIT_OK

        if args.command == "visualize":
            tree = build_parse_tree(source)
            fmt = args.format
            if fmt == "text":
                rendered = tree.to_text()
            elif fmt == "json":
                rendered = tree.to_json()
            elif fmt == "dot":
                rendered = tree.to_dot()
            else:
                rendered = tree.to_svg()

            if args.output:
                out_path = Path(args.output)
                out_path.write_text(rendered, encoding="utf-8")
                print(f"Visualization output ({fmt}) saved to: {out_path}")
            else:
                print(rendered)
            return EXIT_OK

    except SIPLSyntaxError as exc:
        if as_json:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "error_type": "SyntaxError",
                        "diagnostic": exc.diagnostic.to_dict(),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print(exc.diagnostic.format_pretty(), file=sys.stderr)
        return EXIT_SYNTAX_OR_USAGE_ERROR

    except SIPLRuntimeError as exc:
        if as_json:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "error_type": "RuntimeError",
                        "diagnostic": exc.diagnostic.to_dict(),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print(exc.diagnostic.format_pretty(), file=sys.stderr)
        return EXIT_RUNTIME_ERROR

    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        if as_json:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "error_type": "UsageError",
                        "message": str(exc),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return EXIT_SYNTAX_OR_USAGE_ERROR

    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
