"""Point-in-time snapshot construction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from apex.identity import snapshot_identity
from apex.market import MarketObservation, pit_filter
from apex.quality import Quality, combine_quality
from apex.time_model import as_of_from_availability, isoformat_utc


@dataclass
class Snapshot:
    snapshot_id: str
    as_of: datetime
    symbol: str
    timeframe: str
    candles: list[dict[str, Any]]
    quality: Quality
    parameter_package: str
    code_version: str
    instrument_metadata_version: str = "meta-1"

    def to_content(self) -> dict[str, Any]:
        return {
            "as_of": isoformat_utc(self.as_of),
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "candles": self.candles,
            "quality": self.quality.value,
            "parameter_package": self.parameter_package,
            "code_version": self.code_version,
            "instrument_metadata_version": self.instrument_metadata_version,
        }


def build_snapshot(
    observations: list[MarketObservation],
    symbol: str,
    timeframe: str,
    parameter_package: str,
    code_version: str,
    as_of: datetime | None = None,
) -> Snapshot:
    admissible = [o for o in observations if o.symbol == symbol and o.timeframe == timeframe]
    if as_of is None:
        if not admissible:
            raise ValueError("no observations for snapshot")
        as_of = as_of_from_availability(o.availability_time for o in admissible)
    pit = [o for o in admissible if pit_filter(o, as_of) and o.closed]
    candles = [o.to_dict() for o in sorted(pit, key=lambda x: x.exchange_event_time)]
    q = combine_quality(o.quality for o in pit) if pit else Quality.INSUFFICIENT_HISTORY
    content = {
        "as_of": isoformat_utc(as_of),
        "symbol": symbol,
        "timeframe": timeframe,
        "candles": candles,
        "quality": q.value,
        "parameter_package": parameter_package,
        "code_version": code_version,
        "instrument_metadata_version": "meta-1",
    }
    sid = snapshot_identity(content)
    return Snapshot(
        snapshot_id=sid,
        as_of=as_of,
        symbol=symbol,
        timeframe=timeframe,
        candles=candles,
        quality=q,
        parameter_package=parameter_package,
        code_version=code_version,
    )
