"""Data quality taxonomy and conservative propagation."""

from __future__ import annotations

from enum import Enum
from typing import Iterable


class Quality(str, Enum):
    VALID = "VALID"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    MISSING = "MISSING"
    INVALID = "INVALID"
    UNAVAILABLE = "UNAVAILABLE"
    CORRUPTED = "CORRUPTED"
    OUT_OF_ORDER = "OUT_OF_ORDER"
    DUPLICATE = "DUPLICATE"
    PENDING = "PENDING"
    NOT_ADMITTED = "NOT_ADMITTED"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"


BLOCKING = {
    Quality.MISSING,
    Quality.INVALID,
    Quality.UNAVAILABLE,
    Quality.CORRUPTED,
    Quality.NOT_ADMITTED,
    Quality.INSUFFICIENT_HISTORY,
}


def combine_quality(values: Iterable[Quality]) -> Quality:
    items = list(values)
    if not items:
        return Quality.UNAVAILABLE
    rank = [
        Quality.CORRUPTED,
        Quality.INVALID,
        Quality.NOT_ADMITTED,
        Quality.UNAVAILABLE,
        Quality.MISSING,
        Quality.INSUFFICIENT_HISTORY,
        Quality.OUT_OF_ORDER,
        Quality.STALE,
        Quality.DUPLICATE,
        Quality.PENDING,
        Quality.DEGRADED,
        Quality.VALID,
    ]
    for q in rank:
        if q in items:
            return q
    return Quality.VALID


def is_admissible(q: Quality) -> bool:
    return q not in BLOCKING
