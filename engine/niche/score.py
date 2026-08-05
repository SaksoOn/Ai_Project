#!/usr/bin/env python3
"""니치 스코어링 하네스 (개발자 도구용).

candidates.yaml의 후보를 결정론적으로 채점해 NICHES.md를 생성한다.

설계 원칙:
  1. 근거 없는 후보는 채점하지 않는다.
  2. 점수는 판단이지 측정값이 아니다. 그래서 evidence와 출처를 항상 함께 출력한다.
  3. 하드 필터는 이미 배운 교훈을 코드로 박아둔 것이다 — 사람이 매번 기억할 필요가 없게.

실행: python3 engine/niche/score.py
"""

from __future__ import annotations

import datetime as dt
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
CANDIDATES = ROOT / "engine" / "niche" / "candidates.yaml"
OUTPUT = ROOT / "NICHES.md"

# 가중치 합 = 1.00
# free_alternative_pressure에 가장 큰 가중치를 준다 — 지난번 실패의 핵심 원인이었다.
WEIGHTS = {
    "pain_frequency": 0.20,
    "free_alternative_pressure": 0.25,  # 역방향
    "willingness_to_pay": 0.20,
    "local_feasibility": 0.10,
    "search_demand": 0.15,
    "maintenance_burden": 0.10,  # 역방향
}

INVERTED = {"free_alternative_pressure", "maintenance_burden"}

# 총점과 무관하게 탈락시킨다.
HARD_FILTERS = [
    ("free_alternative_pressure", "gte", 8,
     "무료로 이미 잘 되는 문제 — 돈 내고 살 이유가 없다"),
    ("local_feasibility", "lte", 4,
     "외부 API·서버가 필요하다 — 운영비가 들고 프라이버시 셀링포인트를 잃는다"),
]

SELECT_TOP_N = 3


def total_score(scores: dict[str, int]) -> float:
    total = 0.0
    for axis, weight in WEIGHTS.items():
        raw = scores[axis]
        total += ((10 - raw) if axis in INVERTED else raw) * weight
    return round(total, 2)


def hard_filter_reason(scores: dict[str, int]) -> str | None:
    for axis, op, threshold, reason in HARD_FILTERS:
        value = scores.get(axis)
        if value is None:
            continue
        hit = value >= threshold if op == "gte" else value <= threshold
        if hit:
            symbol = "≥" if op == "gte" else "≤"
            return f"{reason} ({axis}={value} {symbol} {threshold})"
    return None


def evaluate(candidate: dict) -> dict:
    scores = candidate.get("scores") or {}
    evidence = candidate.get("evidence") or []

    missing = [axis for axis in WEIGHTS if axis not in scores]
    if missing:
        return {**candidate, "excluded": f"점수 누락: {', '.join(missing)}", "total": 0.0}
    if not evidence:
        return {**candidate, "excluded": "근거 없음 — 채점하지 않는다", "total": 0.0}

    reason = hard_filter_reason(scores)
    return {
        **candidate,
        "excluded": f"하드 필터 탈락 — {reason}" if reason else None,
        "total": total_score(scores),
    }


def render(results: list[dict]) -> str:
    passed = sorted((r for r in results if not r["excluded"]),
                    key=lambda r: r["total"], reverse=True)
    rejected = [r for r in results if r["excluded"]]
    selected = passed[:SELECT_TOP_N]
    selected_ids = {r["id"] for r in selected}
    axes = list(WEIGHTS)

    lines = [
        "# 니치 스코어",
        "",
        f"> `engine/niche/score.py` 자동 생성 · 최종 실행 {dt.date.today().isoformat()}",
        "> 점수는 `candidates.yaml`의 근거에 기반한 **판단**이지 측정값이 아니다.",
        "",
        "> ⚠️ 사용자 마찰 목록(`APPROVALS.md` 요청 #1)이 들어오면 그것이 **1순위 후보**가 된다.",
        "> 실제로 겪는 통증은 검증 비용이 0이기 때문이다. 아래는 시장 조사로 뽑은 잠정 후보다.",
        "",
        "## 채택",
        "",
    ]

    if not selected:
        lines += ["_통과한 후보 없음._", ""]
    for rank, r in enumerate(selected, 1):
        lines += [
            f"### {rank}. {r['name']} — **{r['total']}점**",
            "",
            f"- **카테고리:** {r.get('category', '—')}",
            f"- **대상:** {r['target']}",
            f"- **통증:** {r['pain'].strip()}",
            "",
            "**근거**",
            "",
        ]
        for e in r["evidence"]:
            lines.append(f"- {e['claim']}  \n  ↳ {e['source']}")
        if r.get("notes"):
            lines += ["", f"**메모:** {r['notes'].strip()}"]
        lines.append("")

    lines += [
        "## 전체 순위",
        "",
        "| 후보 | 총점 | " + " | ".join(axes) + " | 판정 |",
        "|---|---|" + "---|" * len(axes) + "---|",
    ]
    for r in sorted(results, key=lambda x: x["total"], reverse=True):
        cells = " | ".join(str(r.get("scores", {}).get(a, "—")) for a in axes)
        if r["excluded"]:
            verdict = f"❌ {r['excluded']}"
        elif r["id"] in selected_ids:
            verdict = "✅ 채택"
        else:
            verdict = "⏸ 대기"
        lines.append(f"| {r['name']} | {r['total']} | {cells} | {verdict} |")

    lines += [
        "",
        "> 역방향 축: `free_alternative_pressure`, `maintenance_burden` — 낮을수록 좋다.",
        "> `free_alternative_pressure`에 가장 큰 가중치(0.25)를 뒀다. 지난번 실패의 핵심 원인이었다.",
        "",
        "## 탈락 후보를 남겨두는 이유",
        "",
        "같은 실수를 반복하지 않기 위해서다. **왜 안 되는지**가 기록된 목록이다.",
        "",
    ]
    for r in rejected:
        lines.append(f"- **{r['name']}** — {r['excluded']}")
        if r.get("notes"):
            lines.append(f"  - {r['notes'].strip()}")

    lines += ["", "## 다음 행동", "",
              "1위 후보로 1호 도구를 만든다. 3개를 동시에 착수하지 않는다 — 첫 개는 배우는 과정이다.", ""]
    return "\n".join(lines)


def main() -> int:
    if not CANDIDATES.exists():
        print(f"후보 파일 없음: {CANDIDATES}", file=sys.stderr)
        return 1

    data = yaml.safe_load(CANDIDATES.read_text(encoding="utf-8"))
    candidates = data.get("candidates") or []
    if not candidates:
        print("후보가 비어 있다.", file=sys.stderr)
        return 1

    results = [evaluate(c) for c in candidates]
    OUTPUT.write_text(render(results), encoding="utf-8")

    passed = sorted((r for r in results if not r["excluded"]),
                    key=lambda r: r["total"], reverse=True)
    print(f"후보 {len(results)}개 채점 → 통과 {len(passed)}개, 탈락 {len(results) - len(passed)}개\n")
    for rank, r in enumerate(passed[:SELECT_TOP_N], 1):
        print(f"  채택 {rank}. {r['name']} ({r['total']}점) [{r.get('category', '—')}]")
    for r in results:
        if r["excluded"]:
            print(f"  탈락    {r['name']} — {r['excluded']}")
    print(f"\n→ {OUTPUT.relative_to(ROOT)} 생성")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
