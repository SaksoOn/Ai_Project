"""결재선 규칙.

여기가 틀리면 규정 위반 문서가 조용히 올라간다. 가장 촘촘히 덮는다.
"""

import unittest

from engine.approval import line
from engine.approval.schema import ApprovalRule, Field, FormTemplate


def _template(rules=()):
    return FormTemplate(
        code="T",
        name="테스트",
        version=1,
        fields=(
            Field("amount", "금액", "money"),
            Field("kind", "구분", "select", options=("사고", "변경")),
        ),
        default_line=("팀장", "부서장"),
        rules=tuple(rules),
    )


def _rule(when, line_names):
    return ApprovalRule(when=when, line=tuple(line_names), condition=line.compile_condition(when))


class Evaluate(unittest.TestCase):
    def test_numeric_comparison(self):
        tree = line.compile_condition("amount > 1000000")
        self.assertTrue(line.evaluate(tree, {"amount": 1000001}))
        self.assertFalse(line.evaluate(tree, {"amount": 1000000}))

    def test_membership(self):
        tree = line.compile_condition("kind in ['사고', '손실']")
        self.assertTrue(line.evaluate(tree, {"kind": "사고"}))
        self.assertFalse(line.evaluate(tree, {"kind": "변경"}))

    def test_boolean_combination(self):
        tree = line.compile_condition("amount > 100 and kind == '사고'")
        self.assertTrue(line.evaluate(tree, {"amount": 200, "kind": "사고"}))
        self.assertFalse(line.evaluate(tree, {"amount": 200, "kind": "변경"}))

    def test_chained_comparison(self):
        tree = line.compile_condition("100 < amount < 200")
        self.assertTrue(line.evaluate(tree, {"amount": 150}))
        self.assertFalse(line.evaluate(tree, {"amount": 250}))

    def test_unknown_field_raises_rather_than_silently_false(self):
        # 오타가 조용히 거짓이 되면 기본 결재선으로 떨어져 규정 위반이 된다.
        tree = line.compile_condition("buget > 100")
        with self.assertRaises(line.ConditionError):
            line.evaluate(tree, {"budget": 999})


class Safety(unittest.TestCase):
    def test_function_call_rejected(self):
        with self.assertRaises(line.ConditionError):
            line.compile_condition("__import__('os').system('ls')")

    def test_attribute_access_rejected(self):
        with self.assertRaises(line.ConditionError):
            line.compile_condition("amount.__class__")

    def test_subscript_rejected(self):
        with self.assertRaises(line.ConditionError):
            line.compile_condition("amount[0]")

    def test_syntax_error_is_reported_as_condition_error(self):
        with self.assertRaises(line.ConditionError):
            line.compile_condition("amount >")


class Resolve(unittest.TestCase):
    def test_default_when_no_rule_matches(self):
        template = _template([_rule("amount > 1000000", ["팀장", "재무팀장"])])
        self.assertEqual(line.resolve(template, {"amount": 500}), ("팀장", "부서장"))

    def test_matching_rule_wins(self):
        template = _template([_rule("amount > 1000000", ["팀장", "재무팀장"])])
        self.assertEqual(
            line.resolve(template, {"amount": 2000000}), ("팀장", "재무팀장")
        )

    def test_first_matching_rule_wins(self):
        # 순서가 의미를 가진다. 좁은 조건을 위에 두면 예측 가능해진다.
        template = _template(
            [
                _rule("amount > 10000000", ["대표"]),
                _rule("amount > 1000000", ["재무팀장"]),
            ]
        )
        self.assertEqual(line.resolve(template, {"amount": 50000000}), ("대표",))
        self.assertEqual(line.resolve(template, {"amount": 2000000}), ("재무팀장",))


if __name__ == "__main__":
    unittest.main()
