"""무엇을 대기열에 올릴지 정한다.

두 단계다.

1. **포함 규칙** — 사용자가 정한 기준(내가 보낸 것 / 내가 To인 것 / 부서로 온 것)
2. **학습된 제외** — 지금까지 늘 지워온 것은 애초에 안 올린다

2번이 이 도구의 수명을 결정한다. 매일 30줄에서 20줄을 지워야 한다면 곧 안 쓰게 된다.
쓸수록 대기열이 깨끗해져야 계속 쓴다.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .models import CALENDAR, MAIL_RECEIVED, MAIL_SENT, QueueItem, RawItem


@dataclass
class InclusionConfig:
    my_addresses: tuple[str, ...] = ()
    department_addresses: tuple[str, ...] = ()
    include_sent: bool = True
    include_to: bool = True
    include_cc: bool = False       # 참조는 대개 업무가 아니다. 기본 제외
    include_department: bool = True
    include_calendar: bool = True


def _norm(address: str) -> str:
    return address.strip().lower()


def _matches(addresses: tuple[str, ...], targets: tuple[str, ...]) -> bool:
    normalized = {_norm(a) for a in addresses if a.strip()}
    return any(_norm(t) in normalized for t in targets if t.strip())


def include_reason(item: RawItem, config: InclusionConfig) -> str | None:
    """포함해야 하면 사유 문자열을, 아니면 None을 돌려준다.

    사유를 남기는 이유: 대기열에서 "이게 왜 여기 있지?"를 바로 알 수 있어야
    지울지 말지 판단이 빨라진다.
    """
    if item.kind == CALENDAR:
        return "일정" if config.include_calendar else None

    if item.kind == MAIL_SENT:
        return "내가 보낸 메일" if config.include_sent else None

    if item.kind == MAIL_RECEIVED:
        if config.include_to and _matches(item.to, config.my_addresses):
            return "내가 수신(To)"
        if config.include_department and (
            _matches(item.to, config.department_addresses)
            or _matches(item.cc, config.department_addresses)
        ):
            return "부서 수신"
        if config.include_cc and _matches(item.cc, config.my_addresses):
            return "내가 참조(CC)"
        return None

    return None


# ── 학습 ─────────────────────────────────────────────────────

@dataclass
class ExclusionConfig:
    """자동 제외를 켜는 조건.

    보수적으로 잡는다. 잘못 제외하면 사용자가 그 사실조차 모른다 —
    없는 걸 알아채기는 어렵다. 그래서 '항상 지웠던 것'만 제외한다.
    """

    min_observations: int = 5
    drop_ratio: float = 1.0  # 100% 지웠을 때만


@dataclass
class LearnedStats:
    """상대방별 유지/삭제 집계."""

    seen: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    dropped: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def observe(self, counterpart: str, was_dropped: bool) -> None:
        key = _norm(counterpart)
        if not key:
            return
        self.seen[key] += 1
        if was_dropped:
            self.dropped[key] += 1

    def drop_rate(self, counterpart: str) -> float:
        key = _norm(counterpart)
        total = self.seen.get(key, 0)
        return self.dropped.get(key, 0) / total if total else 0.0

    def to_dict(self) -> dict:
        return {"seen": dict(self.seen), "dropped": dict(self.dropped)}

    @classmethod
    def from_dict(cls, data: dict | None) -> LearnedStats:
        stats = cls()
        for key, value in (data or {}).get("seen", {}).items():
            stats.seen[key] = int(value)
        for key, value in (data or {}).get("dropped", {}).items():
            stats.dropped[key] = int(value)
        return stats


def auto_excluded(counterpart: str, stats: LearnedStats, config: ExclusionConfig) -> bool:
    key = _norm(counterpart)
    seen = stats.seen.get(key, 0)
    if seen < config.min_observations:
        return False
    return stats.drop_rate(key) >= config.drop_ratio


def build_queue(
    items: list[RawItem],
    inclusion: InclusionConfig,
    stats: LearnedStats | None = None,
    exclusion: ExclusionConfig | None = None,
) -> tuple[list[QueueItem], list[QueueItem]]:
    """(대기열, 자동제외된 것) 을 돌려준다.

    자동 제외된 것도 함께 돌려주는 이유: 조용히 사라지면 사용자가 신뢰할 수 없다.
    별도 시트에 남겨 "이런 걸 빼뒀습니다"를 보여준다.
    """
    stats = stats or LearnedStats()
    exclusion = exclusion or ExclusionConfig()

    queue: list[QueueItem] = []
    excluded: list[QueueItem] = []
    seen_keys: set[str] = set()
    seen_identities: set[tuple[str, str, str, str]] = set()

    for raw in sorted(items, key=lambda i: i.at):
        reason = include_reason(raw, inclusion)
        if reason is None:
            continue
        if raw.key in seen_keys:  # 같은 메일이 여러 폴더에 잡히는 경우
            continue
        seen_keys.add(raw.key)

        # EntryID는 사서함마다 다르게 붙는다. 부서 주소를 두 개 이상 넣으면 같은 메일이
        # 사서함 수만큼 올라오는데, 위의 키 비교로는 못 거른다. 내용으로 한 번 더 본다.
        #
        # 같은 분·같은 발신자·같은 제목이면 한 건으로 본다. 진짜 다른 메일이 이 조건에
        # 걸릴 수도 있지만(1분 안에 같은 제목으로 두 번 온 자동알림), 업무 기록에서는
        # 그것도 한 건으로 세는 편이 맞다.
        identity = (raw.at.isoformat(), raw.kind, _norm(raw.sender), raw.subject.strip())
        if identity in seen_identities:
            continue
        seen_identities.add(identity)

        counterpart = raw.sender if raw.kind != MAIL_SENT else ", ".join(raw.to)
        entry = QueueItem(
            key=raw.key,
            at=raw.at,
            kind=raw.kind,
            counterpart=counterpart,
            subject=raw.subject,
            reason=reason,
        )
        if auto_excluded(counterpart, stats, exclusion):
            rate = stats.drop_rate(counterpart)
            entry.hint = f"지금까지 {stats.seen[_norm(counterpart)]}회 중 {rate:.0%} 제외"
            excluded.append(entry)
        else:
            queue.append(entry)

    return queue, excluded
