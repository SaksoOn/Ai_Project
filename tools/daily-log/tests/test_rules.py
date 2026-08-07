import datetime as dt
import unittest

from daily_log.models import CALENDAR, MAIL_RECEIVED, MAIL_SENT, RawItem
from daily_log.rules import (
    ExclusionConfig,
    InclusionConfig,
    LearnedStats,
    auto_excluded,
    build_queue,
    include_reason,
)

ME = "me@company.com"
DEPT = "team@company.com"

CONFIG = InclusionConfig(
    my_addresses=(ME,),
    department_addresses=(DEPT,),
)


def mail(kind=MAIL_RECEIVED, *, sender="other@x.com", to=(), cc=(), subject="제목", minute=0):
    return RawItem(
        at=dt.datetime(2026, 8, 6, 9, minute),
        kind=kind,
        subject=subject,
        sender=sender,
        to=tuple(to),
        cc=tuple(cc),
    )


class 포함규칙(unittest.TestCase):
    def test_내가_보낸_메일은_포함한다(self):
        item = mail(MAIL_SENT, sender=ME, to=("client@x.com",))
        self.assertEqual(include_reason(item, CONFIG), "내가 보낸 메일")

    def test_내가_To인_메일은_포함한다(self):
        self.assertEqual(include_reason(mail(to=(ME,)), CONFIG), "내가 수신(To)")

    def test_부서로_온_메일은_포함한다(self):
        self.assertEqual(include_reason(mail(to=(DEPT,)), CONFIG), "부서 수신")

    def test_부서가_참조여도_포함한다(self):
        self.assertEqual(include_reason(mail(to=("x@y.com",), cc=(DEPT,)), CONFIG), "부서 수신")

    def test_나만_참조된_메일은_기본적으로_뺀다(self):
        # 참조는 대개 "알아두라"는 뜻이지 내 업무가 아니다.
        self.assertIsNone(include_reason(mail(cc=(ME,)), CONFIG))

    def test_참조_포함을_켜면_들어온다(self):
        config = InclusionConfig(my_addresses=(ME,), include_cc=True)
        self.assertEqual(include_reason(mail(cc=(ME,)), config), "내가 참조(CC)")

    def test_나와_무관한_메일은_뺀다(self):
        self.assertIsNone(include_reason(mail(to=("stranger@x.com",)), CONFIG))

    def test_일정은_포함한다(self):
        self.assertEqual(include_reason(mail(CALENDAR, subject="주간회의"), CONFIG), "일정")

    def test_주소_대소문자와_공백을_무시한다(self):
        item = mail(to=("  ME@Company.COM ",))
        self.assertEqual(include_reason(item, CONFIG), "내가 수신(To)")

    def test_끄면_안_들어온다(self):
        config = InclusionConfig(
            my_addresses=(ME,), include_sent=False, include_calendar=False
        )
        self.assertIsNone(include_reason(mail(MAIL_SENT, sender=ME), config))
        self.assertIsNone(include_reason(mail(CALENDAR), config))


class 대기열_구성(unittest.TestCase):
    def test_시간순으로_정렬한다(self):
        items = [
            mail(to=(ME,), subject="늦은 것", minute=30),
            mail(to=(ME,), subject="이른 것", minute=5),
        ]
        queue, _ = build_queue(items, CONFIG)
        self.assertEqual([q.subject for q in queue], ["이른 것", "늦은 것"])

    def test_같은_항목이_두_번_잡혀도_한_번만_올린다(self):
        # 같은 메일이 받은편지함과 하위 폴더에 동시에 걸리는 일이 흔하다.
        item = mail(to=(ME,), subject="중복")
        queue, _ = build_queue([item, item], CONFIG)
        self.assertEqual(len(queue), 1)

    def test_부서_사서함이_여러_개여도_한_번만_올린다(self):
        # 부서 주소를 두 개 넣으면 같은 메일이 사서함마다 다른 EntryID로 올라온다.
        # EntryID 비교만으로는 못 거른다 — 실제로 AWS 알림이 두 줄로 찍혔다.
        common = dict(
            at=dt.datetime(2026, 8, 6, 20, 48),
            kind=MAIL_RECEIVED,
            subject="RE:[CASE 000000000000000] 승인 요청 건",
            sender="no-reply@example.com",
            to=(DEPT,),
        )
        items = [
            RawItem(**common, entry_id="ENTRYID-A"),
            RawItem(**common, entry_id="ENTRYID-B"),
        ]
        queue, _ = build_queue(items, CONFIG)
        self.assertEqual(len(queue), 1)

    def test_제목이_다르면_같은_분이어도_둘_다_올린다(self):
        # 위 중복 제거가 과하게 먹으면 진짜 업무가 사라진다. 경계를 박아둔다.
        items = [
            mail(to=(ME,), subject="첫 번째"),
            mail(to=(ME,), subject="두 번째"),
        ]
        queue, _ = build_queue(items, CONFIG)
        self.assertEqual(len(queue), 2)

    def test_받은_메일은_발신자를_상대로_잡는다(self):
        queue, _ = build_queue([mail(sender="boss@x.com", to=(ME,))], CONFIG)
        self.assertEqual(queue[0].counterpart, "boss@x.com")

    def test_보낸_메일은_수신자를_상대로_잡는다(self):
        item = mail(MAIL_SENT, sender=ME, to=("a@x.com", "b@x.com"))
        queue, _ = build_queue([item], CONFIG)
        self.assertEqual(queue[0].counterpart, "a@x.com, b@x.com")

    def test_포함_사유를_남긴다(self):
        # "이게 왜 여기 있지?"를 바로 알아야 지울지 판단이 빨라진다.
        queue, _ = build_queue([mail(to=(DEPT,))], CONFIG)
        self.assertEqual(queue[0].reason, "부서 수신")


class 학습(unittest.TestCase):
    def _stats(self, counterpart, seen, dropped):
        stats = LearnedStats()
        for i in range(seen):
            stats.observe(counterpart, was_dropped=i < dropped)
        return stats

    def test_항상_지운_상대는_자동_제외한다(self):
        stats = self._stats("noreply@spam.com", seen=5, dropped=5)
        self.assertTrue(auto_excluded("noreply@spam.com", stats, ExclusionConfig()))

    def test_관측이_모자라면_아직_제외하지_않는다(self):
        stats = self._stats("noreply@spam.com", seen=4, dropped=4)
        self.assertFalse(auto_excluded("noreply@spam.com", stats, ExclusionConfig()))

    def test_한_번이라도_남긴_적이_있으면_제외하지_않는다(self):
        # 잘못 제외하면 사용자가 그 사실조차 모른다. 없는 걸 알아채기는 어렵다.
        stats = self._stats("mixed@x.com", seen=10, dropped=9)
        self.assertFalse(auto_excluded("mixed@x.com", stats, ExclusionConfig()))

    def test_자동_제외된_것도_따로_돌려준다(self):
        # 조용히 사라지면 도구를 신뢰할 수 없다.
        stats = self._stats("noreply@spam.com", seen=5, dropped=5)
        items = [
            mail(sender="noreply@spam.com", to=(ME,), subject="광고"),
            mail(sender="boss@x.com", to=(ME,), subject="진짜 업무", minute=10),
        ]
        queue, excluded = build_queue(items, CONFIG, stats)
        self.assertEqual([q.subject for q in queue], ["진짜 업무"])
        self.assertEqual([e.subject for e in excluded], ["광고"])
        self.assertIn("100%", excluded[0].hint)

    def test_저장하고_불러와도_통계가_유지된다(self):
        stats = self._stats("a@x.com", seen=3, dropped=2)
        restored = LearnedStats.from_dict(stats.to_dict())
        self.assertAlmostEqual(restored.drop_rate("a@x.com"), 2 / 3)

    def test_빈_상대는_집계하지_않는다(self):
        stats = LearnedStats()
        stats.observe("", was_dropped=True)
        self.assertEqual(stats.seen, {})


if __name__ == "__main__":
    unittest.main()
