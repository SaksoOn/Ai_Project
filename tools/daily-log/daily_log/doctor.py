"""환경 진단.

만든 사람이 옆에 없어도 "뭐가 왜 안 되는지"가 한 화면에 나와야 한다.
그래야 결과를 그대로 복사해 물어볼 수 있다.

아무것도 쓰지 않는다. 읽기만 한다.
"""

from __future__ import annotations

import datetime as dt
import pathlib
import sys

from .console import FAIL, PASS as OK

WARN = "!"

# config.example.toml 을 복사만 하고 안 고친 상태를 잡아내기 위한 값.
EXAMPLE_MY_ADDRESS = "본인@회사.com"
EXAMPLE_DEPARTMENT_ADDRESS = "부서메일@회사.com"


class Report:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.failed = False
        self.blocked = False  # 더 진행해도 의미 없는 실패

    def ok(self, label: str, detail: str = "") -> None:
        self.lines.append(f"{OK} {label}" + (f"  — {detail}" if detail else ""))

    def warn(self, label: str, detail: str = "") -> None:
        self.lines.append(f"{WARN} {label}" + (f"  — {detail}" if detail else ""))

    def fail(self, label: str, detail: str = "", *, blocking: bool = False) -> None:
        self.lines.append(f"{FAIL} {label}" + (f"  — {detail}" if detail else ""))
        self.failed = True
        if blocking:
            self.blocked = True

    def section(self, title: str) -> None:
        self.lines.append(f"\n── {title} ─────────────────────────")

    def render(self) -> str:
        return "\n".join(self.lines)


def _check_python(report: Report) -> None:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 11):
        report.ok("Python", version)
    else:
        report.fail("Python", f"{version} — 3.11 이상이 필요합니다 (설정 파일 읽기)", blocking=True)


def _check_packages(report: Report) -> bool:
    has_win32 = False
    try:
        import openpyxl  # noqa: F401

        report.ok("openpyxl", "설치됨")
    except ImportError:
        report.fail("openpyxl", "없음 — `pip install openpyxl`", blocking=True)

    if sys.platform != "win32":
        report.warn("pywin32", f"현재 OS가 {sys.platform} 입니다. Outlook 수집은 Windows에서만 됩니다")
        return False

    try:
        import win32com.client  # noqa: F401

        report.ok("pywin32", "설치됨")
        has_win32 = True
    except ImportError:
        report.fail("pywin32", "없음 — `pip install pywin32`", blocking=True)
    return has_win32


def _check_config(report: Report, config_path: pathlib.Path):
    from . import config as config_module

    if not config_path.exists():
        report.fail(
            "config.toml",
            f"없음 — `cp config.example.toml config.toml` 후 메일 주소를 채우세요",
            blocking=True,
        )
        return None
    try:
        cfg = config_module.load(config_path)
    except Exception as exc:  # noqa: BLE001
        report.fail("config.toml", f"읽지 못했습니다: {exc}", blocking=True)
        return None

    my_address = cfg.inclusion.my_addresses[0]
    if my_address.strip().casefold() == EXAMPLE_MY_ADDRESS.casefold():
        # 이걸 놓치면 받은 메일이 한 건도 안 걸리는데, 사용자는 "원래 이런가 보다" 한다.
        report.fail(
            "config.toml",
            f"[me] email 이 예시값 그대로입니다 ({my_address}) — "
            "본인 주소로 바꾸지 않으면 받은 메일이 하나도 안 잡힙니다",
        )
    else:
        report.ok("config.toml", f"내 주소 {my_address}")

    departments = cfg.inclusion.department_addresses
    example_departments = [
        a for a in departments if a.strip().casefold() == EXAMPLE_DEPARTMENT_ADDRESS.casefold()
    ]
    if example_departments:
        report.fail(
            "부서 주소",
            f"예시값 그대로입니다 ({', '.join(example_departments)}) — "
            "실제 부서 주소로 바꾸거나, 안 쓰면 빈 배열로 두세요",
        )
    elif departments:
        report.ok("부서 주소", ", ".join(departments))
    else:
        report.warn("부서 주소", "비어 있음 — 부서로 온 메일은 안 잡힙니다")
    return cfg


def _check_paths(report: Report, cfg) -> None:
    for label, path in (("data", cfg.data_dir), ("queue", cfg.queue_dir)):
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            report.ok(f"{label} 폴더 쓰기", str(path))
        except Exception as exc:  # noqa: BLE001
            report.fail(f"{label} 폴더 쓰기", f"{path} — {exc}")


def _check_outlook(report: Report, cfg, day: dt.date, verbose: bool) -> None:
    from .outlook import OutlookUnavailable, collect
    from .rules import build_queue

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
        report.fail("Outlook 연결", str(exc).replace("\n", " "), blocking=True)
        return
    except Exception as exc:  # noqa: BLE001
        report.fail("Outlook 수집", f"예상치 못한 오류: {exc}", blocking=True)
        return

    report.ok("Outlook 연결", "성공")

    kinds: dict[str, int] = {}
    for item in items:
        kinds[item.kind] = kinds.get(item.kind, 0) + 1
    if items:
        report.ok("수집", ", ".join(f"{k} {v}건" for k, v in sorted(kinds.items())))
    else:
        report.warn("수집", f"{day} 항목이 0건입니다. 날짜를 바꿔 다시 해보세요 (--date)")

    queue, excluded = build_queue(items, cfg.inclusion)
    report.ok("필터 통과", f"{len(queue)}건이 대기열에 오릅니다 (전체 {len(items)}건 중)")

    if items and not queue:
        report.warn(
            "필터",
            "수집은 됐는데 하나도 안 걸렸습니다. config.toml 의 메일 주소가 "
            "Outlook에 보이는 주소와 다를 수 있습니다",
        )

    reasons: dict[str, int] = {}
    for entry in queue:
        reasons[entry.reason] = reasons.get(entry.reason, 0) + 1
    if reasons:
        report.ok("포함 사유", ", ".join(f"{k} {v}건" for k, v in sorted(reasons.items())))

    if verbose and queue:
        report.section("대기열 미리보기 (--verbose)")
        for entry in queue[:10]:
            report.lines.append(
                f"   {entry.at.strftime('%H:%M')} [{entry.kind}] "
                f"{entry.subject[:40]} ← {entry.reason}"
            )
        if len(queue) > 10:
            report.lines.append(f"   … 외 {len(queue) - 10}건")


def run(config_path: pathlib.Path, day: dt.date, verbose: bool = False) -> tuple[str, bool]:
    """(보고서, 성공여부)를 돌려준다. 아무것도 쓰지 않는다."""
    report = Report()
    report.section("환경")
    _check_python(report)
    has_outlook = _check_packages(report)

    report.section("설정")
    cfg = _check_config(report, config_path)

    if cfg and not report.blocked:
        report.section("경로")
        _check_paths(report, cfg)

        if has_outlook:
            report.section(f"Outlook ({day})")
            _check_outlook(report, cfg, day, verbose)
        else:
            report.section("Outlook")
            report.warn("건너뜀", "Windows가 아니거나 pywin32가 없습니다. `demo`로 흐름만 확인하세요")

    report.lines.append("")
    if report.blocked:
        report.lines.append(f"→ 위 {FAIL} 항목을 먼저 해결해야 합니다.")
    elif report.failed:
        report.lines.append(
            f"→ {FAIL} 가 있지만 진행은 가능합니다. `demo` 로 흐름을 먼저 확인해 보세요."
        )
    else:
        report.lines.append("→ 준비됐습니다. `python run.py collect` 을 실행하세요.")

    return report.render(), not report.blocked
