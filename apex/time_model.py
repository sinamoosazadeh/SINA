"""UTC-only runtime time model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def as_of_from_availability(times: Iterable[datetime]) -> datetime:
    values = [as_utc(t) for t in times]
    if not values:
        raise ValueError("as_of requires at least one availability_time")
    return max(values)


def isoformat_utc(dt: datetime) -> str:
    return as_utc(dt).isoformat().replace("+00:00", "Z")
