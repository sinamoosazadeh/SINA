"""End-to-end PAPER decision pipeline."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from apex.config import ApexConfig
from apex.engines import run_engines
from apex.evidence import materialize_evidence
from apex.execution import PaperOrder, PaperExecutionAdapter, OrderState
from apex.features import compute_all_features
from apex.ledger import Ledger
from apex.market import MarketObservation
from apex.patterns import detect_patterns
from apex.persistence import Database
from apex.quality import Quality
from apex.risk import evaluate_risk
from apex.setup_strategy import evaluate_setups, propose_strategy
from apex.snapshot import build_snapshot
from apex.time_model import as_utc


@dataclass
class Position:
    position_id: str
    symbol: str
    quantity: float
    avg_entry: float
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    fees: float = 0.0
    slippage: float = 0.0


class PaperRuntime:
    def __init__(self, config: ApexConfig, db: Database):
        self.config = config
        self.db = db
        self.ledger = Ledger()
        existing = db.load_ledger()
        if existing:
            from apex.ledger import LedgerEvent
            evs = [LedgerEvent(**e) for e in existing]
            self.ledger.load(evs)
        self.adapter = PaperExecutionAdapter()
        self.equity = 10_000.0
        self.position: Position | None = None
        self.last_decision: dict[str, Any] | None = None
        self.health = {
            "process": "healthy",
            "database": "healthy",
            "market_data": "unknown",
            "telegram": "degraded" if not config.telegram_token else "healthy",
            "ledger": "healthy" if self.ledger.verify_chain() else "unhealthy",
            "runtime_mode": config.runtime_mode.value,
        }

    def overall_health(self) -> str:
        vals = [v for k, v in self.health.items() if k != "runtime_mode"]
        if "unhealthy" in vals:
            return "UNHEALTHY"
        if "degraded" in vals or "unknown" in vals:
            return "DEGRADED"
        return "HEALTHY"

    def status(self) -> dict[str, Any]:
        return {
            "runtime_mode": self.config.runtime_mode.value,
            "health": self.overall_health(),
            "symbol": self.config.symbols[0],
            "equity": self.equity,
            "kill_switch": self.db.kill_switch_active(),
            "execution_adapter": self.adapter.kind,
            "exchange": self.config.exchange,
        }

    def ingest_and_decide(self, observations: list[MarketObservation]) -> dict[str, Any]:
        for o in observations:
            self.db.insert_observation(o.to_dict())
        self.health["market_data"] = "healthy"
        snap = build_snapshot(
            observations,
            self.config.symbols[0],
            observations[-1].timeframe if observations else "1h",
            self.config.parameter_package,
            self.config.code_version,
        )
        self.db.put_json("snapshots", "snapshot_id", snap.snapshot_id, snap.to_content() | {"snapshot_id": snap.snapshot_id})
        features = compute_all_features(snap.candles)
        self.db.put_json("feature_state", "snapshot_id", snap.snapshot_id, features)
        engines = run_engines(snap.candles)
        evidence = materialize_evidence(
            engines,
            snap.symbol,
            snap.timeframe,
            snap.snapshot_id,
            snap.as_of,
            self.config.parameter_package,
            self.config.code_version,
        )
        for ev in evidence:
            self.db.put_json("evidence_events", "evidence_id", ev.evidence_id, ev.to_dict())
        patterns = detect_patterns(engines)
        for p in patterns:
            self.db.put_json("patterns", "pat_id", p["pat_id"], p)
        closed = all(c.get("closed", True) for c in snap.candles) if snap.candles else False
        setups = evaluate_setups(patterns, snap.quality.value, closed=True)
        for s in setups:
            self.db.put_json("setups", "setup_id", s.setup_id, s.to_dict())
        proposal = propose_strategy(setups, snap.snapshot_id)
        if proposal:
            self.db.put_json("strategy_proposals", "proposal_id", proposal.proposal_id, proposal.to_dict())
            self.db.put_json("forecasts", "forecast_id", proposal.proposal_id, {
                "probability": proposal.probability,
                "uncertainty": proposal.uncertainty,
                "confidence": proposal.confidence,
                "model_type": "deterministic_baseline",
                "training_status": "none",
            })
        last_close = snap.candles[-1]["close"] if snap.candles else 0.0
        risk = evaluate_risk(
            proposal,
            kill_switch=self.db.kill_switch_active(),
            requested_qty=0.01 if proposal and proposal.eligible else 0.0,
            price=last_close or 0.0,
            max_position_qty=self.config.max_position_qty,
            max_exposure=self.config.max_exposure,
            max_allocation=self.config.max_allocation,
            equity=self.equity,
            ledger_healthy=self.ledger.verify_chain(),
            adapter_kind=self.adapter.kind,
            duplicate=False,
            quality_ok=snap.quality == Quality.VALID,
        )
        self.db.put_json("risk_decisions", "risk_decision_id", risk.risk_decision_id, risk.to_dict())
        self._ledger("RISK", risk.risk_decision_id, risk.to_dict())
        order_payload = None
        fill_payload = None
        if risk.status in {"ALLOW", "REDUCE"} and proposal and risk.quantity > 0:
            oid = f"ORD-{snap.snapshot_id[:16]}"
            order = PaperOrder(
                order_id=oid,
                symbol=snap.symbol,
                side="BUY" if proposal.direction == "BULLISH" else "SELL",
                quantity=risk.quantity,
            )
            order.transition(OrderState.READY)
            order.transition(OrderState.ARMED)
            order.transition(OrderState.TRIGGERED)
            order.transition(OrderState.EXECUTING)
            order.transition(OrderState.ACKNOWLEDGED)
            order = self.adapter.simulate_fill(
                order, last_close, risk.quantity, self.config.fee_bps, self.config.slippage_bps, last_close
            )
            if order.state == OrderState.FILLED:
                order.transition(OrderState.PROTECTED)
                order.transition(OrderState.MANAGED)
                order.transition(OrderState.CLOSED)
                order.transition(OrderState.SETTLED)
                order.transition(OrderState.RECONCILED)
            self.db.put_json("paper_orders", "order_id", order.order_id, {
                "order_id": order.order_id,
                "state": order.state.value,
                "qty": order.quantity,
                "filled": order.filled_qty,
                "avg_price": order.avg_price,
                "fees": order.fees,
                "slippage": order.slippage,
                "side": order.side,
            })
            fill_payload = {
                "fill_id": f"FILL-{order.order_id}",
                "qty": order.filled_qty,
                "price": order.avg_price,
                "fees": order.fees,
                "slippage": order.slippage,
            }
            self.db.put_json("fills", "fill_id", fill_payload["fill_id"], fill_payload)
            self._apply_fill(order)
            self._ledger("ORDER", order.order_id, {"state": order.state.value})
            self._ledger("FILL", fill_payload["fill_id"], fill_payload)
            order_payload = {"order_id": order.order_id, "state": order.state.value}
        decision = {
            "decision_id": f"DEC-{snap.snapshot_id[:16]}",
            "snapshot_id": snap.snapshot_id,
            "as_of": snap.as_of.isoformat(),
            "symbol": snap.symbol,
            "timeframe": snap.timeframe,
            "features_ok": True,
            "engines": [e.engine_id for e in engines],
            "proposal": proposal.to_dict() if proposal else None,
            "risk": risk.to_dict(),
            "order": order_payload,
            "fill": fill_payload,
            "position": asdict(self.position) if self.position else None,
            "equity": self.equity,
            "parameter_package": self.config.parameter_package,
            "code_version": self.config.code_version,
        }
        self.last_decision = decision
        self._ledger("DECISION", decision["decision_id"], {"snapshot_id": snap.snapshot_id, "risk": risk.status})
        return decision

    def _apply_fill(self, order: PaperOrder) -> None:
        signed = order.filled_qty if order.side == "BUY" else -order.filled_qty
        if self.position is None:
            self.position = Position(
                position_id=f"POS-{order.order_id}",
                symbol=order.symbol,
                quantity=signed,
                avg_entry=order.avg_price,
                fees=order.fees,
                slippage=order.slippage,
            )
        else:
            self.position.quantity += signed
            self.position.fees += order.fees
            self.position.slippage += order.slippage
        self.equity -= order.fees
        if self.position:
            self.db.put_json("positions", "position_id", self.position.position_id, asdict(self.position))
            import json as _json
            self.db.conn.execute(
                "INSERT INTO pnl(payload) VALUES (?)",
                (
                    _json.dumps(
                        {
                            "equity": self.equity,
                            "fees": self.position.fees,
                            "realized": self.position.realized_pnl,
                        },
                        sort_keys=True,
                    ),
                ),
            )
            self.db.conn.commit()

    def _ledger(self, typ: str, eid: str, payload: dict) -> None:
        ev = self.ledger.append(typ, eid, payload, self.config.runtime_mode.value)
        self.db.append_ledger(ev.sequence, ev.event_id, ev.to_dict())

    def restore(self) -> None:
        if not self.ledger.verify_chain():
            self.health["ledger"] = "unhealthy"
            raise RuntimeError("ledger unhealthy")
        self.health["ledger"] = "healthy"
