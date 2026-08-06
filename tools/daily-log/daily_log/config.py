"""설정 로드.

설정 파일에는 **본인 메일 주소와 부서 주소만** 들어간다.
비밀번호나 접속정보는 필요 없다 — Outlook에 이미 로그인돼 있는 걸 그대로 쓴다.
"""

from __future__ import annotations

import pathlib
import tomllib
from dataclasses import dataclass, field

from .rules import ExclusionConfig, InclusionConfig


@dataclass
class Config:
    inclusion: InclusionConfig = field(default_factory=InclusionConfig)
    exclusion: ExclusionConfig = field(default_factory=ExclusionConfig)
    data_dir: pathlib.Path = pathlib.Path("data")
    queue_dir: pathlib.Path = pathlib.Path("queue")
    report_to: str = ""
    lookback_days: int = 0  # 0이면 오늘만


def _tuple(value) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    return tuple(str(v) for v in (value or []))


def load(path: pathlib.Path) -> Config:
    if not path.exists():
        raise FileNotFoundError(
            f"설정 파일이 없습니다: {path}\n"
            "config.example.toml 을 config.toml 로 복사한 뒤 메일 주소를 채워주세요."
        )
    data = tomllib.loads(path.read_text(encoding="utf-8"))

    me = data.get("me", {})
    collect = data.get("collect", {})
    learn = data.get("learn", {})
    paths = data.get("paths", {})

    my_addresses = _tuple(me.get("email"))
    if not my_addresses or not my_addresses[0].strip():
        raise ValueError("config.toml 의 [me] email 을 채워주세요. 판단 기준의 출발점입니다.")

    base = path.parent
    return Config(
        inclusion=InclusionConfig(
            my_addresses=my_addresses,
            department_addresses=_tuple(me.get("department_addresses")),
            include_sent=bool(collect.get("include_sent", True)),
            include_to=bool(collect.get("include_to", True)),
            include_cc=bool(collect.get("include_cc", False)),
            include_department=bool(collect.get("include_department", True)),
            include_calendar=bool(collect.get("include_calendar", True)),
        ),
        exclusion=ExclusionConfig(
            min_observations=int(learn.get("min_observations", 5)),
            drop_ratio=float(learn.get("drop_ratio", 1.0)),
        ),
        data_dir=base / str(paths.get("data_dir", "data")),
        queue_dir=base / str(paths.get("queue_dir", "queue")),
        report_to=str(data.get("report", {}).get("to", "")),
        lookback_days=int(collect.get("lookback_days", 0)),
    )
