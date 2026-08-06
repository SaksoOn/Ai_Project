"""주간 보고 HTML 생성.

일별 기록이 쌓여 있으면 이건 순수 가공이다. 그래서 완전 자동화된다 —
사용자는 초안을 열어 확인하고 보내기만 누른다.
"""

from __future__ import annotations

import datetime as dt
import html

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]

STYLE = (
    "border-collapse:collapse;font-family:'맑은 고딕',sans-serif;font-size:10pt;width:100%"
)
TH = "border:1px solid #d2d6dc;background:#f5f7fa;padding:6px 10px;text-align:left"
TD = "border:1px solid #d2d6dc;padding:6px 10px;vertical-align:top"
TD_DATE = TD + ";white-space:nowrap;font-weight:bold;background:#fbfcfd"


def week_bounds(anchor: dt.date) -> tuple[dt.date, dt.date]:
    """해당 날짜가 속한 주의 월요일과 금요일."""
    monday = anchor - dt.timedelta(days=anchor.weekday())
    return monday, monday + dt.timedelta(days=4)


def build_html(records: list[dict], start: dt.date, end: dt.date) -> str:
    by_date: dict[str, list[dict]] = {}
    for record in records:
        by_date.setdefault(record.get("date", ""), []).append(record)

    rows = []
    day = start
    while day <= end:
        key = day.isoformat()
        entries = sorted(by_date.get(key, []), key=lambda r: r.get("at", ""))
        label = f"{day.strftime('%m/%d')} ({WEEKDAYS[day.weekday()]})"

        if entries:
            body = "<br>".join(
                f"· {html.escape(str(e.get('content', '')))}" for e in entries
            )
        else:
            body = "<span style='color:#9ca3af'>-</span>"
        rows.append(
            f"<tr><td style=\"{TD_DATE}\">{label}</td>"
            f"<td style=\"{TD}\">{body}</td>"
            f"<td style=\"{TD};text-align:center;white-space:nowrap\">{len(entries)}</td></tr>"
        )
        day += dt.timedelta(days=1)

    total = sum(len(v) for k, v in by_date.items() if start.isoformat() <= k <= end.isoformat())
    return (
        f"<p style=\"font-family:'맑은 고딕',sans-serif;font-size:10pt\">"
        f"{start.strftime('%Y-%m-%d')} ~ {end.strftime('%Y-%m-%d')} 주간 업무 보고입니다.</p>"
        f"<table style=\"{STYLE}\">"
        f"<tr><th style=\"{TH};width:90px\">일자</th>"
        f"<th style=\"{TH}\">업무 내용</th>"
        f"<th style=\"{TH};width:60px;text-align:center\">건수</th></tr>"
        + "".join(rows)
        + f"<tr><td style=\"{TD_DATE}\">합계</td>"
        f"<td style=\"{TD}\"></td>"
        f"<td style=\"{TD};text-align:center;font-weight:bold\">{total}</td></tr>"
        "</table>"
    )


def subject_for(start: dt.date, end: dt.date) -> str:
    return f"[주간업무보고] {start.strftime('%Y-%m-%d')} ~ {end.strftime('%m-%d')}"
