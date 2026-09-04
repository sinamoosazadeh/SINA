"""Market observation validation, OHLCV+OI, closed-candle policy."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any

from apex.quality import Quality
from apex.time_model import as_utc, isoformat_utc


SUPPORTED_TIMEFRAMES = [
    "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d", "3d", "1w", "1mo",
]


@dataclass
class MarketObservation:
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    open_interest: float | None
    exchange_event_time: datetime
    availability_time: datetime
    ingestion_time: datetime
    received_at: datetime
    closed: bool
    quality: Quality
    oi_quality: Quality
    source: str = "TOOBIT"
    revision: int = 0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for k in ("exchange_event_time", "availability_time", "ingestion_time", "received_at"):
            d[k] = isoformat_utc(d[k])
        d["quality"] = self.quality.value
        d["oi_quality"] = self.oi_quality.value
        return d


def validate_observation(obs: MarketObservation) -> MarketObservation:
    if obs.timeframe not in SUPPORTED_TIMEFRAMES:
        obs.quality = Quality.INVALID
        return obs
    if obs.high < obs.low:
        obs.quality = Quality.INVALID
        return obs
    if obs.close > obs.high or obs.close < obs.low or obs.open > obs.high or obs.open < obs.low:
        obs.quality = Quality.INVALID
        return obs
    if obs.volume < 0:
        obs.quality = Quality.INVALID
        return obs
    if obs.open_interest is None:
        obs.oi_quality = Quality.UNAVAILABLE
    elif obs.open_interest < 0:
        obs.oi_quality = Quality.INVALID
        obs.quality = Quality.DEGRADED
    else:
        obs.oi_quality = Quality.VALID
    if not obs.closed:
        # Open candles may update; they are not immutable historical evidence.
        if obs.quality == Quality.VALID:
            obs.quality = Quality.PENDING
    return obs


def pit_filter(obs: MarketObservation, as_of: datetime) -> bool:
    return as_utc(obs.availability_time) <= as_utc(as_of)
