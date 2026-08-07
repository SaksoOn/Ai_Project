"""확정된 업무 기록에서 반복업무 후보를 뽑는다.

왜 필요한가: 인벤토리를 손으로 채우면 **기억나는 것만** 적힌다. 실제로 시간을 잡아먹는
잔업무는 기억에 안 남아서 빠지고, 그게 바로 자동화 대상이다. 매일 확정한 기록에서
뽑으면 기억에 기대지 않는다.

무엇을 채우고 무엇을 비우는가:

- **채운다** — 업무명·분류·사용 시스템·작업 절차. 전부 기록에 근거가 있다.
- **주기** — 실제 발생 횟수로 계산한다. 단, 관측 기간이 짧으면 비운다.
  2주도 안 본 것을 "주 1회"라고 쓰면 그 숫자가 우선순위를 결정해버린다.
- **비운다** — 1회 소요시간. 사용자만 안다. 여기서 추정하면 우선순위 전체가 감이 된다.

마지막 항목이 이 파일의 설계 전제다. `APPROVALS.md` 가 파란 칸을 사용자에게 맡기지
않는 것과 같은 이유다 — 근거 없는 숫자가 순위를 정하면 안 된다.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from dataclasses import dataclass, field

# 관측이 이보다 짧으면 주기를 말하지 않는다.
MIN_SPAN_FOR_FREQUENCY = 14
MIN_SPAN_FOR_MONTHLY = 28

CATEGORIES = ["문서·승인", "시스템 운영", "데이터 집계·보고", "커뮤니케이션", "기타"]

# 제목 앞에 붙는 회신·전달 표식. 같은 업무가 갈라지지 않게 떼어낸다.
_PREFIX = re.compile(r"^\s*(re|fw|fwd|답장|회신|전달)\s*[:：]\s*", re.IGNORECASE)
# 괄호 안은 대개 그 건의 고유값(이름·날짜·번호)이다. 떼야 같은 업무로 묶인다.
#   "VPN 접속 승인요청서(홍길동,26.08.06)" → "VPN 접속 승인요청서"
_PARENS = re.compile(r"[(（][^)）]*[)）]")
_DATEISH = re.compile(r"\d{2,4}[-./]\d{1,2}([-./]\d{1,2})?|\d+\s*차|no\.?\s*\d+", re.IGNORECASE)
# 대괄호 안이 사실상 식별번호인 것만 뗀다. "[CASE 000000000000000]" 는 떼고
# "[테크톡]", "[사내공지]" 처럼 뜻이 있는 말머리는 남긴다.
_ID_BRACKET = re.compile(r"[\[［][^\]］]*\d{4,}[^\]］]*[\]］]")
_SPACE = re.compile(r"\s+")

# 절차 문장에서 시스템 이름을 건진다. 사내 시스템은 사람이 부르는 이름이 곧 이름이다.
_SYSTEMS = [
    ("아웃룩", ("아웃룩", "outlook", "메일", "mail")),
    ("MES", ("mes",)),
    ("ERP", ("erp",)),
    ("AWS", ("aws", "ses")),
    ("그룹웨어", ("그룹웨어", "결재", "전자결재")),
    ("엑셀", ("엑셀", "excel")),
    ("VPN", ("vpn",)),
    ("메신저", ("sns", "카톡", "카카오", "메신저", "zalo", "잘로")),
]

_CATEGORY_HINTS = [
    ("문서·승인", ("승인", "결재", "날인", "도장", "요청서", "품의", "체크리스트", "감사")),
    ("시스템 운영", ("점검", "장애", "오류", "설치", "계정", "서버", "백업", "복구", "세팅")),
    ("데이터 집계·보고", ("집계", "보고", "실적", "현황", "정산", "사용량", "취합")),
    ("커뮤니케이션", ("공지", "안내", "회의", "일정", "미팅")),
]


def normalize(subject: str) -> str:
    """묶음 키. 같은 업무의 여러 메일이 하나로 모이게 한다."""
    text = subject or ""
    while True:
        stripped = _PREFIX.sub("", text)
        if stripped == text:
            break
        text = stripped
    text = _PARENS.sub(" ", text)
    text = _DATEISH.sub(" ", text)
    text = _SPACE.sub(" ", text).strip(" -–—·:：")
    return text.casefold()


@dataclass
class Candidate:
    """반복업무 후보 하나."""

    name: str
    occurrences: list[dt.datetime] = field(default_factory=list)
    memos: list[str] = field(default_factory=list)
    kinds: Counter = field(default_factory=Counter)
    counterparts: Counter = field(default_factory=Counter)

    @property
    def count(self) -> int:
        return len(self.occurrences)

    @property
    def span_days(self) -> int:
        """관측 기간. 첫 기록과 마지막 기록 사이의 날수."""
        if not self.occurrences:
            return 0
        return (max(self.occurrences).date() - min(self.occurrences).date()).days + 1

    @property
    def procedure(self) -> str:
        """작업 절차. 사용자가 남긴 메모가 근거다 — 없으면 비운다."""
        seen: list[str] = []
        for memo in self.memos:
            memo = memo.strip()
            if memo and memo not in seen:
                seen.append(memo)
        return " / ".join(seen)

    @property
    def systems(self) -> str:
        haystack = " ".join([self.name, *self.memos]).casefold()
        found = [label for label, keys in _SYSTEMS if any(k in haystack for k in keys)]
        return ", ".join(found)

    @property
    def category(self) -> str:
        haystack = " ".join([self.name, *self.memos]).casefold()
        for label, keys in _CATEGORY_HINTS:
            if any(k in haystack for k in keys):
                return label
        return "기타"


def build_candidates(records: list[dict]) -> list[Candidate]:
    """확정 기록을 업무 단위로 묶는다.

    records 는 store.load_daily 가 주는 모양 그대로다:
    {"at": ISO8601, "kind": ..., "counterpart": ..., "content": ..., "subject": ...}

    묶는 기준은 **제목**이다. content 는 사용자가 적은 메모로 덮여 있어서 그날그날
    달라진다 — 그걸로 묶으면 같은 업무가 매번 새 줄이 된다. 대신 메모는 작업 절차의
    근거로 모은다. 예전 기록에는 subject 가 없으므로 content 로 물러선다.
    """
    grouped: dict[str, Candidate] = {}

    for record in records:
        content = str(record.get("content") or "").strip()
        subject = str(record.get("subject") or "").strip()
        basis = subject or content
        if not basis:
            continue
        key = normalize(basis)
        if not key:
            continue

        candidate = grouped.get(key)
        if candidate is None:
            # 표시용 이름은 정규화 전 원문을 쓴다. 정규화한 건 묶기 위한 키일 뿐이다.
            candidate = Candidate(name=_display_name(basis))
            grouped[key] = candidate

        candidate.occurrences.append(_parse_at(record.get("at")))
        candidate.kinds[record.get("kind") or ""] += 1
        candidate.counterparts[record.get("counterpart") or ""] += 1
        if content and content != subject:
            candidate.memos.append(content)

    ordered = sorted(grouped.values(), key=lambda c: (-c.count, c.name))
    return ordered


def suggest_frequency(candidate: Candidate) -> str:
    """실제 발생 횟수에서 주기를 낸다. 근거가 모자라면 빈 문자열.

    짧게 보고 주기를 단정하면 안 되는 이유: 주기는 연간 횟수로 곱해지고,
    연간 횟수는 비용과 우선순위로 이어진다. 한 번 틀리면 순위 전체가 틀어진다.
    """
    span = candidate.span_days
    if span < MIN_SPAN_FOR_FREQUENCY or candidate.count < 2:
        return ""

    per_week = candidate.count / (span / 7)
    if per_week >= 4:
        return "매일"
    if per_week >= 1.5:
        return "주 2~3회"
    if per_week >= 0.8:
        return "주 1회"
    if per_week >= 0.35:
        return "격주"
    if span >= MIN_SPAN_FOR_MONTHLY:
        return "월 1회"
    return ""


def evidence_note(candidate: Candidate) -> str:
    """왜 이 행이 생겼는지 남긴다. 근거 없이 늘어난 행은 사용자가 못 믿는다."""
    span = candidate.span_days
    parts = [f"기록에서 자동 추출 — {span}일간 {candidate.count}회"]
    if not suggest_frequency(candidate):
        parts.append(f"주기는 관측 {MIN_SPAN_FOR_FREQUENCY}일 이상부터 채웁니다")
    top = candidate.counterparts.most_common(1)
    if top and top[0][0]:
        parts.append(f"주 상대: {top[0][0]}")
    return " · ".join(parts)


# ── 인벤토리 엑셀에 써넣기 ────────────────────────────────────────
# 열 위치는 engine/products/sheets/work_inventory.py 와 맞춰져 있다.

SHEET = "업무목록"
ROW_FIRST, ROW_LAST = 6, 105
COL_NAME, COL_CATEGORY, COL_FREQUENCY = 1, 2, 3
COL_MINUTES, COL_SYSTEMS, COL_PROCEDURE = 4, 5, 7
COL_NOTE = 16


def write_into_inventory(path, candidates: list[Candidate]) -> tuple[list[str], list[str], int]:
    """인벤토리 [업무목록]에 후보를 추가한다. (추가된 것, 이미 있던 것, 남은 칸)

    이미 있는 업무는 건드리지 않는다. 사용자가 소요시간을 채워놨는데 덮어쓰면
    다음부터 이 명령을 못 믿게 된다. 새 줄만 붙인다.
    """
    from openpyxl import load_workbook

    wb = load_workbook(path)
    if SHEET not in wb.sheetnames:
        raise ValueError(f"[{SHEET}] 시트가 없습니다: {path}")
    ws = wb[SHEET]

    existing: set[str] = set()
    free_rows: list[int] = []
    for row in range(ROW_FIRST, ROW_LAST + 1):
        name = ws.cell(row=row, column=COL_NAME).value
        if name and str(name).strip():
            existing.add(normalize(str(name)))
        else:
            free_rows.append(row)

    added: list[str] = []
    skipped: list[str] = []
    for candidate in candidates:
        if normalize(candidate.name) in existing:
            skipped.append(candidate.name)
            continue
        if not free_rows:
            break
        row = free_rows.pop(0)
        # openpyxl 의 cell(value=None) 은 셀을 지우지 않고 그냥 넘어간다.
        # 빈 값을 넣으려면 .value = None 으로 써야 한다. 안 그러면 업무명만 지워둔
        # 행을 재사용할 때 예전 주기·절차가 새 업무에 붙는다.
        for column, value in {
            COL_NAME: candidate.name,
            COL_CATEGORY: candidate.category,
            COL_FREQUENCY: suggest_frequency(candidate) or None,
            # 1회 소요시간은 비운다. 여기서 찍으면 우선순위가 감이 된다.
            COL_MINUTES: None,
            COL_SYSTEMS: candidate.systems or None,
            COL_PROCEDURE: candidate.procedure or None,
            COL_NOTE: evidence_note(candidate),
        }.items():
            ws.cell(row=row, column=column).value = value
        added.append(candidate.name)
        existing.add(normalize(candidate.name))

    if added:
        wb.save(path)
    return added, skipped, len(free_rows)


def _display_name(content: str) -> str:
    """반복업무의 이름. 그 건에만 해당하는 값은 떼어낸다.

    "FW: VPN 접속 승인요청서(홍길동,26.08.06)" → "VPN 접속 승인요청서"

    normalize() 와 같은 것을 떼지만 casefold 는 하지 않는다. 저건 묶음 키라 대소문자가
    상관없지만, 이건 사람이 인벤토리에서 읽을 이름이다.
    """
    text = _strip_prefixes(content)
    text = _PARENS.sub(" ", text)
    text = _ID_BRACKET.sub(" ", text)
    text = _DATEISH.sub(" ", text)
    text = _SPACE.sub(" ", text).strip(" -–—·:：,")
    # 다 떼고 나면 빈 문자열이 되는 제목이 있다(예: "[CASE 12345]"). 그럴 땐 원문을 쓴다.
    return text or _SPACE.sub(" ", _strip_prefixes(content)).strip()


def _strip_prefixes(text: str) -> str:
    text = text or ""
    while True:
        stripped = _PREFIX.sub("", text)
        if stripped == text:
            return text
        text = stripped


def _parse_at(value) -> dt.datetime:
    if isinstance(value, dt.datetime):
        return value
    try:
        return dt.datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return dt.datetime.min
