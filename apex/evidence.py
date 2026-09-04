"""Evidence Fabric — 24-field-compatible evidence events."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any

from apex.engines import EngineOutput
from apex.identity import sha256_hex, canonical_dumps
from apex.quality import Quality
from apex.time_model import isoformat_utc, utc_now


@dataclass
class EvidenceEvent:
    evidence_id: str
    engine: str
    symbol: str
    timeframe: str
    event_type: str
    direction: str
    strength: float
    confidence: float
    quality: str
    validity: str
    lifecycle: str
    parameter_version: str
    snapshot_identity: str
    provenance: str
    as_of: str
    created_at: str
    source_lineage: str
    classification: str
    admitted: bool
    pit_ok: bool
    code_version: str
    extra: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def materialize_evidence(
    engines: list[EngineOutput],
    symbol: str,
    timeframe: str,
    snapshot_id: str,
    as_of: datetime,
    parameter_version: str,
    code_version: str,
) -> list[EvidenceEvent]:
    events = []
    now = isoformat_utc(utc_now())
    as_of_s = isoformat_utc(as_of)
    for e in engines:
        payload = {
            "engine": e.engine_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "snapshot": snapshot_id,
            "direction": e.direction,
            "strength": e.strength,
            "as_of": as_of_s,
        }
        eid = sha256_hex(canonical_dumps(payload))
        admitted = e.quality == Quality.VALID
        events.append(
            EvidenceEvent(
                evidence_id=eid,
                engine=e.engine_id,
                symbol=symbol,
                timeframe=timeframe,
                event_type="ENGINE_EVIDENCE",
                direction=e.direction,
                strength=e.strength,
                confidence=e.confidence,
                quality=e.quality.value,
                validity="VALID" if admitted else "NOT_ADMITTED",
                lifecycle="ACTIVE" if admitted else "HELD",
                parameter_version=parameter_version,
                snapshot_identity=snapshot_id,
                provenance=f"engine:{e.engine_id}",
                as_of=as_of_s,
                created_at=now,
                source_lineage="LAYER00->ENGINE",
                classification="NATIVE" if e.engine_id != "E12" else "DERIVED",
                admitted=admitted,
                pit_ok=True,
                code_version=code_version,
                extra=e.details,
            )
        )
    return events
