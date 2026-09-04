"""E01–E12 analyst engines — executable Layer-1 implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.features import compute_feature
from apex.quality import Quality, combine_quality


@dataclass
class EngineOutput:
    engine_id: str
    direction: str
    strength: float
    confidence: float
    quality: Quality
    details: dict[str, Any]


def _dir_from_sign(x: float | None) -> str:
    if x is None:
        return "FLAT"
    if x > 0:
        return "BULLISH"
    if x < 0:
        return "BEARISH"
    return "FLAT"


def run_engines(candles: list[dict]) -> list[EngineOutput]:
    def f(fid: str):
        v, q = compute_feature(fid, candles)
        return v, q

    close, q_close = f("F01")
    sma20, q20 = f("F09")
    sma50, q50 = f("F10")
    rsi, qrsi = f("F15")
    atr, qatr = f("F16")
    z, qz = f("F18")
    vol_ratio, qv = f("F20")
    bos_up, qb = f("F60")
    bos_dn, qbd = f("F61")
    body, qbody = f("F44")
    oi_d, qoi = f("F31")
    macd, qmacd = f("F14")
    stoch, qst = f("F48")
    range_atr, qra = f("F37")

    def emit(eid, direction, strength, conf, qs, details) -> EngineOutput:
        q = combine_quality(qs)
        if q in {Quality.INSUFFICIENT_HISTORY, Quality.UNAVAILABLE, Quality.INVALID, Quality.NOT_ADMITTED}:
            return EngineOutput(eid, "FLAT", 0.0, 0.0, q, details)
        return EngineOutput(eid, direction, float(strength), float(conf), q, details)

    e01 = emit(
        "E01",
        "BULLISH" if (bos_up or 0) > 0 else ("BEARISH" if (bos_dn or 0) > 0 else _dir_from_sign((close or 0) - (sma20 or 0) if close and sma20 else None)),
        abs((close or 0) - (sma20 or 0)) / (sma20 or 1) if close and sma20 else 0,
        0.6 if q20 == Quality.VALID else 0.0,
        [q_close, q20, qb, qbd],
        {"bos_up": bos_up, "bos_dn": bos_dn},
    )
    e02 = emit("E02", _dir_from_sign((vol_ratio or 1) - 1), min(1.0, abs((vol_ratio or 1) - 1)), 0.5, [qv], {"vol_ratio": vol_ratio})
    e03 = emit("E03", _dir_from_sign((vol_ratio or 1) - 1), min(1.0, (vol_ratio or 0) / 3), 0.5, [qv], {"participation": vol_ratio})
    e04 = emit("E04", "FLAT", min(1.0, (range_atr or 0) / 3) if range_atr else 0, 0.5, [qra, qatr], {"atr": atr, "range_atr": range_atr})
    imb = None
    if body is not None:
        imb = body - 0.5
    e05 = emit("E05", _dir_from_sign(imb), abs(imb or 0), 0.45, [qbody], {"body_ratio": body})
    e06 = emit("E06", e01.direction, e01.strength * 0.8, 0.4, [e01.quality], {"structure": e01.direction})
    e07 = emit("E07", e01.direction, e01.strength * 0.7, 0.4, [e01.quality], {"mss": e01.details})
    e08 = emit("E08", e03.direction, e03.strength * 0.6, 0.35, [e03.quality], {"auction": e03.details})
    trend_sign = None
    if sma20 is not None and sma50 is not None:
        trend_sign = sma20 - sma50
    e09 = emit("E09", _dir_from_sign(trend_sign), abs(trend_sign or 0) / (sma50 or 1) if sma50 else 0, 0.7, [q20, q50], {"sma20": sma20, "sma50": sma50})
    e10 = emit("E10", _dir_from_sign((rsi or 50) - 50), abs((rsi or 50) - 50) / 50, 0.65, [qrsi, qmacd], {"rsi": rsi, "macd": macd, "stoch": stoch})
    e11 = emit("E11", "FLAT", min(1.0, abs(z or 0) / 3) if z is not None else 0, 0.55, [qz], {"zscore": z})
    # E12 temporal context: UTC hour bucket only (analytical, not forex session gate)
    hour = 0
    if candles:
        ts = candles[-1].get("exchange_event_time") or ""
        try:
            hour = int(ts[11:13])
        except Exception:
            hour = 0
    e12 = emit("E12", "FLAT", 0.1, 0.3, [q_close], {"utc_hour": hour, "activity_window": hour // 4})
    # OI does not fabricate; include quality in E02 details
    e02.details["oi_delta"] = oi_d
    e02.details["oi_quality"] = qoi.value
    return [e01, e02, e03, e04, e05, e06, e07, e08, e09, e10, e11, e12]
