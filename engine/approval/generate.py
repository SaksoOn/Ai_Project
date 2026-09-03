#!/usr/bin/env python3
"""결재 문서 생성기.

    python3 -m engine.approval.generate list              양식 목록
    python3 -m engine.approval.generate show 출장명령서    필드·결재선 확인
    python3 -m engine.approval.generate new 출장명령서     초안 파일 생성
    python3 -m engine.approval.generate build <초안.yaml>  문서 생성 (HTML + 평문)
    python3 -m engine.approval.generate seal 홍길동        도장 미리보기
    python3 -m engine.approval.generate doctor            환경 진단

흐름:
    new → 편집기에서 값 채움 → build → 평문을 기존 그룹웨어에 붙여넣어 상신
                                    → HTML은 인쇄(Ctrl+P)로 PDF 보관

초안(drafts/)과 결과물(dist/approval/)에는 회사 데이터가 들어간다. 둘 다 gitignore 돼 있다.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

from engine.products.console import FAIL, PASS, configure, pad

from . import document, line as line_module, render, schema, seal

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DRAFTS_DIR = REPO_ROOT / "drafts"
OUT_DIR = REPO_ROOT / "dist" / "approval"


def _templates() -> dict[str, schema.FormTemplate]:
    templates = schema.load_all()
    if not templates:
        raise schema.FormError(
            f"양식이 하나도 없습니다. {schema.FORMS_DIR} 를 확인하세요."
        )
    return templates


# ────────────────────────────── 명령 ──────────────────────────────


def cmd_list() -> int:
    for template in sorted(_templates().values(), key=lambda t: t.name):
        origin = ""
        if template.source and schema.LOCAL_FORMS_DIR in template.source.parents:
            origin = "  [forms.local]"
        print(
            f"  {pad(template.name, 12)} {pad(template.code, 12)} "
            f"필드 {len(template.fields)}개{origin}"
        )
    return 0


def cmd_show(needle: str) -> int:
    template = schema.find(_templates(), needle)

    print(f"\n{template.name} ({template.code}) v{template.version}")
    if template.source:
        print(f"  정의: {template.source}")

    print("\n  필드")
    for f in template.fields:
        mark = "*" if f.required else " "
        extra = f"  [{'/'.join(f.options)}]" if f.options else ""
        hint = f"  — {f.hint}" if f.hint else ""
        print(f"   {mark} {pad(f.label, 12)} {pad(f.key, 12)} {f.type}{extra}{hint}")
    print("     (* 표시는 필수)")

    print("\n  결재선")
    print(f"     기본: {' → '.join(template.default_line)}")
    for rule in template.rules:
        print(f"     {rule.when}  →  {' → '.join(rule.line)}")
    if template.rules:
        print("     (위에서부터 먼저 맞는 규칙이 이깁니다)")
    print()
    return 0


def cmd_new(needle: str, drafts_dir: pathlib.Path) -> int:
    template = schema.find(_templates(), needle)
    text = document.skeleton(template)

    drafts_dir.mkdir(parents=True, exist_ok=True)
    import datetime as dt

    base = f"{template.name}_{dt.date.today().isoformat()}"
    path = drafts_dir / f"{base}.yaml"
    serial = 2
    while path.exists():  # 같은 날 두 번째 문서를 덮어쓰면 안 된다.
        path = drafts_dir / f"{base}_{serial}.yaml"
        serial += 1

    path.write_text(text, encoding="utf-8")
    print(f"{PASS} 초안을 만들었습니다: {path}")
    print("   값을 채운 뒤:")
    print(f"     python3 -m engine.approval.generate build {path}")
    return 0


def cmd_build(draft_path: pathlib.Path, out_dir: pathlib.Path) -> int:
    code, meta_raw, raw_values = document.load_draft(draft_path)
    template = schema.find(_templates(), code)

    problems = document.validate(template, raw_values)
    if problems:
        print(f"{FAIL} {draft_path.name} — 고칠 것이 {len(problems)}건 있습니다:", file=sys.stderr)
        for problem in problems:
            print(f"   - {problem}", file=sys.stderr)
        return 1

    values = document.coerce(template, raw_values)

    try:
        positions = line_module.resolve(template, values)
    except line_module.ConditionError as exc:
        print(f"{FAIL} 결재선을 정할 수 없습니다 — {exc}", file=sys.stderr)
        return 1

    drafted_on = document.parse_drafted_on(meta_raw)
    drafter = str(meta_raw.get("drafter") or "").strip()

    meta = render.DocumentMeta(
        title=str(meta_raw.get("title") or "").strip(),
        drafter=drafter,
        department=str(meta_raw.get("department") or "").strip(),
        drafted_on=drafted_on,
        doc_no=str(meta_raw.get("doc_no") or "").strip(),
        company=str(meta_raw.get("company") or "").strip(),
        # 이름은 비운다 — 결재는 기존 그룹웨어에서 이뤄지고, 여기서 도장을 찍으면
        # 승인되지 않은 문서가 승인된 것처럼 보인다.
        approvers=tuple(render.Approver(position) for position in positions),
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = document.slugify(meta.title, fallback=template.name)
    base = f"{drafted_on.isoformat()}_{template.name}_{stem}"

    html_path = out_dir / f"{base}.html"
    text_path = out_dir / f"{base}.txt"
    html_path.write_text(render.render_html(template, values, meta), encoding="utf-8")
    text_path.write_text(render.render_text(template, values, meta), encoding="utf-8")

    print(f"{PASS} {template.name} 생성 완료")
    print(f"   결재선: {' → '.join((render.DRAFTER_COLUMN, *positions))}")
    print(f"   붙여넣기용: {text_path}")
    print(f"   인쇄·PDF용: {html_path}")
    print("   (HTML을 브라우저로 열고 Ctrl+P → 'PDF로 저장')")
    return 0


def cmd_seal(name: str, out_dir: pathlib.Path) -> int:
    """도장 모양만 확인한다. 문서에는 승인 기록이 있을 때만 찍힌다."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"도장_{document.slugify(name, 'seal')}.html"
    path.write_text(
        '<!doctype html><meta charset="utf-8"><title>도장 미리보기</title>'
        '<body style="display:flex;gap:24px;align-items:center;padding:40px;'
        'font-family:Malgun Gothic,sans-serif">'
        f"{seal.seal_svg(name, size=120)}"
        f"<div><b>{name}</b><br>실제 문서에는 승인 기록이 있을 때만 찍힙니다.</div>"
        "</body>",
        encoding="utf-8",
    )
    print(f"{PASS} {path}")
    return 0


def cmd_doctor(drafts_dir: pathlib.Path, out_dir: pathlib.Path) -> int:
    from . import doctor

    text, ok = doctor.run(drafts_dir, out_dir)
    print(text)
    return 0 if ok else 1


# ────────────────────────────── 진입점 ──────────────────────────────


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m engine.approval.generate",
        description="결재 문서 생성기",
    )
    parser.add_argument(
        "command", choices=["list", "show", "new", "build", "seal", "doctor"]
    )
    parser.add_argument("target", nargs="?", help="양식 이름/코드, 초안 파일 경로, 또는 이름")
    parser.add_argument("--drafts", type=pathlib.Path, default=DRAFTS_DIR)
    parser.add_argument("--out", type=pathlib.Path, default=OUT_DIR)
    args = parser.parse_args(argv)

    needs_target = {"show", "new", "build", "seal"}
    if args.command in needs_target and not args.target:
        parser.error(f"{args.command} 에는 대상이 필요합니다.")

    try:
        if args.command == "list":
            return cmd_list()
        if args.command == "show":
            return cmd_show(args.target)
        if args.command == "new":
            return cmd_new(args.target, args.drafts)
        if args.command == "build":
            return cmd_build(pathlib.Path(args.target), args.out)
        if args.command == "seal":
            return cmd_seal(args.target, args.out)
        return cmd_doctor(args.drafts, args.out)
    except (schema.FormError, document.DraftError) as exc:
        print(f"{FAIL} {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    configure()
    raise SystemExit(main(sys.argv[1:]))
