"""Operational Pattern Registry — admitted vs known/not-admitted."""

from __future__ import annotations

from dataclasses import dataclass

from apex.engines import EngineOutput
from apex.quality import Quality


@dataclass(frozen=True)
class PatternEntity:
    pat_id: str
    name: str
    family: str
    admission: str  # RUNTIME_ADMITTED | KNOWN_NOT_ADMITTED | RESEARCH_ONLY | EXCLUDED
    required_engines: tuple[str, ...]


OPERATIONAL_PATTERNS = [
    PatternEntity("PAT01", "BOS_CONTINUATION", "STRUCTURE", "RUNTIME_ADMITTED", ("E01", "E09")),
    PatternEntity("PAT02", "CHOCH_REVERSAL", "STRUCTURE", "RUNTIME_ADMITTED", ("E01", "E10")),
    PatternEntity("PAT03", "LIQUIDITY_SWEEP", "LIQUIDITY", "RUNTIME_ADMITTED", ("E02", "E01")),
    PatternEntity("PAT04", "FVG_IMBALANCE", "IMBALANCE", "RUNTIME_ADMITTED", ("E05",)),
    PatternEntity("PAT05", "ORDER_BLOCK", "ORDER_BLOCK", "RUNTIME_ADMITTED", ("E06",)),
    PatternEntity("PAT06", "TREND_PULLBACK", "TREND", "RUNTIME_ADMITTED", ("E09", "E10")),
    PatternEntity("PAT07", "MOMENTUM_BREAK", "MOMENTUM", "RUNTIME_ADMITTED", ("E10",)),
    PatternEntity("PAT08", "VOL_EXPANSION", "VOLATILITY", "RUNTIME_ADMITTED", ("E04", "E11")),
    PatternEntity("PAT09", "WYCKOFF_SPRING", "WYCKOFF", "KNOWN_NOT_ADMITTED", ("E08",)),
    PatternEntity("PAT10", "ICEBERG", "MICROSTRUCTURE", "KNOWN_NOT_ADMITTED", ()),
    PatternEntity("PAT11", "SPOOFING", "MICROSTRUCTURE", "EXCLUDED", ()),
    PatternEntity("PAT12", "FUNDING_SQUEEZE", "FUNDING", "EXCLUDED", ()),
]


def detect_patterns(engines: list[EngineOutput]) -> list[dict]:
    by_id = {e.engine_id: e for e in engines}
    out = []
    for p in OPERATIONAL_PATTERNS:
        if p.admission != "RUNTIME_ADMITTED":
            out.append({"pat_id": p.pat_id, "name": p.name, "admission": p.admission, "active": False, "quality": Quality.NOT_ADMITTED.value})
            continue
        missing = [eid for eid in p.required_engines if by_id.get(eid) is None or by_id[eid].quality != Quality.VALID]
        if missing:
            out.append({"pat_id": p.pat_id, "name": p.name, "admission": p.admission, "active": False, "quality": Quality.UNAVAILABLE.value, "missing": missing})
            continue
        dirs = [by_id[eid].direction for eid in p.required_engines]
        aligned = len(set(dirs)) == 1 and dirs[0] != "FLAT"
        strength = min(by_id[eid].strength for eid in p.required_engines)
        out.append({
            "pat_id": p.pat_id,
            "name": p.name,
            "admission": p.admission,
            "active": aligned,
            "direction": dirs[0] if aligned else "FLAT",
            "strength": strength if aligned else 0.0,
            "quality": Quality.VALID.value,
        })
    return out
