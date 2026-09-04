"""Canonical non-finite policy: never coerce NaN/Inf/None to 0."""

from __future__ import annotations

import math
from typing import Any

from apex.quality import Quality


class BoundaryValue:
    def __init__(self, kind: str, value: Any = None, quality: Quality = Quality.UNAVAILABLE):
        self.kind = kind
        self.value = value
        self.quality = quality

    def is_value(self) -> bool:
        return self.kind == "VALUE"


def sanitize_number(value: Any) -> BoundaryValue:
    if value is None:
        return BoundaryValue("UNAVAILABLE", None, Quality.UNAVAILABLE)
    if isinstance(value, bool):
        return BoundaryValue("INVALID", value, Quality.INVALID)
    try:
        num = float(value)
    except (TypeError, ValueError):
        return BoundaryValue("INVALID", value, Quality.INVALID)
    if math.isnan(num):
        return BoundaryValue("INVALID", None, Quality.INVALID)
    if math.isinf(num):
        return BoundaryValue("INVALID", None, Quality.INVALID)
    return BoundaryValue("VALUE", num, Quality.VALID)
