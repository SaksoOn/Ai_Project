"""콘솔 출력 보조.

한국어 Windows 콘솔(cp949)은 ✓ ✗ — 같은 문자를 인코딩하지 못해
UnicodeEncodeError로 죽는다. 이 도구는 Windows 전용이므로 정면으로 만나는 문제다.

특히 `doctor`가 그렇다. "뭐가 왜 안 되는지"를 찍어주려고 만든 명령인데,
그 결과를 찍다가 죽으면 진단 도구로서 존재 이유가 없어진다.

막히는 글자를 하나씩 찾아 고치는 방식은 실패한다 — 본문이 한국어 산문이라
새 문장을 쓸 때마다 지뢰가 늘어난다. 그래서 두 층으로 막는다:

1. `configure()` — 못 찍는 문자는 죽는 대신 대체 문자로 떨어뜨린다. 그물.
2. `OK` / `FAIL` — 성공·실패 표시는 의미를 지고 있어서 '?'가 되면 곤란하다.
   콘솔이 못 찍으면 ASCII로 바꿔 뜻을 지킨다.

UTF-8로 강제 전환하지 않는 이유: 구형 콘솔에서 한글이 통째로 깨진다.
문장부호 몇 개를 포기하는 편이 낫다.
"""

from __future__ import annotations

import codecs
import sys

# 기본 'replace'는 전부 '?'로 만든다. 진단 결과가 '?' 범벅이면 죽지는 않아도
# 읽을 수가 없어서 도구의 목적이 사라진다. 뜻이 남는 ASCII 등가물로 떨어뜨린다.
_ASCII_FALLBACKS = {
    "—": "-", "–": "-", "―": "-",
    "✓": "v", "✗": "x",
    "…": "...", "•": "*", "·": "-",
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "≠": "!=", "→": "->", "←": "<-", "▶": ">", "─": "-",
}

_HANDLER = "daily_log.console.ascii_fallback"


def _ascii_fallback(error: UnicodeError):
    bad = error.object[error.start : error.end]  # type: ignore[attr-defined]
    return "".join(_ASCII_FALLBACKS.get(ch, "?") for ch in bad), error.end  # type: ignore[attr-defined]


codecs.register_error(_HANDLER, _ascii_fallback)


def configure() -> None:
    """진입점에서 한 번 부른다. 인코딩 때문에 죽지 않게 만든다."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors=_HANDLER)
        except (AttributeError, OSError):
            pass  # 파이프로 넘겼거나 이미 감싸진 스트림. 그대로 둔다.


def marks() -> tuple[str, str]:
    """(성공표시, 실패표시). 콘솔이 못 찍는 문자면 ASCII로 떨어진다."""
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        "✓✗".encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return "[v]", "[x]"
    return "✓", "✗"


PASS, FAIL = marks()
