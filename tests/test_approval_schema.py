"""양식 정의 검증.

양식이 깨졌다는 사실은 문서와 무관하게 항상 참이다. 값을 다 채운 뒤에 알게 되면
늦으므로 로드 시점에 전부 잡아야 한다.
"""

import unittest

from engine.approval import schema


def _form(**overrides):
    data = {
        "code": "T",
        "name": "테스트",
        "fields": [
            {"key": "amount", "label": "금액", "type": "money", "required": True},
            {"key": "memo", "label": "메모", "type": "textarea"},
        ],
        "approval_line": {"default": ["팀장", "부서장"]},
    }
    data.update(overrides)
    return data


class Parse(unittest.TestCase):
    def test_minimal_form(self):
        template = schema.parse(_form())
        self.assertEqual(template.code, "T")
        self.assertEqual(template.version, 1)
        self.assertEqual(len(template.fields), 2)
        self.assertEqual(template.default_line, ("팀장", "부서장"))

    def test_field_lookup(self):
        template = schema.parse(_form())
        self.assertEqual(template.field("amount").label, "금액")
        self.assertIsNone(template.field("nope"))

    def test_textarea_is_full_width(self):
        template = schema.parse(_form())
        self.assertTrue(template.field("memo").full_width)
        self.assertFalse(template.field("amount").full_width)


class Rejects(unittest.TestCase):
    def _assert_rejected(self, data, needle=""):
        with self.assertRaises(schema.FormError) as ctx:
            schema.parse(data)
        if needle:
            self.assertIn(needle, str(ctx.exception))

    def test_missing_code(self):
        data = _form()
        del data["code"]
        self._assert_rejected(data, "code")

    def test_duplicate_field_key(self):
        # 뒤엣것이 앞엣것을 덮어써서 한 칸이 조용히 사라진다.
        self._assert_rejected(
            _form(
                fields=[
                    {"key": "a", "label": "가", "type": "text"},
                    {"key": "a", "label": "나", "type": "text"},
                ]
            ),
            "중복",
        )

    def test_unknown_field_type(self):
        self._assert_rejected(
            _form(fields=[{"key": "a", "label": "가", "type": "슈퍼텍스트"}]),
            "슈퍼텍스트",
        )

    def test_select_without_options(self):
        self._assert_rejected(
            _form(fields=[{"key": "a", "label": "가", "type": "select"}]), "options"
        )

    def test_empty_default_line(self):
        self._assert_rejected(_form(approval_line={"default": []}), "default")

    def test_rule_condition_referencing_unknown_field(self):
        # 여기서 안 잡으면 문서를 만드는 순간에야 터진다.
        self._assert_rejected(
            _form(
                approval_line={
                    "default": ["팀장"],
                    "rules": [{"when": "amout > 100", "line": ["대표"]}],
                }
            ),
            "amout",
        )

    def test_rule_with_unsafe_condition(self):
        self._assert_rejected(
            _form(
                approval_line={
                    "default": ["팀장"],
                    "rules": [{"when": "__import__('os')", "line": ["대표"]}],
                }
            )
        )


class ShippedForms(unittest.TestCase):
    """저장소에 든 양식 4종이 실제로 로드되는가."""

    def setUp(self):
        # forms.local/ 은 사용자 환경마다 달라 테스트에서 제외한다.
        self.templates = schema.load_all(local_dir=schema.FORMS_DIR / "__none__")

    def test_all_four_forms_load(self):
        self.assertEqual(
            sorted(self.templates), ["DRAFT", "PROPOSAL", "REPORT", "TRIP_ORDER"]
        )

    def test_every_form_has_fields_and_a_line(self):
        for template in self.templates.values():
            with self.subTest(form=template.code):
                self.assertTrue(template.fields)
                self.assertTrue(template.default_line)

    def test_find_by_korean_name(self):
        self.assertEqual(schema.find(self.templates, "출장명령서").code, "TRIP_ORDER")

    def test_find_by_code_is_case_insensitive(self):
        self.assertEqual(schema.find(self.templates, "trip_order").code, "TRIP_ORDER")

    def test_find_unknown_lists_what_exists(self):
        with self.assertRaises(schema.FormError) as ctx:
            schema.find(self.templates, "없는양식")
        self.assertIn("출장명령서", str(ctx.exception))


class LocalOverride(unittest.TestCase):
    def test_local_form_replaces_shipped_one(self):
        import pathlib
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            local = pathlib.Path(tmp)
            (local / "trip_order.yaml").write_text(
                "code: TRIP_ORDER\n"
                "name: 출장명령서\n"
                "fields:\n"
                "  - {key: x, label: 엑스, type: text}\n"
                "approval_line: {default: [사장]}\n",
                encoding="utf-8",
            )
            templates = schema.load_all(local_dir=local)

        self.assertEqual(templates["TRIP_ORDER"].default_line, ("사장",))
        self.assertEqual(len(templates["TRIP_ORDER"].fields), 1)
        # 다른 양식은 그대로 남아야 한다.
        self.assertIn("PROPOSAL", templates)


if __name__ == "__main__":
    unittest.main()
