"""결재 도장을 SVG로 그린다.

전 직원의 인감 이미지를 모으는 일이 전자결재 도입에서 가장 큰 마찰이다.
이름만 있으면 도장이 나오게 해서 그 단계를 통째로 없앤다.

**법적으로 유효한 것은 도장 그림이 아니라 '누가 언제 승인했는가'의 기록이다.**
도장은 시각적 관습이므로 여기에 과잉 투자하지 않는다. 실제 인감 이미지를
쓰고 싶으면 나중에 사용자별로 업로드받아 이 함수를 대체하면 된다.

SVG로 만드는 이유: 폰트만 있으면 어떤 해상도로 인쇄해도 안 깨지고,
HTML에 그대로 인라인되므로 이미지 파일 관리가 필요 없다.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

SEAL_COLOR = "#c0392b"  # 인주 빨강

# 글자 수별 크기. 3자(한국 이름 대부분)에서 원 안에 꽉 차 보이도록 맞춘 값이다.
_ONE_LINE_SIZE = {1: 46, 2: 34, 3: 25}
_GRID_SIZE = 26  # 4자를 2x2로 배치할 때
_LONG_NAME_SIZE = 18
_MAX_CHARS = 6  # 이보다 길면 원 안에서 읽을 수 없다


def seal_svg(name: str, *, size: int = 64, color: str = SEAL_COLOR) -> str:
    """이름으로 원형 도장 SVG를 만든다. 빈 이름이면 빈 문자열."""
    text = (name or "").strip()
    if not text:
        return ""

    if len(text) > _MAX_CHARS:
        text = text[:_MAX_CHARS]

    body = _grid(text, color) if len(text) == 4 else _one_line(text, color)

    return (
        f'<svg class="seal" viewBox="0 0 100 100" width="{size}" height="{size}" '
        f'role="img" aria-label="{escape(name)} 도장" xmlns="http://www.w3.org/2000/svg">'
        f'<circle cx="50" cy="50" r="45" fill="none" stroke="{color}" stroke-width="5"/>'
        f"{body}</svg>"
    )


def _text(content: str, x: float, y: float, font_size: int, color: str) -> str:
    return (
        f'<text x="{x}" y="{y}" font-size="{font_size}" fill="{color}" '
        f'text-anchor="middle" dominant-baseline="central" '
        f'font-family="Malgun Gothic, Noto Sans KR, sans-serif" '
        f'font-weight="700">{escape(content)}</text>'
    )


def _one_line(text: str, color: str) -> str:
    font_size = _ONE_LINE_SIZE.get(len(text), _LONG_NAME_SIZE)
    return _text(text, 50, 52, font_size, color)


def _grid(text: str, color: str) -> str:
    """4자는 2x2로. 한 줄로 늘어놓으면 글자가 너무 작아진다.

    한자 인장의 관례는 오른쪽 위 → 오른쪽 아래 → 왼쪽 위 → 왼쪽 아래지만,
    한글 이름을 그렇게 배치하면 읽는 사람이 헷갈린다. 왼→오, 위→아래로 둔다.
    """
    positions = ((33, 35), (67, 35), (33, 67), (67, 67))
    return "".join(
        _text(ch, x, y, _GRID_SIZE, color) for ch, (x, y) in zip(text, positions)
    )
