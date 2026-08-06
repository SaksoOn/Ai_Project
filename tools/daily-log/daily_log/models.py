"""자료 구조.

Outlook에 의존하지 않는다. 그래야 Windows 없이도 로직 전체를 테스트할 수 있다.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass, field

MAIL_RECEIVED = "메일수신"
MAIL_SENT = "메일발신"
CALENDAR = "일정"


@dataclass(frozen=True)
class RawItem:
    """Outlook에서 막 꺼낸 항목. 아직 걸러지지 않았다."""

    at: dt.datetime
    kind: str
    subject: str
    sender: str = ""
    to: tuple[str, ...] = ()
    cc: tuple[str, ...] = ()
    entry_id: str = ""

    @property
    def key(self) -> str:
        """행을 다시 만나도 같은 것으로 알아보게 하는 식별자.

        Outlook의 EntryID가 있으면 그걸 쓰고, 없으면(일정 등) 내용으로 해시한다.
        학습과 중복 제거가 이 키에 걸려 있다.
        """
        if self.entry_id:
            return self.entry_id
        seed = f"{self.at.isoformat()}|{self.kind}|{self.sender}|{self.subject}"
        return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]


@dataclass
class QueueItem:
    """대기열에 올라간 항목. 사용자가 지우면 업무가 아닌 것으로 학습된다."""

    key: str
    at: dt.datetime
    kind: str
    counterpart: str
    subject: str
    reason: str
    hint: str = ""

    @property
    def date(self) -> dt.date:
        return self.at.date()


@dataclass
class DecisionLog:
    """대기열에서 무엇이 남고 무엇이 지워졌는지.

    이게 학습 데이터다. 지운 것을 기억해야 다음번 대기열이 깨끗해진다.
    """

    kept: list[QueueItem] = field(default_factory=list)
    dropped: list[QueueItem] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.kept) + len(self.dropped)
