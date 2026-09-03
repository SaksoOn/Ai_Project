"""환경 진단.

만든 사람이 옆에 없어도 "뭐가 왜 안 되는지"가 한 화면에 나와야 한다.
그래야 결과를 그대로 복사해 물어볼 수 있다. `tools/daily-log` 의 doctor 와 같은 규약이다.

아무것도 쓰지 않는다. 읽기만 한다.
"""

from __future__ import annotations

import pathlib
import sys

from engine.products.console import FAIL, PASS as OK

WARN = "!"


class Report:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.failed = False

    def ok(self, label: str, detail: str = "") -> None:
        self.lines.append(f"{OK} {label}" + (f"  — {detail}" if detail else ""))

    def warn(self, label: str, detail: str = "") -> None:
        self.lines.append(f"{WARN} {label}" + (f"  — {detail}" if detail else ""))

    def fail(self, label: str, detail: str = "") -> None:
        self.lines.append(f"{FAIL} {label}" + (f"  — {detail}" if detail else ""))
        self.failed = True

    def section(self, title: str) -> None:
        self.lines.append(f"\n── {title} ─────────────────────────")

    def render(self) -> str:
        return "\n".join(self.lines)


def _check_python(report: Report) -> None:
    v = sys.version_info
    version = f"{v.major}.{v.minor}.{v.micro}"
    if v >= (3, 11):
        report.ok("Python", version)
    else:
        report.fail("Python", f"{version} — 3.11 이상이 필요합니다")


def _check_yaml(report: Report) -> bool:
    try:
        import yaml  # noqa: F401
    except ImportError:
        report.fail("PyYAML", "설치되지 않음 — pip install PyYAML")
        return False
    report.ok("PyYAML", "설치됨")
    return True


def _check_forms(report: Report) -> None:
    from . import schema

    report.section("양식")

    if not schema.FORMS_DIR.is_dir():
        report.fail("기본 양식 폴더", f"{schema.FORMS_DIR} 이 없습니다")
        return

    paths = sorted(schema.FORMS_DIR.glob("*.yaml"))
    if not paths:
        report.fail("기본 양식", f"{schema.FORMS_DIR} 에 *.yaml 이 없습니다")
        return

    loaded: dict[str, str] = {}
    for path in paths:
        try:
            template = schema.load_file(path)
        except schema.FormError as exc:
            report.fail(path.name, str(exc))
            continue
        loaded[template.code] = template.name
        report.ok(
            f"{template.name} ({template.code})",
            f"필드 {len(template.fields)}개, 결재선 규칙 {len(template.rules)}개",
        )

    if schema.LOCAL_FORMS_DIR.is_dir():
        local = sorted(schema.LOCAL_FORMS_DIR.glob("*.yaml"))
        for path in local:
            try:
                template = schema.load_file(path)
            except schema.FormError as exc:
                report.fail(f"forms.local/{path.name}", str(exc))
                continue
            verb = "덮어씀" if template.code in loaded else "추가"
            report.ok(f"forms.local/{path.name}", f"{template.name} — 기본 양식을 {verb}")
        if not local:
            report.warn("forms.local/", "폴더는 있으나 비어 있음")
    else:
        report.warn(
            "forms.local/",
            "없음 — 사내 실제 규정을 쓰려면 여기에 양식을 두세요 (저장소에 안 올라감)",
        )


def _check_output(report: Report, drafts: pathlib.Path, out: pathlib.Path) -> None:
    report.section("출력 위치")
    for label, path in (("초안", drafts), ("문서", out)):
        if path.exists():
            report.ok(f"{label} 폴더", str(path))
        else:
            report.warn(f"{label} 폴더", f"{path} — 아직 없음 (처음 실행할 때 만들어집니다)")


def run(drafts: pathlib.Path, out: pathlib.Path) -> tuple[str, bool]:
    report = Report()
    report.section("환경")
    _check_python(report)

    if _check_yaml(report):
        _check_forms(report)

    _check_output(report, drafts, out)

    report.lines.append("")
    if report.failed:
        report.lines.append(f"{FAIL} 위의 실패 항목을 먼저 해결하세요.")
    else:
        report.lines.append(f"{OK} 문서를 만들 준비가 됐습니다.")

    return report.render(), not report.failed
