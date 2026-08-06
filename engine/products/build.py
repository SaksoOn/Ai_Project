#!/usr/bin/env python3
"""개인 도구 시트를 빌드한다.

실행: python3 -m engine.products.build [시트ID ...]
"""

from __future__ import annotations

import importlib
import pathlib
import sys
import traceback

ROOT = pathlib.Path(__file__).resolve().parents[2]
DIST = ROOT / "dist"

SHEETS: dict[str, tuple[str, str]] = {
    # id: (모듈명, 산출 파일명)
    "trade-review": ("trade_review", "매매복기.xlsx"),
    "work-inventory": ("work_inventory", "반복업무_인벤토리.xlsx"),
}


def build_one(sheet_id: str) -> tuple[bool, str]:
    module_name, filename = SHEETS[sheet_id]
    try:
        module = importlib.import_module(f"engine.products.sheets.{module_name}")
    except ModuleNotFoundError:
        return False, f"미구현 — engine/products/sheets/{module_name}.py 없음"

    try:
        wb = module.build()
    except Exception:
        return False, "빌드 실패\n" + traceback.format_exc(limit=6)

    out = DIST / filename
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return True, f"{out.relative_to(ROOT)} ({out.stat().st_size / 1024:.0f} KB)"


def main(argv: list[str]) -> int:
    targets = [s for s in SHEETS if not argv or s in argv]
    if not targets:
        print(f"해당 시트 없음: {', '.join(argv)}", file=sys.stderr)
        return 1

    failed = []
    for sheet_id in targets:
        ok, detail = build_one(sheet_id)
        print(f"{'✓' if ok else '✗'} {sheet_id}\n    {detail}")
        if not ok:
            failed.append(sheet_id)

    print(f"\n빌드 {len(targets) - len(failed)}/{len(targets)} 성공")
    if failed:
        print("실패: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
