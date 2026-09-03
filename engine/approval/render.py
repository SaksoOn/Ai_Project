"""문서를 A4 HTML과 붙여넣기용 평문으로 렌더한다.

**설계의 핵심: HTML 한 벌로 화면·인쇄·PDF를 전부 처리한다.**
화면 미리보기와 인쇄물이 다른 코드에서 나오면 반드시 어긋나고, 한국 결재 문서는
종이로 뽑았을 때 기존 양식과 같아야 감사·세무에서 통과한다. 그래서 `@page`와
`@media print` 로 같은 문서를 두 매체에 맞춘다 — 본문 폭은 양쪽 다 180mm다.

평문 출력이 따로 있는 이유: Phase 0에서는 이 문서를 **기존 그룹웨어 편집기에
붙여넣어 상신**한다. HTML을 붙여넣으면 서식이 깨지므로 평문이 실제 주력이다.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass, field as dc_field
from html import escape
from typing import Any

from .schema import Field, FormTemplate
from .seal import seal_svg

# 기안자 칸의 이름. 한국 결재란은 관례적으로 기안자가 맨 왼쪽에 온다.
DRAFTER_COLUMN = "담당"


@dataclass(frozen=True)
class Approver:
    position: str
    name: str = ""
    approved_on: dt.date | None = None


@dataclass(frozen=True)
class DocumentMeta:
    title: str
    drafter: str = ""
    department: str = ""
    drafted_on: dt.date = dc_field(default_factory=dt.date.today)
    doc_no: str = ""
    company: str = ""
    approvers: tuple[Approver, ...] = ()


# ────────────────────────────── 값 포맷 ──────────────────────────────


def format_value(field: Field, raw: Any) -> str:
    """필드 타입에 맞게 사람이 읽을 문자열로. 빈 값은 빈 문자열."""
    if raw is None or raw == "" or raw == []:
        return ""

    if field.type == "money":
        try:
            return f"{int(round(float(raw))):,} 원"
        except (TypeError, ValueError):
            return str(raw)

    if field.type == "number":
        try:
            number = float(raw)
        except (TypeError, ValueError):
            return str(raw)
        return f"{int(number):,}" if number.is_integer() else f"{number:,}"

    if field.type == "date":
        return raw.isoformat() if isinstance(raw, (dt.date, dt.datetime)) else str(raw)

    if field.type == "user_list":
        items = raw if isinstance(raw, (list, tuple)) else [raw]
        return ", ".join(str(i) for i in items if str(i).strip())

    if field.type == "checkbox":
        return "☑" if raw else "☐"

    return str(raw)


def approval_columns(meta: DocumentMeta) -> tuple[Approver, ...]:
    """결재란에 실제로 그릴 칸. 기안자를 맨 앞에 넣는다."""
    drafter = Approver(DRAFTER_COLUMN, meta.drafter, meta.drafted_on)
    return (drafter, *meta.approvers)


# ────────────────────────────── HTML ──────────────────────────────

_CSS = """
@page { size: A4; margin: 20mm 15mm; }
* { box-sizing: border-box; }
body {
  margin: 0; background: #ecedef; color: #000;
  font-family: "Malgun Gothic", "맑은 고딕", "Noto Sans KR", "Apple SD Gothic Neo", sans-serif;
  font-size: 10.5pt; line-height: 1.55;
}
/* 화면에서도 A4 한 장으로 보인다. 본문 폭 210-15*2 = 180mm 로 인쇄와 같다. */
.sheet {
  width: 210mm; min-height: 297mm; padding: 20mm 15mm; margin: 8mm auto;
  background: #fff; box-shadow: 0 2px 14px rgba(0,0,0,.16);
}
.head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10mm; }
.head .who { font-size: 9.5pt; color: #333; }
.head .who div { margin-bottom: 1.5mm; }
.approval { border-collapse: collapse; table-layout: fixed; }
.approval td, .approval th { border: 0.6pt solid #333; text-align: center; padding: 0; }
.approval th { font-size: 8.5pt; font-weight: 600; height: 7mm; background: #f6f6f6; }
.approval td.box { height: 20mm; width: 20mm; vertical-align: middle; }
.approval td.on   { font-size: 8pt; height: 6mm; color: #333; }
.seal { display: block; margin: 0 auto; }
h1.title {
  text-align: center; font-size: 20pt; letter-spacing: 0.5em; text-indent: 0.5em;
  margin: 12mm 0 8mm; font-weight: 700;
}
h2.subject { text-align: center; font-size: 12pt; margin: -5mm 0 8mm; font-weight: 600; }
table.body { width: 100%; border-collapse: collapse; }
table.body th, table.body td { border: 0.6pt solid #333; padding: 2.4mm 3mm; vertical-align: top; }
table.body th {
  width: 30mm; background: #f6f6f6; text-align: center; font-weight: 600; white-space: nowrap;
}
table.body td.value { white-space: pre-wrap; word-break: break-word; }
table.body tr.block td { min-height: 20mm; }
.empty { color: #999; }
.foot { margin-top: 14mm; text-align: center; font-size: 13pt; font-weight: 700; letter-spacing: .2em; }
.note { max-width: 210mm; margin: 0 auto 6mm; font-size: 9pt; color: #555; }

@media print {
  body { background: #fff; }
  .sheet { width: auto; min-height: 0; margin: 0; padding: 0; box-shadow: none; }
  .no-print { display: none !important; }
}
/* 폰에서 A4를 축소하면 아무도 못 읽는다. 폭을 풀고 흐르게 둔다. */
@media screen and (max-width: 820px) {
  .sheet { width: auto; min-height: 0; padding: 6mm; margin: 0; box-shadow: none; }
  .head { flex-direction: column-reverse; align-items: stretch; gap: 5mm; }
  h1.title { font-size: 16pt; margin: 6mm 0 3mm; }
  h2.subject { margin: 0 0 6mm; font-size: 11pt; }  /* 데스크톱의 음수 여백은 여기선 너무 좁다 */
  table.body th { width: 24mm; }
}
"""


def _cell(text: str) -> str:
    return escape(text) if text else '<span class="empty">&nbsp;</span>'


def _approval_table(meta: DocumentMeta) -> str:
    """결재란. 우상단 도장 격자 — 이게 없으면 정식 문서로 안 보인다."""
    columns = approval_columns(meta)
    if not columns:
        return ""

    heads = "".join(f"<th>{escape(c.position)}</th>" for c in columns)
    boxes = "".join(
        f'<td class="box">{seal_svg(c.name) if c.approved_on and c.name else "&nbsp;"}</td>'
        for c in columns
    )
    dates = "".join(
        f'<td class="on">{c.approved_on.strftime("%m/%d") if c.approved_on else "&nbsp;"}</td>'
        for c in columns
    )
    return f"<table class='approval'><tr>{heads}</tr><tr>{boxes}</tr><tr>{dates}</tr></table>"


def _body_rows(template: FormTemplate, values: Mapping[str, Any]) -> str:
    rows: list[str] = []
    for f in template.fields:
        text = format_value(f, values.get(f.key))
        if f.full_width:
            rows.append(
                f'<tr><th colspan="2">{escape(f.label)}</th></tr>'
                f'<tr class="block"><td class="value" colspan="2">{_cell(text)}</td></tr>'
            )
        else:
            rows.append(
                f"<tr><th>{escape(f.label)}</th>"
                f'<td class="value">{_cell(text)}</td></tr>'
            )
    return "".join(rows)


def render_html(
    template: FormTemplate, values: Mapping[str, Any], meta: DocumentMeta
) -> str:
    """A4 한 장짜리 독립 HTML. 파일 하나로 열리고 그대로 인쇄·PDF 된다."""
    who = "".join(
        f"<div>{escape(label)}: {escape(value)}</div>"
        for label, value in (
            ("문서번호", meta.doc_no),
            ("기안부서", meta.department),
            ("기안자", meta.drafter),
            ("기안일", meta.drafted_on.isoformat()),
        )
        if value
    )

    subject = f'<h2 class="subject">{escape(meta.title)}</h2>' if meta.title else ""
    foot = f'<div class="foot">{escape(meta.company)}</div>' if meta.company else ""

    return (
        "<!doctype html>\n"
        '<html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(meta.title or template.name)}</title>"
        f"<style>{_CSS}</style></head><body>"
        '<div class="note no-print">브라우저에서 인쇄(Ctrl+P) → 대상을 "PDF로 저장"으로 두면 '
        "그대로 결재용 PDF가 됩니다.</div>"
        '<div class="sheet">'
        f'<div class="head"><div class="who">{who}</div>{_approval_table(meta)}</div>'
        f'<h1 class="title">{escape(template.name)}</h1>{subject}'
        f'<table class="body">{_body_rows(template, values)}</table>'
        f"{foot}</div></body></html>\n"
    )


# ────────────────────────────── 평문 ──────────────────────────────


def render_text(
    template: FormTemplate, values: Mapping[str, Any], meta: DocumentMeta
) -> str:
    """기존 그룹웨어 편집기에 붙여넣을 평문. Phase 0의 실제 주력 산출물이다."""
    lines: list[str] = [f"[{template.name}] {meta.title}".rstrip(), ""]

    for label, value in (
        ("문서번호", meta.doc_no),
        ("기안부서", meta.department),
        ("기안자", meta.drafter),
        ("기안일", meta.drafted_on.isoformat()),
    ):
        if value:
            lines.append(f"{label}: {value}")

    line_names = [a.position for a in meta.approvers]
    if line_names:
        lines.append("결재선: " + " → ".join(line_names))

    lines.append("")
    for f in template.fields:
        text = format_value(f, values.get(f.key))
        if not text:
            continue
        if f.full_width or "\n" in text:
            lines.append(f"■ {f.label}")
            lines.extend(f"   {chunk}" for chunk in text.splitlines())
            lines.append("")
        else:
            lines.append(f"■ {f.label}: {text}")

    return "\n".join(lines).rstrip() + "\n"
