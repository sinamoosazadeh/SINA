"""Authoritative runtime-mode model. Fail-closed on ambiguity."""

from __future__ import annotations

from enum import Enum


class RuntimeMode(str, Enum):
    PAPER = "PAPER"
    LIVE = "LIVE"
    RESEARCH = "RESEARCH"
    REPLAY = "REPLAY"
    TEST = "TEST"
    DEVELOPMENT = "DEVELOPMENT"


CAPITAL_MODES = {RuntimeMode.PAPER, RuntimeMode.LIVE}


class RuntimeModeError(Exception):
    pass


def parse_runtime_mode(raw: str | None) -> RuntimeMode:
    if raw is None or not str(raw).strip():
        return RuntimeMode.PAPER
    value = str(raw).strip().upper()
    if "+" in value or "," in value or " " in value:
        raise RuntimeModeError(f"ambiguous runtime mode: {raw!r}")
    try:
        mode = RuntimeMode(value)
    except ValueError as exc:
        raise RuntimeModeError(f"unknown runtime mode: {raw!r}") from exc
    return mode


def assert_paper_live_isolation(mode: RuntimeMode, adapter_kind: str) -> None:
    kind = adapter_kind.upper()
    if mode == RuntimeMode.PAPER and kind == "LIVE":
        raise RuntimeModeError("PAPER runtime cannot bind LIVE execution adapter")
    if mode == RuntimeMode.LIVE and kind == "PAPER":
        raise RuntimeModeError("LIVE runtime cannot bind PAPER execution adapter")
    if kind not in {"PAPER", "LIVE", "REPLAY", "TEST"}:
        raise RuntimeModeError(f"unknown execution adapter: {adapter_kind!r}")
