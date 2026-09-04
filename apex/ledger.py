"""Append-only immutable ledger with hash chain."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from apex.identity import sha256_hex, canonical_dumps
from apex.time_model import isoformat_utc, utc_now


@dataclass
class LedgerEvent:
    sequence: int
    event_id: str
    event_type: str
    entity_id: str
    payload: dict[str, Any]
    timestamp: str
    runtime: str
    prev_hash: str
    event_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Ledger:
    def __init__(self) -> None:
        self._events: list[LedgerEvent] = []

    def append(self, event_type: str, entity_id: str, payload: dict[str, Any], runtime: str) -> LedgerEvent:
        seq = len(self._events) + 1
        prev = self._events[-1].event_hash if self._events else "GENESIS"
        ts = isoformat_utc(utc_now())
        body = {
            "sequence": seq,
            "event_type": event_type,
            "entity_id": entity_id,
            "payload": payload,
            "timestamp": ts,
            "runtime": runtime,
            "prev_hash": prev,
        }
        eh = sha256_hex(canonical_dumps(body))
        ev = LedgerEvent(seq, eh, event_type, entity_id, payload, ts, runtime, prev, eh)
        self._events.append(ev)
        return ev

    def events(self) -> list[LedgerEvent]:
        return list(self._events)

    def verify_chain(self) -> bool:
        prev = "GENESIS"
        for i, ev in enumerate(self._events, start=1):
            if ev.sequence != i:
                return False
            if ev.prev_hash != prev:
                return False
            body = {
                "sequence": ev.sequence,
                "event_type": ev.event_type,
                "entity_id": ev.entity_id,
                "payload": ev.payload,
                "timestamp": ev.timestamp,
                "runtime": ev.runtime,
                "prev_hash": ev.prev_hash,
            }
            if sha256_hex(canonical_dumps(body)) != ev.event_hash:
                return False
            prev = ev.event_hash
        return True

    def load(self, events: list[LedgerEvent]) -> None:
        self._events = list(events)
        if not self.verify_chain():
            raise ValueError("ledger chain invalid")
