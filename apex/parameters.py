"""Versioned parameter packages — activation is explicit."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ParameterPackage:
    package_id: str
    version: str
    active: bool
    values: dict
    content_hash: str


DEFAULT = ParameterPackage(
    package_id="pp-default-1",
    version="1",
    active=True,
    values={"fee_bps": 4.0, "slippage_bps": 2.0},
    content_hash="pp-default-1",
)
