"""초안 검증·변환과 문서 렌더."""

import datetime as dt
import unittest

from engine.approval import document, line, render, schema, seal


def _template():
    return schema.parse(
        {
            "code": "T",
            "name": "출장명령서",
            "fields": [
                {"key": "purpose", "label": "출장목적", "type": "text", "required": True},
                {"key": "date_from", "label": "출발일", "type": "date", "required": True},
                {"key": "budget", "label": "예상경비", "type": "money", "required": True},
                {
                    "key": "transport",
                    "label": "교통편",
                    "type": "select",
                    "options": ["자가용", "항공"],
                },
                {"key": "companions", "label": "동행자", "type": "user_list"},
                {"key": "detail", "label": "세부일정", "type": "textarea"},
            ],
            "approval_line": {
                "default": ["팀장", "부서장"],
                "rules": [{"when": "budget > 1000000", "line": ["팀장", "재무팀장", "대표"]}],
            },
        }
    )


_GOOD = {
    "purpose": "협력사 감사",
    "date_from": "2026-09-10",
    "budget": "2000000",
    "transport": "항공",
    "companions": "홍길동, 김철수",
    "detail": "1일차 이동\n2일차 감사",
}


class Validate(unittest.TestCase):
    def test_clean_draft_has_no_problems(self):
        self.assertEqual(document.validate(_template(), dict(_GOOD)), [])

    def test_missing_required_field_is_reported(self):
        values = dict(_GOOD, purpose="   ")
        problems = document.validate(_template(), values)
        self.assertTrue(any("출장목적" in p for p in problems))

    def test_all_problems_are_collected_at_once(self):
        # 하나씩 터뜨리면 고치고 다시 돌리기를 반복하게 된다.
        problems = document.validate(_template(), {})
        self.assertEqual(len(problems), 3)  # purpose, date_from, budget

    def test_select_value_outside_options(self):
        problems = document.validate(_template(), dict(_GOOD, transport="우주선"))
        self.assertTrue(any("우주선" in p for p in problems))

    def test_bad_date(self):
        problems = document.validate(_template(), dict(_GOOD, date_from="9월 10일"))
        self.assertTrue(any("출발일" in p for p in problems))

    def test_non_numeric_money(self):
        problems = document.validate(_template(), dict(_GOOD, budget="이백만원"))
        self.assertTrue(any("예상경비" in p for p in problems))

    def test_unknown_key_is_flagged_as_possible_typo(self):
        problems = document.validate(_template(), dict(_GOOD, purpse="오타"))
        self.assertTrue(any("purpse" in p for p in problems))


class Coerce(unittest.TestCase):
    def test_money_string_becomes_number_so_the_rule_compares_correctly(self):
        # "2000000" > 1000000 을 문자열로 비교하면 결재선이 틀린다.
        template = _template()
        values = document.coerce(template, dict(_GOOD))
        self.assertEqual(values["budget"], 2000000.0)
        self.assertEqual(line.resolve(template, values), ("팀장", "재무팀장", "대표"))

    def test_below_threshold_uses_default_line(self):
        template = _template()
        values = document.coerce(template, dict(_GOOD, budget="500000"))
        self.assertEqual(line.resolve(template, values), ("팀장", "부서장"))

    def test_user_list_splits_on_comma(self):
        values = document.coerce(_template(), dict(_GOOD))
        self.assertEqual(values["companions"], ["홍길동", "김철수"])

    def test_date_becomes_date_object(self):
        values = document.coerce(_template(), dict(_GOOD))
        self.assertEqual(values["date_from"], dt.date(2026, 9, 10))

    def test_blank_becomes_none(self):
        values = document.coerce(_template(), dict(_GOOD, detail=""))
        self.assertIsNone(values["detail"])


class Skeleton(unittest.TestCase):
    def test_skeleton_round_trips_through_yaml(self):
        import yaml

        template = _template()
        data = yaml.safe_load(document.skeleton(template, dt.date(2026, 9, 3)))

        self.assertEqual(data["form"], "T")
        self.assertEqual(data["drafted_on"], dt.date(2026, 9, 3))
        self.assertEqual(sorted(data["values"]), sorted(f.key for f in template.fields))

    def test_skeleton_mentions_select_options(self):
        self.assertIn("자가용/항공", document.skeleton(_template()))


class Format(unittest.TestCase):
    def setUp(self):
        self.template = _template()

    def _fmt(self, key, value):
        return render.format_value(self.template.field(key), value)

    def test_money_gets_thousand_separators(self):
        self.assertEqual(self._fmt("budget", 2000000), "2,000,000 원")

    def test_user_list_joins(self):
        self.assertEqual(self._fmt("companions", ["가", "나"]), "가, 나")

    def test_blank_stays_blank_not_none(self):
        self.assertEqual(self._fmt("purpose", None), "")
        self.assertEqual(self._fmt("companions", []), "")

    def test_date_is_isoformat(self):
        self.assertEqual(self._fmt("date_from", dt.date(2026, 9, 10)), "2026-09-10")


class RenderHtml(unittest.TestCase):
    def setUp(self):
        self.template = _template()
        self.values = document.coerce(self.template, dict(_GOOD))

    def _html(self, **meta_kwargs):
        meta = render.DocumentMeta(
            title="협력사 정기감사 출장",
            drafter="홍길동",
            department="품질팀",
            drafted_on=dt.date(2026, 9, 3),
            approvers=tuple(
                render.Approver(p) for p in line.resolve(self.template, self.values)
            ),
            **meta_kwargs,
        )
        return render.render_html(self.template, self.values, meta)

    def test_contains_form_name_and_fields(self):
        html = self._html()
        self.assertIn("출장명령서", html)
        self.assertIn("협력사 감사", html)
        self.assertIn("2,000,000 원", html)

    def test_approval_columns_include_drafter_first(self):
        html = self._html()
        head = html[: html.index("</table>")]
        self.assertLess(head.index("담당"), head.index("팀장"))
        self.assertIn("재무팀장", head)

    def test_drafter_box_is_stamped(self):
        # '담당' 칸은 결재가 아니라 '작성했음'을 뜻한다. 기안자가 날인하는 것이 관례다.
        self.assertIn('aria-label="홍길동 도장"', self._html())

    def test_approver_boxes_stay_empty_until_approved(self):
        # 승인하지도 않은 결재자 칸에 도장이 찍히면 승인된 문서처럼 보인다. 절대 안 된다.
        # 기안자 것 하나만 있어야 한다.
        self.assertEqual(self._html().count("<svg"), 1)

    def test_no_seal_at_all_when_drafter_is_unknown(self):
        meta = render.DocumentMeta(title="t", drafted_on=dt.date(2026, 9, 3))
        self.assertNotIn("<svg", render.render_html(self.template, self.values, meta))

    def test_seal_appears_once_approved(self):
        meta = render.DocumentMeta(
            title="t",
            drafter="홍길동",
            drafted_on=dt.date(2026, 9, 3),
            approvers=(render.Approver("팀장", "김철수", dt.date(2026, 9, 4)),),
        )
        html = render.render_html(self.template, self.values, meta)
        self.assertIn("<svg", html)
        self.assertIn("09/04", html)

    def test_html_is_escaped(self):
        values = dict(self.values, purpose="<script>alert(1)</script>")
        meta = render.DocumentMeta(title="t", drafted_on=dt.date(2026, 9, 3))
        html = render.render_html(self.template, values, meta)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_print_rules_are_present(self):
        # 화면과 인쇄가 같은 HTML에서 나온다는 것이 이 설계의 전제다.
        html = self._html()
        self.assertIn("@page", html)
        self.assertIn("size: A4", html)
        self.assertIn("@media print", html)


class RenderText(unittest.TestCase):
    def test_paste_text_has_fields_and_line(self):
        template = _template()
        values = document.coerce(template, dict(_GOOD))
        meta = render.DocumentMeta(
            title="협력사 정기감사 출장",
            drafter="홍길동",
            drafted_on=dt.date(2026, 9, 3),
            approvers=tuple(render.Approver(p) for p in line.resolve(template, values)),
        )
        text = render.render_text(template, values, meta)

        self.assertIn("[출장명령서] 협력사 정기감사 출장", text)
        self.assertIn("결재선: 팀장 → 재무팀장 → 대표", text)
        self.assertIn("■ 출장목적: 협력사 감사", text)
        self.assertIn("■ 세부일정", text)
        self.assertIn("   1일차 이동", text)

    def test_blank_fields_are_omitted(self):
        template = _template()
        values = document.coerce(template, dict(_GOOD, companions=""))
        meta = render.DocumentMeta(title="t", drafted_on=dt.date(2026, 9, 3))
        self.assertNotIn("동행자", render.render_text(template, values, meta))


class Seal(unittest.TestCase):
    def test_three_character_name(self):
        svg = seal.seal_svg("홍길동")
        self.assertIn("<svg", svg)
        self.assertIn("홍길동", svg)

    def test_four_character_name_uses_grid(self):
        svg = seal.seal_svg("남궁길동")
        self.assertEqual(svg.count("<text"), 4)

    def test_blank_name_gives_nothing(self):
        self.assertEqual(seal.seal_svg("  "), "")

    def test_name_is_xml_escaped(self):
        self.assertNotIn("<b>", seal.seal_svg("<b>"))


class Particle(unittest.TestCase):
    def test_final_consonant_takes_eun(self):
        self.assertEqual(document.particle("출장목적", "은", "는"), "은")

    def test_no_final_consonant_takes_neun(self):
        self.assertEqual(document.particle("예상경비", "은", "는"), "는")

    def test_non_hangul_falls_back(self):
        self.assertEqual(document.particle("budget", "은", "는"), "는")
        self.assertEqual(document.particle("", "은", "는"), "는")

    def test_messages_read_correctly(self):
        problems = document.validate(_template(), {})
        self.assertIn("출장목적은 필수입니다.", problems)
        self.assertIn("예상경비는 필수입니다.", problems)


class Slugify(unittest.TestCase):
    def test_korean_survives(self):
        self.assertEqual(document.slugify("협력사 정기감사", "x"), "협력사_정기감사")

    def test_path_separators_are_removed(self):
        self.assertNotIn("/", document.slugify("a/b", "x"))

    def test_empty_falls_back(self):
        self.assertEqual(document.slugify("", "출장명령서"), "출장명령서")


if __name__ == "__main__":
    unittest.main()
