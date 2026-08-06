"""Outlook 수집 어댑터.

⚠️ 이 파일만 Windows + Outlook 설치본에서만 동작한다. 나머지 모듈은 전부
이 파일 없이 테스트된다 — 그래서 로직이 틀렸는지는 Windows 없이도 알 수 있고,
여기가 틀렸는지는 실제로 돌려봐야 안다.

처음 돌릴 때 Outlook이 "다른 프로그램이 메일에 접근하려 합니다" 경고를 띄울 수 있다.
회사 보안 정책에 따라 막힐 수도 있는데, 그 경우 `--dry-run`으로 먼저 확인하면 된다.
"""

from __future__ import annotations

import datetime as dt

from .models import CALENDAR, MAIL_RECEIVED, MAIL_SENT, RawItem

# Outlook 기본 폴더 번호
FOLDER_SENT = 5
FOLDER_INBOX = 6
FOLDER_CALENDAR = 9

# Outlook Recipient.Type
RECIPIENT_TO = 1
RECIPIENT_CC = 2


class OutlookUnavailable(RuntimeError):
    """Outlook에 붙지 못했다. 원인을 사람이 읽을 수 있게 담는다."""


def _namespace():
    try:
        import win32com.client  # type: ignore[import-not-found]
    except ImportError as exc:
        raise OutlookUnavailable(
            "pywin32가 없습니다. `pip install pywin32` 후 다시 시도하세요. "
            "(Windows + Outlook 설치본에서만 동작합니다)"
        ) from exc

    try:
        return win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
    except Exception as exc:  # noqa: BLE001 — COM은 온갖 예외를 던진다
        raise OutlookUnavailable(
            f"Outlook에 연결하지 못했습니다: {exc}\n"
            "Outlook이 실행 중인지, 보안 정책이 외부 접근을 막고 있지 않은지 확인하세요."
        ) from exc


def _smtp(recipient) -> str:
    """수신자의 실제 메일 주소를 최대한 얻어낸다.

    Exchange 환경에서는 Address가 `/o=.../cn=...` 형태의 내부 주소로 나와
    비교가 안 된다. 그래서 ExchangeUser를 먼저 시도한다.
    """
    try:
        entry = recipient.AddressEntry
        exchange_user = entry.GetExchangeUser()
        if exchange_user and exchange_user.PrimarySmtpAddress:
            return str(exchange_user.PrimarySmtpAddress)
    except Exception:  # noqa: BLE001
        pass
    for attr in ("Address", "Name"):
        try:
            value = getattr(recipient, attr, "")
            if value:
                return str(value)
        except Exception:  # noqa: BLE001
            continue
    return ""


def _recipients(item) -> tuple[tuple[str, ...], tuple[str, ...]]:
    to: list[str] = []
    cc: list[str] = []
    try:
        for recipient in item.Recipients:
            address = _smtp(recipient)
            if not address:
                continue
            kind = getattr(recipient, "Type", RECIPIENT_TO)
            (to if kind == RECIPIENT_TO else cc if kind == RECIPIENT_CC else to).append(address)
    except Exception:  # noqa: BLE001 — 수신자를 못 읽어도 항목 자체는 살린다
        pass
    return tuple(to), tuple(cc)


def _sender(item) -> str:
    for attr in ("SenderEmailAddress", "SenderName"):
        try:
            value = getattr(item, attr, "")
            if value:
                return str(value)
        except Exception:  # noqa: BLE001
            continue
    return ""


def _as_datetime(value) -> dt.datetime | None:
    try:
        return dt.datetime(value.year, value.month, value.day, value.hour, value.minute)
    except Exception:  # noqa: BLE001
        return None


def _restrict(items, field: str, since: dt.datetime, until: dt.datetime):
    """날짜로 좁힌다.

    Outlook의 Restrict는 미국식 날짜 문자열만 안정적으로 먹는다.
    실패하면 전체를 훑는 쪽으로 물러난다 — 느리지만 결과는 같다.
    """
    fmt = "%m/%d/%Y %I:%M %p"
    query = f"[{field}] >= '{since.strftime(fmt)}' AND [{field}] <= '{until.strftime(fmt)}'"
    try:
        return items.Restrict(query)
    except Exception:  # noqa: BLE001
        return items


def collect(
    since: dt.datetime,
    until: dt.datetime,
    *,
    include_sent: bool = True,
    include_received: bool = True,
    include_calendar: bool = True,
    max_items: int = 2000,
) -> list[RawItem]:
    """기간 안의 메일·일정을 긁어온다. 걸러내지는 않는다 — 그건 rules.py 몫이다."""
    namespace = _namespace()
    collected: list[RawItem] = []

    def add_mail(folder_id: int, kind: str, time_field: str) -> None:
        folder = namespace.GetDefaultFolder(folder_id)
        items = _restrict(folder.Items, time_field, since, until)
        for index, item in enumerate(items):
            if index >= max_items:
                break
            when = _as_datetime(getattr(item, time_field, None))
            if when is None or not (since <= when <= until):
                continue
            to, cc = _recipients(item)
            collected.append(RawItem(
                at=when,
                kind=kind,
                subject=str(getattr(item, "Subject", "") or "(제목 없음)"),
                sender=_sender(item),
                to=to,
                cc=cc,
                entry_id=str(getattr(item, "EntryID", "") or ""),
            ))

    if include_received:
        add_mail(FOLDER_INBOX, MAIL_RECEIVED, "ReceivedTime")
    if include_sent:
        add_mail(FOLDER_SENT, MAIL_SENT, "SentOn")

    if include_calendar:
        folder = namespace.GetDefaultFolder(FOLDER_CALENDAR)
        items = folder.Items
        # 반복 일정을 펼치려면 정렬 후 IncludeRecurrences를 켜야 한다. 순서가 중요하다.
        try:
            items.Sort("[Start]")
            items.IncludeRecurrences = True
        except Exception:  # noqa: BLE001
            pass
        for index, item in enumerate(_restrict(items, "Start", since, until)):
            if index >= max_items:
                break
            when = _as_datetime(getattr(item, "Start", None))
            if when is None or not (since <= when <= until):
                continue
            collected.append(RawItem(
                at=when,
                kind=CALENDAR,
                subject=str(getattr(item, "Subject", "") or "(제목 없음)"),
                sender="",
                entry_id=str(getattr(item, "EntryID", "") or ""),
            ))

    return collected


def create_draft(subject: str, html_body: str, to: str = "") -> None:
    """주간 보고 메일 초안을 띄운다. 보내지는 않는다 — 확인은 사람이 한다."""
    namespace = _namespace()
    mail = namespace.Application.CreateItem(0)  # olMailItem
    mail.Subject = subject
    mail.HTMLBody = html_body
    if to:
        mail.To = to
    mail.Display()
