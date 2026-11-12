from __future__ import annotations

import json
from dataclasses import dataclass, field
from html import escape
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
    SourceSpan,
    Stm,
    Var,
    While,
)
from sipl.parser import parse_program


@dataclass(slots=True)
class ParseTreeNode:
    node_id: int
    label: str
    kind: str
    rule: str | None = None
    span: SourceSpan | None = None
    source_fragment: str | None = None
    leaf_index: int | None = None
    children: list[ParseTreeNode] = field(default_factory=list)

    @property
    def is_terminal(self) -> bool:
        return self.kind == "terminal"

    def collect_leaves(self) -> list[ParseTreeNode]:
        if self.is_terminal:
            return [self]
        leaves: list[ParseTreeNode] = []
        for child in self.children:
            leaves.extend(child.collect_leaves())
        return leaves

    def numbered_leaves_text(self) -> str:
        leaves = self.collect_leaves()
        return " ".join(f"{leaf.leaf_index} {leaf.label}" for leaf in leaves)

    def reconstructed_program(self) -> str:
        leaves = self.collect_leaves()
        return " ".join(leaf.label for leaf in leaves)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "label": self.label,
            "kind": self.kind,
            "rule": self.rule,
            "leaf_index": self.leaf_index,
            "span": self.span.to_dict() if self.span else None,
            "source_fragment": self.source_fragment,
            "children": [child.to_dict() for child in self.children],
        }

    def to_json(self, indent: int = 2) -> str:
        payload = {
            "parse_tree": self.to_dict(),
            "leaf_traversal": [
                {"index": leaf.leaf_index, "token": leaf.label}
                for leaf in self.collect_leaves()
            ],
            "numbered_leaves_text": self.numbered_leaves_text(),
            "reconstructed_program": self.reconstructed_program(),
        }
        return json.dumps(payload, ensure_ascii=False, indent=indent)

    def to_text(self) -> str:
        lines: list[str] = []

        def _render(node: ParseTreeNode, prefix: str, is_last: bool, is_root: bool) -> None:
            connector = "" if is_root else ("└── " if is_last else "├── ")
            if node.is_terminal:
                node_str = f"[{node.leaf_index}] {node.label}"
            else:
                rule_suffix = f" ({node.rule})" if node.rule else ""
                node_str = f"{node.label}{rule_suffix}"
            lines.append(f"{prefix}{connector}{node_str}")
            child_prefix = prefix if is_root else prefix + ("    " if is_last else "│   ")
            for idx, child in enumerate(node.children):
                _render(child, child_prefix, idx == len(node.children) - 1, False)

        _render(self, "", True, True)
        lines.append("")
        lines.append(f"Left-to-right leaf traversal: {self.numbered_leaves_text()}")
        return "\n".join(lines)

    def to_dot(self) -> str:
        lines = [
            "digraph SIPLParseTree {",
            '  rankdir=TB;',
            '  node [fontname="Arial"];',
        ]

        def _walk(node: ParseTreeNode) -> None:
            escaped_label = node.label.replace('"', '\\"')
            if node.is_terminal:
                lbl = f"{node.leaf_index}: {escaped_label}"
                lines.append(
                    f'  n{node.node_id} [label="{lbl}", shape=box, style="rounded,filled", fillcolor="#FFF8E7", color="#D97706"];'
                )
            else:
                lines.append(
                    f'  n{node.node_id} [label="{escaped_label}", shape=ellipse, style="filled", fillcolor="#EFF6FF", color="#2563EB"];'
                )
            for child in node.children:
                _walk(child)
                lines.append(f"  n{node.node_id} -> n{child.node_id};")

        _walk(self)
        lines.append("}")
        return "\n".join(lines)

    def to_svg(self) -> str:
        positions: dict[int, tuple[float, float]] = {}
        x_Step = 90.0
        y_step = 75.0
        margin_x = 60.0
        margin_y = 50.0
        current_leaf_slot = 0
        max_depth = 0

        def _layout(node: ParseTreeNode, depth: int) -> float:
            nonlocal current_leaf_slot, max_depth
            max_depth = max(max_depth, depth)
            y = margin_y + depth * y_step
            if not node.children:
                x = margin_x + current_leaf_slot * x_Step
                current_leaf_slot += 1
                positions[node.node_id] = (x, y)
                return x
            child_xs = [_layout(child, depth + 1) for child in node.children]
            x = (child_xs[0] + child_xs[-1]) / 2.0
            positions[node.node_id] = (x, y)
            return x

        _layout(self, 0)
        width = int(max(400.0, margin_x * 2 + max(1, current_leaf_slot - 1) * x_Step + 60.0))
        height = int(margin_y * 2 + (max_depth + 1) * y_step)

        svg_lines = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            "  <style>",
            '    .nt-box { fill: #EFF6FF; stroke: #2563EB; stroke-width: 1.5; }',
            '    .t-box { fill: #FEF3C7; stroke: #D97706; stroke-width: 1.5; }',
            '    .edge { stroke: #475569; stroke-width: 1.5; }',
            '    .lbl { font-family: Arial, sans-serif; font-size: 12px; fill: #0F172A; text-anchor: middle; dominant-baseline: middle; }',
            '    .leaf-num { font-family: Arial, sans-serif; font-size: 11px; font-weight: bold; fill: #DC2626; }',
            "  </style>",
            f'  <rect width="{width}" height="{height}" fill="#FFFFFF"/>',
        ]

        def _draw_edges(node: ParseTreeNode) -> None:
            x1, y1 = positions[node.node_id]
            for child in node.children:
                x2, y2 = positions[child.node_id]
                svg_lines.append(
                    f'  <line class="edge" x1="{x1:.1f}" y1="{y1 + 14:.1f}" x2="{x2:.1f}" y2="{y2 - 14:.1f}"/>'
                )
                _draw_edges(child)

        def _draw_nodes(node: ParseTreeNode) -> None:
            x, y = positions[node.node_id]
            text = escape(node.label)
            box_w = max(54.0, len(node.label) * 7.5 + 16.0)
            box_h = 28.0
            if node.is_terminal:
                svg_lines.append(
                    f'  <rect class="t-box" x="{x - box_w / 2:.1f}" y="{y - box_h / 2:.1f}" width="{box_w:.1f}" height="{box_h:.1f}" rx="4"/>'
                )
                svg_lines.append(
                    f'  <text class="leaf-num" x="{x - box_w / 2 - 6:.1f}" y="{y - 4:.1f}" text-anchor="end">{node.leaf_index}</text>'
                )
            else:
                svg_lines.append(
                    f'  <rect class="nt-box" x="{x - box_w / 2:.1f}" y="{y - box_h / 2:.1f}" width="{box_w:.1f}" height="{box_h:.1f}" rx="12"/>'
                )
            svg_lines.append(f'  <text class="lbl" x="{x:.1f}" y="{y:.1f}">{text}</text>')
            for child in node.children:
                _draw_nodes(child)

        _draw_edges(self)
        _draw_nodes(self)
        svg_lines.append("</svg>")
        return "\n".join(svg_lines)


class _ParseTreeBuilder:
    def __init__(self, source: str | None = None) -> None:
        self.source = source
        self._next_id = 1
        self._next_leaf = 1

    def _alloc_id(self) -> int:
        nid = self._next_id
        self._next_id += 1
        return nid

    def _snippet(self, span: SourceSpan | None) -> str | None:
        if not self.source or not span:
            return None
        start = span.start.offset
        end = span.end.offset
        if 0 <= start <= end <= len(self.source):
            return self.source[start:end]
        return None

    def _term(self, label: str, span: SourceSpan | None = None) -> ParseTreeNode:
        idx = self._next_leaf
        self._next_leaf += 1
        return ParseTreeNode(
            node_id=self._alloc_id(),
            label=label,
            kind="terminal",
            span=span,
            source_fragment=label,
            leaf_index=idx,
        )

    def _nonterm(
        self,
        label: str,
        rule: str,
        children: list[ParseTreeNode],
        span: SourceSpan | None = None,
    ) -> ParseTreeNode:
        return ParseTreeNode(
            node_id=self._alloc_id(),
            label=label,
            kind="nonterminal",
            rule=rule,
            span=span,
            source_fragment=self._snippet(span),
            children=children,
        )

    def build_program(self, prog: Program) -> ParseTreeNode:
        nid = self._alloc_id()
        t_begin = self._term("begin")
        s_node = self.build_stm(prog.body)
        t_end = self._term("end")
        return ParseTreeNode(
            node_id=nid,
            label="<program>",
            kind="nonterminal",
            rule="NP1",
            span=prog.span,
            source_fragment=self._snippet(prog.span),
            children=[t_begin, s_node, t_end],
        )

    def build_stm(self, stm: Stm) -> ParseTreeNode:
        nid = self._alloc_id()
        if isinstance(stm, Assign):
            var_nt = self.build_var(stm.var)
            t_assign = self._term(":=")
            expr_nt = self.build_aexp(stm.expr)
            children = [var_nt, t_assign, expr_nt]
            rule = "NS1"
        elif isinstance(stm, Seq):
            s1 = self.build_stm(stm.first)
            t_semi = self._term(";")
            s2 = self.build_stm(stm.second)
            children = [s1, t_semi, s2]
            rule = "NS2"
        elif isinstance(stm, If):
            t_if = self._term("if")
            b_nt = self.build_bexp(stm.cond)
            t_then = self._term("then")
            s1 = self.build_stm(stm.then_branch)
            t_else = self._term("else")
            s2 = self.build_stm(stm.else_branch)
            children = [t_if, b_nt, t_then, s1, t_else, s2]
            rule = "NS3"
        elif isinstance(stm, While):
            t_while = self._term("while")
            b_nt = self.build_bexp(stm.cond)
            t_do = self._term("do")
            body_nt = self.build_stm(stm.body)
            children = [t_while, b_nt, t_do, body_nt]
            rule = "NS4"
        elif isinstance(stm, Block):
            t_begin = self._term("begin")
            body_nt = self.build_stm(stm.body)
            t_end = self._term("end")
            children = [t_begin, body_nt, t_end]
            rule = "NS5"
        elif isinstance(stm, Skip):
            children = [self._term("skip", stm.span)]
            rule = "NS6"
        else:
            raise TypeError(f"Unsupported Stm: {type(stm)!r}")

        return ParseTreeNode(
            node_id=nid,
            label="<statement>",
            kind="nonterminal",
            rule=rule,
            span=stm.span,
            source_fragment=self._snippet(stm.span),
            children=children,
        )

    def build_bexp(self, cond: Bexp) -> ParseTreeNode:
        nid = self._alloc_id()
        if isinstance(cond, CmpOp):
            left_nt = self.build_aexp(cond.left)
            t_op = self._term(cond.op)
            right_nt = self.build_aexp(cond.right)
            children = [left_nt, t_op, right_nt]
            rule = "NB1" if cond.op == "=" else "NB2"
        elif isinstance(cond, OrOp):
            left_b = self.build_bexp(cond.left)
            t_or = self._term("∨")
            right_b = self.build_bexp(cond.right)
            children = [left_b, t_or, right_b]
            rule = "NB3"
        elif isinstance(cond, NotOp):
            t_not = self._term("¬")
            op_b = self.build_bexp(cond.operand)
            children = [t_not, op_b]
            rule = "NB4"
        elif isinstance(cond, ParenBexp):
            t_lp = self._term("(")
            inner = self.build_bexp(cond.cond)
            t_rp = self._term(")")
            children = [t_lp, inner, t_rp]
            rule = "NB5"
        else:
            raise TypeError(f"Unsupported Bexp: {type(cond)!r}")

        return ParseTreeNode(
            node_id=nid,
            label="<condition>",
            kind="nonterminal",
            rule=rule,
            span=cond.span,
            source_fragment=self._snippet(cond.span),
            children=children,
        )

    def build_aexp(self, expr: Aexp) -> ParseTreeNode:
        nid = self._alloc_id()
        if isinstance(expr, Num):
            children = [self.build_num(expr)]
            rule = "NA1"
        elif isinstance(expr, Var):
            children = [self.build_var(expr)]
            rule = "NA2"
        elif isinstance(expr, BinOp):
            left_a = self.build_aexp(expr.left)
            t_op = self._term(expr.op)
            right_a = self.build_aexp(expr.right)
            children = [left_a, t_op, right_a]
            if expr.op == "+":
                rule = "NA3"
            elif expr.op == "-":
                rule = "NA4"
            else:
                rule = "NA5"
        elif isinstance(expr, ParenAexp):
            t_lp = self._term("(")
            inner = self.build_aexp(expr.expr)
            t_rp = self._term(")")
            children = [t_lp, inner, t_rp]
            rule = "NA6"
        else:
            raise TypeError(f"Unsupported Aexp: {type(expr)!r}")

        return ParseTreeNode(
            node_id=nid,
            label="<expression>",
            kind="nonterminal",
            rule=rule,
            span=expr.span,
            source_fragment=self._snippet(expr.span),
            children=children,
        )

    def build_var(self, var: Var) -> ParseTreeNode:
        nid = self._alloc_id()
        leaf = self._term(var.name, var.span)
        return ParseTreeNode(
            node_id=nid,
            label="<variable>",
            kind="nonterminal",
            rule="NV",
            span=var.span,
            source_fragment=var.name,
            children=[leaf],
        )

    def build_num(self, num: Num) -> ParseTreeNode:
        nid = self._alloc_id()
        leaf = self._term(str(num.value), num.span)
        return ParseTreeNode(
            node_id=nid,
            label="<number>",
            kind="nonterminal",
            rule="NN",
            span=num.span,
            source_fragment=str(num.value),
            children=[leaf],
        )


def build_parse_tree(program: Program | str) -> ParseTreeNode:
    if isinstance(program, str):
        ast_prog = parse_program(program)
        builder = _ParseTreeBuilder(source=program)
    else:
        ast_prog = program
        builder = _ParseTreeBuilder(source=None)
    return builder.build_program(ast_prog)