"""대기열 엑셀 생성과 되읽기.

왜 엑셀인가: 이미 매일 쓰는 도구고, **행 삭제가 가장 직관적인 "아니오"** 이기 때문이다.
새 프로그램을 배우게 하면 3주 뒤에 안 쓴다.
"""

from __future__ import annotations

import datetime as dt
import pathlib

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from .models import QueueItem

FONT = "맑은 고딕"
ACCENT = "2563EB"
MUTED = "7B8794"
KEY_FILL = "F5F7FA"

HEADERS = ["시각", "종류", "상대", "제목", "포함 사유", "업무 내용 (고칠 것만)", "_key"]
KEY_COLUMN = 7
FIRST_ROW = 4

_THIN = Side(style="thin", color="D2D6DC")
BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)


def _title(ws, row: int, text: str, size: int = 14, color: str = "1F2933") -> None:
    cell = ws.cell(row=row, column=1, value=text)
    cell.font = Font(name=FONT, size=size, bold=True, color=color)


def _header(ws, row: int) -> None:
    for index, name in enumerate(HEADERS, start=1):
        cell = ws.cell(row=row, column=index, value=name)
        cell.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=ACCENT)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = BORDER
    ws.row_dimensions[row].height = 24


def _write_rows(ws, start: int, items: list[QueueItem], *, with_hint: bool = False) -> None:
    for offset, item in enumerate(items):
        row = start + offset
        values = [
            item.at.strftime("%H:%M"),
            item.kind,
            item.counterpart,
            item.subject,
            item.hint if with_hint and item.hint else item.reason,
            "",
            item.key,
        ]
        for index, value in enumerate(values, start=1):
            cell = ws.cell(row=row, column=index, value=value)
            cell.font = Font(name=FONT, size=10)
            cell.border = BORDER
            cell.alignment = Alignment(
                horizontal="center" if index in (1, 2) else "left", vertical="center"
            )
        key_cell = ws.cell(row=row, column=KEY_COLUMN)
        key_cell.font = Font(name=FONT, size=8, color=MUTED)
        key_cell.fill = PatternFill("solid", fgColor=KEY_FILL)


def write_queue(
    path: pathlib.Path,
    day: dt.date,
    queue: list[QueueItem],
    excluded: list[QueueItem] | None = None,
) -> pathlib.Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "오늘 업무"
    ws.sheet_view.showGridLines = False
    for column, width in {
        "A": 8, "B": 11, "C": 30, "D": 60, "E": 16, "F": 40, "G": 20
    }.items():
        ws.column_dimensions[column].width = width

    _title(ws, 1, f"{day.strftime('%Y-%m-%d (%a)')} 업무 대기열")
    note = ws.cell(
        row=2, column=1,
        value="업무가 아닌 행을 통째로 지우고 저장하세요. 남은 것이 오늘 업무로 기록됩니다. "
              "제목을 다듬고 싶으면 '업무 내용' 칸에 쓰면 그게 대신 들어갑니다.",
    )
    note.font = Font(name=FONT, size=9, color=MUTED)
    ws.merge_cells("A2:F2")

    _header(ws, 3)
    _write_rows(ws, FIRST_ROW, queue)
    ws.freeze_panes = f"A{FIRST_ROW}"
    ws.column_dimensions["G"].hidden = True  # _key는 손대지 말라는 뜻

    if excluded:
        # 조용히 사라지면 도구를 못 믿는다. 무엇을 뺐는지 보여준다.
        ws2 = wb.create_sheet("자동 제외됨")
        ws2.sheet_view.showGridLines = False
        for column, width in {
            "A": 8, "B": 11, "C": 30, "D": 60, "E": 26, "F": 40, "G": 20
        }.items():
            ws2.column_dimensions[column].width = width
        _title(ws2, 1, "자동으로 뺀 항목", size=12, color=MUTED)
        hint = ws2.cell(
            row=2, column=1,
            value="지금까지 항상 지우셨던 상대라 미리 뺐습니다. "
                  "잘못 뺀 게 있으면 이 행을 [오늘 업무] 시트로 옮겨주세요.",
        )
        hint.font = Font(name=FONT, size=9, color=MUTED)
        ws2.merge_cells("A2:F2")
        _header(ws2, 3)
        _write_rows(ws2, FIRST_ROW, excluded, with_hint=True)

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def read_kept(path: pathlib.Path) -> dict[str, str]:
    """사용자가 남긴 행을 돌려준다. {key: 업무내용}

    '업무 내용'을 적었으면 그 값을, 안 적었으면 제목을 쓴다.
    """
    wb = load_workbook(path, data_only=True)
    kept: dict[str, str] = {}

    for sheet_name in ("오늘 업무", "자동 제외됨"):
        if sheet_name not in wb.sheetnames:
            continue
        ws = wb[sheet_name]
        for row in ws.iter_rows(min_row=FIRST_ROW, values_only=True):
            if not row or len(row) < KEY_COLUMN:
                continue
            key = row[KEY_COLUMN - 1]
            if not key or not str(key).strip():
                continue
            subject = str(row[3] or "").strip()
            override = str(row[5] or "").strip()
            kept[str(key).strip()] = override or subject

    return kept
