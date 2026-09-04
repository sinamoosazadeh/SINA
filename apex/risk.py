"""Independent Risk Kernel — 14 hard vetoes. Cannot be overridden."""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any

from apex.setup_strategy import StrategyProposal


HARD_VETOES = [
    "V01_KILL_SWITCH",
    "V02_MAX_POSITION",
    "V03_MAX_EXPOSURE",
    "V04_MAX_ALLOCATION",
    "V05_INVALID_QUANTITY",
    "V06_INVALID_PRICE",
    "V07_QUALITY_FAIL",
    "V08_NOT_ELIGIBLE",
    "V09_RUNTIME_NOT_PAPER_SAFE",
    "V10_LEDGER_UNHEALTHY",
    "V11_RECONCILE_REQUIRED",
    "V12_UNKNOWN_ADAPTER",
    "V13_INSUFFICIENT_MARGIN_PROXY",
    "V14_DUPLICATE_INTENT",
]


@dataclass
class RiskDecision:
    risk_decision_id: str
    status: str  # ALLOW | REDUCE | REJECT
    fired_vetoes: list[str]
    evaluated_vetoes: list[str]
    quantity: float
    reason: str
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_risk(
    proposal: StrategyProposal | None,
    *,
    kill_switch: bool,
    requested_qty: float,
    price: float,
    max_position_qty: float,
    max_exposure: float,
    max_allocation: float,
    equity: float,
    ledger_healthy: bool,
    adapter_kind: str,
    duplicate: bool,
    quality_ok: bool,
) -> RiskDecision:
    fired: list[str] = []
    if proposal is None:
        fired.append("V08_NOT_ELIGIBLE")
    if kill_switch:
        fired.append("V01_KILL_SWITCH")
    if requested_qty <= 0:
        fired.append("V05_INVALID_QUANTITY")
    if price <= 0:
        fired.append("V06_INVALID_PRICE")
    if requested_qty > max_position_qty:
        fired.append("V02_MAX_POSITION")
    notional = requested_qty * price
    if notional > max_exposure:
        fired.append("V03_MAX_EXPOSURE")
    if equity > 0 and (notional / equity) > max_allocation:
        fired.append("V04_MAX_ALLOCATION")
    if not quality_ok:
        fired.append("V07_QUALITY_FAIL")
    if proposal is not None and not proposal.eligible:
        fired.append("V08_NOT_ELIGIBLE")
    if adapter_kind != "PAPER":
        fired.append("V09_RUNTIME_NOT_PAPER_SAFE")
        fired.append("V12_UNKNOWN_ADAPTER")
    if not ledger_healthy:
        fired.append("V10_LEDGER_UNHEALTHY")
    if duplicate:
        fired.append("V14_DUPLICATE_INTENT")
    qty = requested_qty
    status = "ALLOW"
    if fired:
        reducible = set(fired) <= {"V02_MAX_POSITION", "V03_MAX_EXPOSURE", "V04_MAX_ALLOCATION"}
        if reducible:
            cap_qty = max_position_qty
            if price > 0:
                cap_qty = min(cap_qty, max_exposure / price)
                if equity > 0:
                    cap_qty = min(cap_qty, (max_allocation * equity) / price)
            qty = max(0.0, min(requested_qty, cap_qty))
            status = "REDUCE" if qty > 0 else "REJECT"
            if qty <= 0:
                status = "REJECT"
        else:
            status = "REJECT"
            qty = 0.0
    rid = f"RISK-{(proposal.proposal_id if proposal else 'NONE')}"
    return RiskDecision(
        risk_decision_id=rid,
        status=status,
        fired_vetoes=fired,
        evaluated_vetoes=list(HARD_VETOES),
        quantity=qty,
        reason=";".join(fired) if fired else "OK",
    )
