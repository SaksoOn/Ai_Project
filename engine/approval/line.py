"""결재선 규칙을 평가한다.

금액에 따라 결재선이 갈리는 것은 한국 기업의 표준 패턴이다.

    100만원 이하 → 팀장 → 부서장 → 대표
    100만원 초과 → 팀장 → 부서장 → 재무팀장 → 대표

이걸 코드로 짜면 전결 규정이 바뀔 때마다 배포해야 한다. 양식 YAML의 조건식으로 둔다.
기성 그룹웨어가 정확히 못 맞추는 지점이 여기고, 자체 구축을 정당화하는 근거다.

**`eval()`을 쓰지 않는 이유.** 양식 파일은 결국 관리자가 편집하게 될 물건이고,
조건식은 그 시점부터 사용자 입력이다. `ast`로 파싱해 허용한 노드만 통과시킨다.
함수 호출·속성 접근·첨자는 문법 단계에서 막힌다.

**모르는 필드명에 예외를 던지는 이유.** 오타가 나면 조건이 조용히 거짓이 되고
기본 결재선으로 떨어진다. 금액이 큰데 재무팀장이 빠진 문서가 그대로 올라가면
규정 위반이고, 아무도 눈치채지 못한다. 시끄럽게 죽는 편이 낫다.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from typing import Any


class ConditionError(ValueError):
    """조건식이 해석 불가하거나, 평가에 필요한 값이 없다."""


# 허용 노드. 여기 없는 것은 전부 거부한다 — 특히 Call/Attribute/Subscript.
_ALLOWED_NODES = (
    ast.Expression,
    ast.BoolOp, ast.And, ast.Or,
    ast.UnaryOp, ast.Not, ast.USub, ast.UAdd,
    ast.Compare, ast.Gt, ast.GtE, ast.Lt, ast.LtE, ast.Eq, ast.NotEq, ast.In, ast.NotIn,
    ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod,
    ast.Name, ast.Load, ast.Constant,
    ast.Tuple, ast.List,  # "transport in [항공, 철도]" 같은 표현을 위해
)


def compile_condition(expr: str) -> ast.Expression:
    """조건식을 파싱하고 안전성을 검사한다. 양식을 읽는 시점에 부른다.

    문서를 만들 때가 아니라 양식을 로드할 때 검증해야 오타를 일찍 잡는다.
    """
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise ConditionError(f"조건식을 해석할 수 없습니다: {expr!r} — {exc.msg}") from exc

    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ConditionError(
                f"조건식에 허용되지 않은 표현이 있습니다: {expr!r} "
                f"({type(node).__name__}). 비교·논리 연산과 사칙연산만 쓸 수 있습니다."
            )
    return tree


def condition_names(tree: ast.Expression) -> set[str]:
    """조건식이 참조하는 필드명. 양식 검증에서 '없는 필드' 오타를 잡는 데 쓴다."""
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}


def evaluate(tree: ast.Expression, values: Mapping[str, Any]) -> bool:
    """조건식을 평가한다. 참조된 값이 없으면 예외."""
    return bool(_eval(tree.body, values))


def _eval(node: ast.AST, values: Mapping[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name):
        if node.id not in values:
            raise ConditionError(
                f"조건식이 참조한 '{node.id}' 값이 없습니다. 양식의 필드명과 다를 수 있습니다."
            )
        return values[node.id]

    if isinstance(node, (ast.Tuple, ast.List)):
        return [_eval(e, values) for e in node.elts]

    if isinstance(node, ast.UnaryOp):
        operand = _eval(node.operand, values)
        if isinstance(node.op, ast.Not):
            return not operand
        if isinstance(node.op, ast.USub):
            return -operand
        return +operand

    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            return all(_eval(v, values) for v in node.values)
        return any(_eval(v, values) for v in node.values)

    if isinstance(node, ast.BinOp):
        left, right = _eval(node.left, values), _eval(node.right, values)
        return _BINOPS[type(node.op)](left, right)

    if isinstance(node, ast.Compare):
        left = _eval(node.left, values)
        for op, right_node in zip(node.ops, node.comparators):
            right = _eval(right_node, values)
            if not _COMPARES[type(op)](left, right):
                return False
            left = right  # 1 < x < 10 같은 연쇄 비교
        return True

    raise ConditionError(f"평가할 수 없는 표현입니다: {type(node).__name__}")


_BINOPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
}

_COMPARES = {
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}


def resolve(template, values: Mapping[str, Any]) -> tuple[str, ...]:
    """양식과 입력값으로 실제 결재선을 정한다.

    **먼저 맞는 규칙이 이긴다.** 규칙을 좁은 것부터 쓰면 된다는 뜻이고,
    순서가 의미를 가지므로 양식 파일에서 순서를 바꾸면 결과가 바뀐다.
    '가장 구체적인 규칙'을 자동으로 고르는 방식은 무엇이 더 구체적인지를
    기계가 판단해야 해서, 규정을 읽는 사람이 결과를 예측할 수 없다.
    """
    for rule in template.rules:
        if evaluate(rule.condition, values):
            return rule.line
    return template.default_line
