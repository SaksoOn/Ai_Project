#!/usr/bin/env python3
"""콘솔 출력 보조.

한국어 Windows 콘솔(cp949)은 ✓ ✗ — 같은 문자를 인코딩하지 못해
UnicodeEncodeError로 죽는다. 빌드가 끝난 뒤 결과를 찍는 단계에서 죽기 때문에,
파일은 멀쩡히 만들어졌는데 실패한 것처럼 보인다.

막히는 글자를 하나씩 찾아 고치는 방식은 실패한다 — 본문이 한국어 산문이라
새 문장을 쓸 때마다 지뢰가 늘어난다. 그래서 두 층으로 막는다:

1. `configure()` — 못 찍는 문자는 죽는 대신 대체 문자로 떨어뜨린다. 그물.
2. `PASS` / `FAIL` — 성공·실패 표시는 의미를 지고 있어서 '?'가 되면 곤란하다.
   콘솔이 못 찍으면 ASCII로 바꿔 뜻을 지킨다.

UTF-8로 강제 전환하지 않는 이유: 구형 콘솔에서 한글이 통째로 깨진다.
문장부호 몇 개를 포기하는 편이 낫다.
"""

from __future__ import annotations

import codecs
import sys
import unicodedata

# 기본 'replace'는 전부 '?'로 만든다. 문장부호가 통째로 '?'가 되면 죽지는 않아도
# 읽을 수가 없다. 뜻이 남는 ASCII 등가물로 떨어뜨린다.
_ASCII_FALLBACKS = {
    "—": "-", "–": "-", "―": "-",
    "✓": "v", "✗": "x",
    "…": "...", "•": "*", "·": "-",
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "≠": "!=", "→": "->", "←": "<-", "▶": ">", "─": "-",
}

_HANDLER = "engine.products.console.ascii_fallback"


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


def width(text: str) -> int:
    """터미널에서 차지하는 칸 수. 한글·한자는 두 칸이다.

    `len()`으로 표를 맞추면 한글 열이 전부 어긋난다 — '계출서'는 세 글자지만
    여섯 칸을 쓴다. 목록 출력이 삐뚤어지면 읽는 사람이 열을 잘못 짚는다.
    """
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def pad(text: str, columns: int) -> str:
    """`f"{text:<10}"` 의 한글 안전 버전. 모자라면 오른쪽을 공백으로 채운다."""
    return text + " " * max(0, columns - width(text))
