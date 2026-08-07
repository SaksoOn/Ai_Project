#!/usr/bin/env python3
"""일일 업무기록 · 주간보고 자동화.

    python run.py collect     오늘 메일·일정을 긁어 대기열 엑셀 생성
    python run.py confirm     대기열에서 남긴 것을 확정하고, 지운 것을 학습
    python run.py weekly      이번 주 기록으로 보고 메일 초안 생성
    python run.py demo        가짜 데이터로 전체 흐름 시연 (Outlook 불필요)
    python run.py doctor      환경 진단 — 뭐가 왜 안 되는지 한 화면에
                              (아무것도 쓰지 않음. 막히면 결과를 그대로 물어보세요)

하루 흐름:
    아침/퇴근 전 → collect → 엑셀에서 업무 아닌 행 삭제 → 저장 → confirm
    금요일       → weekly → 초안 확인 후 발송
"""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import sys

from daily_log import config as config_module
from daily_log import queue_sheet, weekly
from daily_log.console import FAIL, PASS, configure
from daily_log.models import CALENDAR, MAIL_RECEIVED, MAIL_SENT, RawItem
from daily_log.rules import build_queue
from daily_log.store import Store

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "config.toml"


def _queue_path(cfg, day: dt.date) -> pathlib.Path:
    return cfg.queue_dir / f"업무대기_{day.isoformat()}.xlsx"


def cmd_collect(cfg, day: dt.date, fake: list[RawItem] | None = None) -> int:
    store = Store(cfg.data_dir)

    if fake is not None:
        items = fake
    else:
        from daily_log.outlook import OutlookUnavailable, collect

        since = dt.datetime.combine(day - dt.timedelta(days=cfg.lookback_days), dt.time.min)
        until = dt.datetime.combine(day, dt.time.max)
        try:
            items = collect(
                since, until,
                include_sent=cfg.inclusion.include_sent,
                include_received=cfg.inclusion.include_to or cfg.inclusion.include_department,
                include_calendar=cfg.inclusion.include_calendar,
            )
        except OutlookUnavailable as exc:
            print(f"{FAIL} {exc}", file=sys.stderr)
            return 1

    queue, excluded = build_queue(items, cfg.inclusion, store.load_stats(), cfg.exclusion)

    path = _queue_path(cfg, day)
    queue_sheet.write_queue(path, day, queue, excluded)
    store.save_snapshot(day, queue + excluded)

    print(f"{PASS} 대기열 {len(queue)}건 생성 → {path}")
    if excluded:
        print(f"  (늘 빼시던 {len(excluded)}건은 '자동 제외됨' 시트로 뺐습니다)")
    print("\n다음 순서로 하시면 됩니다:")
    print("  1. 위 엑셀을 엽니다")
    print("  2. 업무가 아닌 줄은 '구분'을 [아님] 으로 바꿉니다 (행을 지워도 같습니다)")
    print("     '업무 내용 / 메모' 에 왜 아닌지 적어두면 반복업무를 뽑을 때 근거로 씁니다")
    print("  3. 저장한 뒤 2_확정.bat (또는 `python run.py confirm`) 을 실행합니다")
    return 0


def cmd_confirm(cfg, day: dt.date) -> int:
    store = Store(cfg.data_dir)
    path = _queue_path(cfg, day)
    if not path.exists():
        print(f"{FAIL} 대기열 파일이 없습니다: {path}\n먼저 `python run.py collect` 을 실행하세요.",
              file=sys.stderr)
        return 1

    snapshot = store.load_snapshot(day)
    if not snapshot:
        print(f"{FAIL} {day} 스냅샷이 없습니다. 학습 없이 진행할 수 없습니다.", file=sys.stderr)
        return 1

    kept = queue_sheet.read_kept(path)

    entries = []
    stats = store.load_stats()
    for item in snapshot:
        was_dropped = item.key not in kept
        stats.observe(item.counterpart, was_dropped=was_dropped)
        if not was_dropped:
            entries.append({
                "at": item.at.isoformat(),
                "kind": item.kind,
                "counterpart": item.counterpart,
                "content": kept[item.key] or item.subject,
                # 제목을 따로 남긴다. content 는 메모로 덮이는데, 메모는 그날그날 달라서
                # 같은 업무를 묶는 기준으로 못 쓴다. 반복업무 추출이 제목에 걸려 있다.
                "subject": item.subject,
            })

    store.append_daily(day, entries)
    store.save_stats(stats)

    dropped = len(snapshot) - len(entries)
    print(f"{PASS} {day} 업무 {len(entries)}건 확정 (제외 {dropped}건)")
    if dropped:
        print("  제외 패턴을 학습했습니다. 다음 대기열은 조금 더 깨끗해집니다.")
    return 0


def cmd_weekly(cfg, day: dt.date, *, no_outlook: bool = False) -> int:
    store = Store(cfg.data_dir)
    start, end = weekly.week_bounds(day)
    records = store.load_daily(start, end)

    if not records:
        print(f"{FAIL} {start} ~ {end} 기록이 없습니다. confirm 을 먼저 실행하세요.", file=sys.stderr)
        return 1

    html_body = weekly.build_html(records, start, end)
    subject = weekly.subject_for(start, end)

    out = cfg.queue_dir / f"주간보고_{start.isoformat()}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_body, encoding="utf-8")
    print(f"{PASS} 주간보고 {len(records)}건 → {out}")

    if no_outlook:
        return 0
    try:
        from daily_log.outlook import OutlookUnavailable, create_draft

        create_draft(subject, html_body, cfg.report_to)
        print(f"{PASS} Outlook 초안을 띄웠습니다. 확인 후 보내세요.")
    except Exception as exc:  # noqa: BLE001
        print(f"  (Outlook 초안 생성은 건너뜁니다: {exc})")
        print(f"  위 HTML 파일을 열어 복사해 붙여넣으셔도 됩니다.")
    return 0


DEFAULT_INVENTORY = pathlib.Path(__file__).resolve().parents[2] / "dist" / "반복업무_인벤토리.xlsx"


def cmd_inventory(cfg, path: pathlib.Path, *, dry_run: bool = False) -> int:
    from daily_log import inventory

    store = Store(cfg.data_dir)
    records = store.load_daily()
    if not records:
        print(f"{FAIL} 확정된 기록이 없습니다. `python run.py confirm` 을 먼저 실행하세요.",
              file=sys.stderr)
        return 1

    candidates = inventory.build_candidates(records)
    if not candidates:
        print(f"{FAIL} 기록에서 뽑을 업무가 없습니다.", file=sys.stderr)
        return 1

    days = {r.get("date") for r in records if r.get("date")}
    print(f"기록 {len(records)}건 / {len(days)}일 → 업무 후보 {len(candidates)}건\n")
    for c in candidates:
        frequency = inventory.suggest_frequency(c) or "주기 미정"
        print(f"  {c.count:>2}회  {c.name[:44]:<44}  {c.category} · {frequency}")

    if dry_run:
        print("\n(--dry-run 이라 파일은 건드리지 않았습니다)")
        return 0

    if not path.exists():
        print(f"\n{FAIL} 인벤토리 파일이 없습니다: {path}\n"
              f"저장소 루트에서 `python -m engine.products.build` 를 먼저 실행하세요.",
              file=sys.stderr)
        return 1

    try:
        added, skipped, free = inventory.write_into_inventory(path, candidates)
    except (ValueError, OSError) as exc:
        print(f"\n{FAIL} 인벤토리에 쓰지 못했습니다: {exc}", file=sys.stderr)
        return 1

    print(f"\n{PASS} {len(added)}건 추가 → {path}")
    if skipped:
        print(f"  이미 있어서 건너뜀 {len(skipped)}건 (기존 내용은 그대로 둡니다)")
    if not free:
        print("  ! 업무목록이 가득 찼습니다. 다 쓴 행을 정리해주세요.")
    if added:
        print("\n1회 소요시간은 비워뒀습니다. 그 칸만 채우시면 우선순위가 계산됩니다.")
    return 0


def _demo_items(day: dt.date, me: str, dept: str) -> list[RawItem]:
    """Outlook 없이 전체 흐름을 확인하기 위한 가짜 하루."""
    def at(hour, minute=0):
        return dt.datetime.combine(day, dt.time(hour, minute))

    return [
        RawItem(at(9, 5), MAIL_RECEIVED, "1월 정산 자료 확인 요청",
                sender="kim@partner.com", to=(me,)),
        RawItem(at(9, 20), MAIL_RECEIVED, "[사내공지] 보안교육 이수 안내",
                sender="noreply@company.com", to=(dept,)),
        RawItem(at(10, 0), CALENDAR, "주간 부서회의"),
        RawItem(at(11, 30), MAIL_SENT, "RE: 1월 정산 자료 확인 요청",
                sender=me, to=("kim@partner.com",)),
        RawItem(at(14, 0), MAIL_RECEIVED, "전산업무의뢰서 반려 건",
                sender="lee@company.com", to=(dept,)),
        RawItem(at(16, 45), MAIL_RECEIVED, "광고: 이번 주 특가",
                sender="ad@newsletter.com", cc=(me,)),  # CC라 애초에 안 들어옴
    ]


def cmd_demo(cfg, day: dt.date) -> int:
    me = cfg.inclusion.my_addresses[0]
    dept = (cfg.inclusion.department_addresses or ("team@company.com",))[0]
    print("── 가짜 하루로 전체 흐름을 돌려봅니다 (Outlook 불필요) ──\n")
    if cmd_collect(cfg, day, fake=_demo_items(day, me, dept)) != 0:
        return 1
    print(f"\n엑셀을 열어보세요: {_queue_path(cfg, day)}")
    print("행을 지우고 저장한 뒤 `python run.py confirm` → `python run.py weekly` 순으로 실행하면")
    print("실제와 똑같은 흐름을 Outlook 없이 확인하실 수 있습니다.")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="일일 업무기록 · 주간보고 자동화")
    parser.add_argument(
        "command", choices=["collect", "confirm", "weekly", "demo", "doctor", "inventory"]
    )
    parser.add_argument("--config", type=pathlib.Path, default=DEFAULT_CONFIG)
    parser.add_argument("--date", help="YYYY-MM-DD (기본: 오늘)")
    parser.add_argument("--no-outlook", action="store_true", help="Outlook 초안 생성을 건너뜀")
    parser.add_argument(
        "--verbose", action="store_true", help="doctor: 대기열 미리보기까지 출력"
    )
    parser.add_argument(
        "--inventory", type=pathlib.Path, default=DEFAULT_INVENTORY,
        help="inventory: 반복업무 인벤토리 엑셀 경로",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="inventory: 뽑기만 하고 파일은 안 건드림"
    )
    args = parser.parse_args(argv)

    day = dt.date.fromisoformat(args.date) if args.date else dt.date.today()

    if args.command == "doctor":
        from daily_log import doctor

        text, ok = doctor.run(args.config, day, verbose=args.verbose)
        print(text)
        return 0 if ok else 1

    try:
        cfg = config_module.load(args.config)
    except (FileNotFoundError, ValueError) as exc:
        print(f"{FAIL} {exc}", file=sys.stderr)
        return 1

    if args.command == "collect":
        return cmd_collect(cfg, day)
    if args.command == "confirm":
        return cmd_confirm(cfg, day)
    if args.command == "weekly":
        return cmd_weekly(cfg, day, no_outlook=args.no_outlook)
    if args.command == "inventory":
        return cmd_inventory(cfg, args.inventory, dry_run=args.dry_run)
    return cmd_demo(cfg, day)


if __name__ == "__main__":
    configure()
    raise SystemExit(main(sys.argv[1:]))
