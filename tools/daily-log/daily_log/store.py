"""로컬 저장소.

전부 이 PC 안에서만 돈다. 어디에도 올리지 않는다 — 회사 메일 제목이 들어 있기 때문이다.
`data/` 폴더는 .gitignore에 들어 있다.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib

from .models import QueueItem
from .rules import LearnedStats


class Store:
    def __init__(self, data_dir: pathlib.Path):
        self.dir = data_dir
        self.snapshots = data_dir / "snapshots"
        self.daily_path = data_dir / "daily.jsonl"
        self.stats_path = data_dir / "stats.json"

    # ── 스냅샷 ──────────────────────────────────────────
    # 대기열을 만들 때 원본을 남겨둬야 "무엇이 지워졌는지"를 알 수 있다.
    # 사용자는 행을 지우지 '삭제 표시'를 하지 않으므로, 비교 대상이 필요하다.

    def save_snapshot(self, day: dt.date, items: list[QueueItem]) -> None:
        self.snapshots.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "key": i.key,
                "at": i.at.isoformat(),
                "kind": i.kind,
                "counterpart": i.counterpart,
                "subject": i.subject,
                "reason": i.reason,
            }
            for i in items
        ]
        (self.snapshots / f"{day.isoformat()}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    def load_snapshot(self, day: dt.date) -> list[QueueItem]:
        path = self.snapshots / f"{day.isoformat()}.json"
        if not path.exists():
            return []
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        return [
            QueueItem(
                key=r["key"],
                at=dt.datetime.fromisoformat(r["at"]),
                kind=r.get("kind", ""),
                counterpart=r.get("counterpart", ""),
                subject=r.get("subject", ""),
                reason=r.get("reason", ""),
            )
            for r in raw
        ]

    # ── 확정된 일별 기록 ────────────────────────────────

    def append_daily(self, day: dt.date, entries: list[dict]) -> None:
        """같은 날짜를 다시 확정하면 덮어쓴다. 하루에 여러 번 돌려도 안전해야 한다."""
        existing = [r for r in self.load_daily() if r.get("date") != day.isoformat()]
        existing.extend({**e, "date": day.isoformat()} for e in entries)
        existing.sort(key=lambda r: (r.get("date", ""), r.get("at", "")))
        self.dir.mkdir(parents=True, exist_ok=True)
        self.daily_path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in existing) + "\n",
            encoding="utf-8",
        )

    def load_daily(
        self, start: dt.date | None = None, end: dt.date | None = None
    ) -> list[dict]:
        if not self.daily_path.exists():
            return []
        records = []
        for line in self.daily_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue  # 한 줄이 깨져도 나머지는 살린다
            day = record.get("date", "")
            if start and day < start.isoformat():
                continue
            if end and day > end.isoformat():
                continue
            records.append(record)
        return records

    # ── 학습 통계 ───────────────────────────────────────

    def load_stats(self) -> LearnedStats:
        if not self.stats_path.exists():
            return LearnedStats()
        try:
            return LearnedStats.from_dict(json.loads(self.stats_path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            return LearnedStats()

    def save_stats(self, stats: LearnedStats) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.stats_path.write_text(
            json.dumps(stats.to_dict(), ensure_ascii=False), encoding="utf-8"
        )
