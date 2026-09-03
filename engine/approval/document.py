"""작성용 입력 파일(초안 YAML)을 만들고, 읽고, 검증한다.

왜 대화형 입력이 아니라 파일인가: 결재 문서는 한 번에 다 쓰지 않는다. 쓰다 말고
자료를 찾으러 갔다가 돌아온다. 프롬프트로 물으면 그 순간 처음부터 다시다.
파일로 두면 편집기에서 쓰다 말다 할 수 있고, 초안 자체가 기록으로 남는다.

**문서번호를 자동 생성하지 않는 이유.** Phase 0에서 이 문서는 기존 그룹웨어에
붙여넣어 상신하고, 진짜 문서번호는 그쪽이 매긴다. 여기서 그럴듯한 번호를 만들면
정본이 아닌 번호가 문서에 박혀 나중에 대조할 때 혼란만 준다. 비워두는 게 정직하다.
"""

from __future__ import annotations

import datetime as dt
import pathlib
from typing import Any

import yaml

from .schema import FormTemplate, FormError

# 초안 YAML 에서 값이 아닌 메타 키.
META_KEYS = ("form", "title", "drafter", "department", "company", "drafted_on", "doc_no")


class DraftError(ValueError):
    """초안 파일이 잘못됐다."""


# ────────────────────────────── 만들기 ──────────────────────────────

# 빈 칸을 `key:` 로만 두면 YAML 이 None 으로 읽어 "어디에 쓰라는 건지" 가 안 보인다.
# 따옴표를 남겨서 커서를 둘 자리를 만든다.
_PLACEHOLDER = {
    "date": '""',
    "money": 0,
    "number": 0,
    "checkbox": False,
    "user_list": '""',
}


def skeleton(template: FormTemplate, today: dt.date | None = None) -> str:
    """채워 넣을 초안 YAML. 주석으로 무엇을 적어야 하는지 옆에 붙인다."""
    today = today or dt.date.today()

    lines = [
        f"# {template.name} 초안 — 값을 채운 뒤 build 하세요.",
        f"#   python3 -m engine.approval.generate build <이 파일>",
        "#",
        "# 문서번호는 비워두세요. 기존 그룹웨어에 상신하면 그쪽이 매깁니다.",
        "",
        f"form: {template.code}",
        'title: ""            # 문서 제목 (한 줄)',
        'drafter: ""          # 기안자',
        'department: ""       # 기안부서',
        'company: ""          # 문서 하단에 찍을 회사명 (비우면 안 찍음)',
        f"drafted_on: {today.isoformat()}",
        'doc_no: ""',
        "",
        "values:",
    ]

    for f in template.fields:
        default = _PLACEHOLDER.get(f.type, '""')
        note = [f.label]
        if f.required:
            note.append("필수")
        if f.type == "select":
            note.append("/".join(f.options))
        if f.hint:
            note.append(f.hint)

        if f.type == "textarea":
            lines.append(f"  {f.key}: |         # {' — '.join(note)}")
            lines.append("    ")
        else:
            lines.append(f"  {f.key}: {default}".ljust(30) + f"# {' — '.join(note)}")

    return "\n".join(lines) + "\n"


# ────────────────────────────── 읽기 ──────────────────────────────


def load_draft(path: pathlib.Path) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """초안 파일을 (양식코드, 메타, 값) 으로 나눠 돌려준다."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise DraftError(f"{path}: YAML 을 읽을 수 없습니다 — {exc}") from exc
    except OSError as exc:
        raise DraftError(f"{path}: 파일을 열 수 없습니다 — {exc}") from exc

    if not isinstance(data, dict):
        raise DraftError(f"{path}: 최상위가 매핑이 아닙니다.")

    code = data.get("form")
    if not code:
        raise DraftError(f"{path}: 'form' 이 없습니다. 어느 양식인지 알 수 없습니다.")

    meta = {k: data.get(k) for k in META_KEYS if k != "form"}

    values = data.get("values") or {}
    if not isinstance(values, dict):
        raise DraftError(f"{path}: 'values' 가 매핑이 아닙니다.")

    return str(code), meta, values


# ────────────────────────────── 검증 ──────────────────────────────


def particle(word: str, with_final: str, without_final: str) -> str:
    """받침에 맞는 조사를 고른다. `은/는`, `이/가`, `을/를`.

    오류 메시지는 사람이 읽는 문장이다. "'예상경비' 은 숫자여야" 처럼 조사가 틀리면
    기계가 뱉은 티가 나고, 그 순간부터 사람이 메시지를 안 읽는다.

    한글 음절은 0xAC00 부터 28개 종성 단위로 배열돼 있다 — 나머지가 0이면 받침이 없다.
    한글이 아닌 글자로 끝나면 판단할 수 없으므로 받침 없는 쪽을 쓴다.
    """
    if not word:
        return without_final
    last = word[-1]
    if not ("가" <= last <= "힣"):
        return without_final
    return with_final if (ord(last) - 0xAC00) % 28 else without_final


def _topic(word: str) -> str:
    """'예상경비는' / '출장목적은' 처럼 붙여서 돌려준다."""
    return f"{word}{particle(word, '은', '는')}"


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict)):
        return len(value) == 0
    return False


def validate(template: FormTemplate, values: dict[str, Any]) -> list[str]:
    """문제를 전부 모아 돌려준다. 하나씩 터뜨리면 고치고 다시 돌리기를 반복하게 된다."""
    problems: list[str] = []
    known = {f.key for f in template.fields}

    for key in values:
        if key not in known:
            problems.append(
                f"'{key}'{particle(key, '은', '는')} {template.name}에 없는 항목입니다. "
                "오타일 수 있습니다."
            )

    for f in template.fields:
        raw = values.get(f.key)

        if _is_blank(raw):
            if f.required:
                problems.append(f"{_topic(f.label)} 필수입니다.")
            continue

        if f.type == "select" and str(raw) not in f.options:
            problems.append(
                f"'{f.label}'의 값 '{raw}'{particle(str(raw), '은', '는')} 선택지에 없습니다. "
                f"가능한 값: {', '.join(f.options)}"
            )

        elif f.type == "date" and not isinstance(raw, (dt.date, dt.datetime)):
            try:
                dt.date.fromisoformat(str(raw))
            except ValueError:
                problems.append(f"{_topic(f.label)} 날짜여야 합니다 (YYYY-MM-DD): {raw!r}")

        elif f.type in ("money", "number"):
            try:
                float(raw)
            except (TypeError, ValueError):
                problems.append(f"{_topic(f.label)} 숫자여야 합니다: {raw!r}")

    return problems


def coerce(template: FormTemplate, values: dict[str, Any]) -> dict[str, Any]:
    """검증을 통과한 값을 실제 타입으로 바꾼다. 결재선 조건식이 숫자 비교를 하기 때문이다.

    문자열 "1000000" 과 숫자 1000000 을 구분하지 않으면 `amount > 1000000` 이
    조용히 문자열 비교가 되어 결재선이 틀린다.
    """
    out: dict[str, Any] = {}
    for f in template.fields:
        raw = values.get(f.key)

        if _is_blank(raw):
            out[f.key] = None
            continue

        if f.type == "money":
            out[f.key] = float(raw)
        elif f.type == "number":
            out[f.key] = float(raw)
        elif f.type == "date":
            out[f.key] = raw if isinstance(raw, dt.date) else dt.date.fromisoformat(str(raw))
        elif f.type == "user_list":
            if isinstance(raw, (list, tuple)):
                out[f.key] = [str(i).strip() for i in raw if str(i).strip()]
            else:
                out[f.key] = [p.strip() for p in str(raw).split(",") if p.strip()]
        elif f.type == "checkbox":
            out[f.key] = bool(raw)
        else:
            out[f.key] = str(raw).strip() if isinstance(raw, str) else raw

    return out


def parse_drafted_on(meta: dict[str, Any]) -> dt.date:
    raw = meta.get("drafted_on")
    if isinstance(raw, dt.datetime):
        return raw.date()
    if isinstance(raw, dt.date):
        return raw
    if raw:
        try:
            return dt.date.fromisoformat(str(raw))
        except ValueError as exc:
            raise DraftError(f"drafted_on 을 날짜로 읽을 수 없습니다: {raw!r}") from exc
    return dt.date.today()


def slugify(text: str, fallback: str) -> str:
    """파일명으로 쓸 수 있게 다듬는다. 한글은 그대로 둔다 — 찾을 때 읽혀야 한다."""
    cleaned = "".join(ch if ch.isalnum() or ch in " -_()" else "_" for ch in (text or ""))
    cleaned = "_".join(cleaned.split())
    return cleaned[:60] or fallback


__all__ = [
    "DraftError",
    "FormError",
    "coerce",
    "load_draft",
    "parse_drafted_on",
    "particle",
    "skeleton",
    "slugify",
    "validate",
]
