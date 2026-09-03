"""양식 정의를 읽고 검증한다.

품의·기안·계출·출장명령서는 **필드만 다르고 결재 메커니즘은 같다.** 양식을 코드로
짜면 새 양식마다 코드를 고쳐야 하고 규정이 바뀔 때마다 배포해야 한다. YAML로 두면
양식 추가가 파일 하나 추가가 된다.

검증을 로드 시점에 몰아넣는 이유: 문서를 만드는 순간에 터지면 이미 값을 다 채운
뒤다. 양식이 깨졌다는 건 문서와 무관하게 항상 참이므로 미리 알려주는 게 맞다.

**forms.local/ 이 forms/ 를 덮어쓴다.** 저장소에는 일반적인 표준 양식만 두고,
사내 실제 규정(금액 기준·직위명)은 gitignore된 forms.local/ 에 둔다.
`README.md`의 "회사 데이터를 저장소에 올리지 않는다" 원칙을 지키기 위한 장치다.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field as dc_field
from typing import Any

import yaml

from . import line as line_module

# 필드 타입. 렌더러가 아는 것만 허용한다 — 오타가 조용히 text로 처리되면
# 금액이 콤마 없이 찍히고 날짜가 정렬되지 않는다.
FIELD_TYPES = frozenset(
    {"text", "textarea", "date", "money", "number", "select", "user_list", "checkbox"}
)

FORMS_DIR = pathlib.Path(__file__).resolve().parent / "forms"
LOCAL_FORMS_DIR = pathlib.Path(__file__).resolve().parents[2] / "forms.local"


class FormError(ValueError):
    """양식 정의가 잘못됐다."""


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    type: str
    required: bool = False
    options: tuple[str, ...] = ()
    rows: int = 4
    hint: str = ""

    @property
    def full_width(self) -> bool:
        """본문에서 한 줄을 통째로 쓰는 필드. 서술형은 라벨 옆에 두면 못 읽는다."""
        return self.type == "textarea"


@dataclass(frozen=True)
class ApprovalRule:
    when: str
    line: tuple[str, ...]
    condition: Any = dc_field(repr=False, default=None)  # compile_condition 결과


@dataclass(frozen=True)
class FormTemplate:
    code: str
    name: str
    version: int
    fields: tuple[Field, ...]
    default_line: tuple[str, ...]
    rules: tuple[ApprovalRule, ...] = ()
    source: pathlib.Path | None = None

    def field(self, key: str) -> Field | None:
        for f in self.fields:
            if f.key == key:
                return f
        return None


def _require(mapping: dict, key: str, where: str) -> Any:
    if key not in mapping or mapping[key] in (None, "", []):
        raise FormError(f"{where}: '{key}' 가 없습니다.")
    return mapping[key]


def _parse_field(raw: Any, where: str, index: int) -> Field:
    if not isinstance(raw, dict):
        raise FormError(f"{where}: fields[{index}] 가 매핑이 아닙니다.")

    key = str(_require(raw, "key", f"{where} fields[{index}]"))
    label = str(_require(raw, "label", f"{where} fields[{index}]"))
    ftype = str(_require(raw, "type", f"{where} fields[{index}] ({label})"))

    if ftype not in FIELD_TYPES:
        raise FormError(
            f"{where}: '{label}' 의 타입 '{ftype}' 을 모릅니다. "
            f"쓸 수 있는 것: {', '.join(sorted(FIELD_TYPES))}"
        )

    options = tuple(str(o) for o in raw.get("options") or ())
    if ftype == "select" and not options:
        raise FormError(f"{where}: select 필드 '{label}' 에 options 가 없습니다.")

    return Field(
        key=key,
        label=label,
        type=ftype,
        required=bool(raw.get("required", False)),
        options=options,
        rows=int(raw.get("rows", 4)),
        hint=str(raw.get("hint", "")),
    )


def parse(data: dict, source: pathlib.Path | None = None) -> FormTemplate:
    """딕셔너리를 양식으로. 검증 실패는 전부 FormError."""
    where = str(source) if source else "<양식>"

    if not isinstance(data, dict):
        raise FormError(f"{where}: 최상위가 매핑이 아닙니다.")

    code = str(_require(data, "code", where))
    name = str(_require(data, "name", where))
    version = int(data.get("version", 1))
    if version < 1:
        raise FormError(f"{where}: version 은 1 이상이어야 합니다.")

    raw_fields = _require(data, "fields", where)
    if not isinstance(raw_fields, list):
        raise FormError(f"{where}: fields 가 목록이 아닙니다.")

    fields = tuple(_parse_field(r, where, i) for i, r in enumerate(raw_fields))

    seen: set[str] = set()
    for f in fields:
        if f.key in seen:
            # 같은 key가 둘이면 뒤엣것이 앞엣것을 덮어써서 한 칸이 조용히 사라진다.
            raise FormError(f"{where}: 필드 key '{f.key}' 가 중복입니다.")
        seen.add(f.key)

    raw_line = _require(data, "approval_line", where)
    if not isinstance(raw_line, dict):
        raise FormError(f"{where}: approval_line 이 매핑이 아닙니다.")

    default_line = tuple(str(p) for p in _require(raw_line, "default", f"{where} approval_line"))

    rules: list[ApprovalRule] = []
    for i, raw_rule in enumerate(raw_line.get("rules") or ()):
        rule_where = f"{where} approval_line.rules[{i}]"
        if not isinstance(raw_rule, dict):
            raise FormError(f"{rule_where}: 매핑이 아닙니다.")

        when = str(_require(raw_rule, "when", rule_where))
        rule_line = tuple(str(p) for p in _require(raw_rule, "line", rule_where))

        try:
            condition = line_module.compile_condition(when)
        except line_module.ConditionError as exc:
            raise FormError(f"{rule_where}: {exc}") from exc

        unknown = line_module.condition_names(condition) - seen
        if unknown:
            # 여기서 안 잡으면 문서를 만드는 순간에야 터진다. 그때는 이미 늦다.
            raise FormError(
                f"{rule_where}: 조건식이 없는 필드를 참조합니다: {', '.join(sorted(unknown))}"
            )

        rules.append(ApprovalRule(when=when, line=rule_line, condition=condition))

    return FormTemplate(
        code=code,
        name=name,
        version=version,
        fields=fields,
        default_line=default_line,
        rules=tuple(rules),
        source=source,
    )


def load_file(path: pathlib.Path) -> FormTemplate:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise FormError(f"{path}: YAML 을 읽을 수 없습니다 — {exc}") from exc
    return parse(data, source=path)


def load_all(
    forms_dir: pathlib.Path | None = None,
    local_dir: pathlib.Path | None = None,
) -> dict[str, FormTemplate]:
    """양식을 전부 읽는다. code 를 키로 돌려준다.

    forms.local/ 에 같은 code 가 있으면 그쪽이 이긴다. 사내 실제 규정을
    저장소에 올리지 않고도 쓰기 위한 통로다.
    """
    forms_dir = FORMS_DIR if forms_dir is None else forms_dir
    local_dir = LOCAL_FORMS_DIR if local_dir is None else local_dir

    templates: dict[str, FormTemplate] = {}
    for directory in (forms_dir, local_dir):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.yaml")):
            template = load_file(path)
            templates[template.code] = template
    return templates


def find(templates: dict[str, FormTemplate], needle: str) -> FormTemplate:
    """코드('TRIP_ORDER')로도 이름('출장명령서')으로도 찾게 한다.

    쓰는 사람은 양식을 이름으로 부른다. 코드를 외우게 하면 안 쓴다.
    """
    if needle in templates:
        return templates[needle]

    upper = needle.upper()
    if upper in templates:
        return templates[upper]

    matches = [t for t in templates.values() if t.name == needle]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        codes = ", ".join(t.code for t in matches)
        raise FormError(f"'{needle}' 이름의 양식이 여럿입니다: {codes}. 코드로 지정하세요.")

    known = ", ".join(f"{t.code}({t.name})" for t in templates.values()) or "(없음)"
    raise FormError(f"'{needle}' 양식을 찾을 수 없습니다. 있는 것: {known}")
