"""PAPER execution FSM, fills, fees, slippage — never submits live orders."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class OrderState(str, Enum):
    IDLE = "IDLE"
    READY = "READY"
    ARMED = "ARMED"
    TRIGGERED = "TRIGGERED"
    EXECUTING = "EXECUTING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    PROTECTED = "PROTECTED"
    MANAGED = "MANAGED"
    CLOSED = "CLOSED"
    SETTLED = "SETTLED"
    RECONCILED = "RECONCILED"
    ARCHIVED = "ARCHIVED"
    INVALIDATED = "INVALIDATED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    CANCEL_PENDING = "CANCEL_PENDING"
    CANCELLED = "CANCELLED"


ALLOWED_TRANSITIONS: dict[OrderState, set[OrderState]] = {
    OrderState.IDLE: {OrderState.READY, OrderState.REJECTED, OrderState.INVALIDATED},
    OrderState.READY: {OrderState.ARMED, OrderState.REJECTED, OrderState.INVALIDATED},
    OrderState.ARMED: {OrderState.TRIGGERED, OrderState.CANCEL_PENDING, OrderState.INVALIDATED},
    OrderState.TRIGGERED: {OrderState.EXECUTING, OrderState.REJECTED},
    OrderState.EXECUTING: {OrderState.ACKNOWLEDGED, OrderState.UNKNOWN, OrderState.RECOVERY_REQUIRED},
    OrderState.ACKNOWLEDGED: {OrderState.PARTIAL, OrderState.FILLED, OrderState.CANCEL_PENDING},
    OrderState.PARTIAL: {OrderState.PARTIAL, OrderState.FILLED, OrderState.CANCEL_PENDING, OrderState.RECOVERY_REQUIRED},
    OrderState.FILLED: {OrderState.PROTECTED},
    OrderState.PROTECTED: {OrderState.MANAGED},
    OrderState.MANAGED: {OrderState.CLOSED},
    OrderState.CLOSED: {OrderState.SETTLED},
    OrderState.SETTLED: {OrderState.RECONCILED},
    OrderState.RECONCILED: {OrderState.ARCHIVED},
    OrderState.CANCEL_PENDING: {OrderState.CANCELLED, OrderState.RECOVERY_REQUIRED},
    OrderState.CANCELLED: {OrderState.RECONCILED},
    OrderState.REJECTED: {OrderState.ARCHIVED},
    OrderState.INVALIDATED: {OrderState.ARCHIVED},
    OrderState.UNKNOWN: {OrderState.RECOVERY_REQUIRED},
    OrderState.RECOVERY_REQUIRED: {OrderState.RECONCILED, OrderState.REJECTED},
    OrderState.ARCHIVED: set(),
}


class InvalidTransition(Exception):
    pass


@dataclass
class PaperOrder:
    order_id: str
    symbol: str
    side: str
    quantity: float
    filled_qty: float = 0.0
    avg_price: float = 0.0
    state: OrderState = OrderState.IDLE
    fees: float = 0.0
    slippage: float = 0.0
    events: list[str] = field(default_factory=list)

    def transition(self, new: OrderState) -> None:
        if new not in ALLOWED_TRANSITIONS.get(self.state, set()):
            raise InvalidTransition(f"{self.state.value} -> {new.value} not allowed")
        self.state = new
        self.events.append(new.value)


class PaperExecutionAdapter:
    kind = "PAPER"

    def submit_live(self, *args, **kwargs):
        raise RuntimeError("PAPER adapter cannot submit live orders")

    def simulate_fill(
        self,
        order: PaperOrder,
        market_price: float,
        available_qty: float,
        fee_bps: float,
        slippage_bps: float,
        as_of_price_only: float,
    ) -> PaperOrder:
        # PIT: fill uses only as_of price, never future bars.
        price = as_of_price_only
        slip = price * (slippage_bps / 10_000.0)
        fill_price = price + slip if order.side == "BUY" else price - slip
        remaining = order.quantity - order.filled_qty
        fill_qty = min(remaining, available_qty)
        if fill_qty <= 0:
            return order
        notional = fill_qty * fill_price
        fee = notional * (fee_bps / 10_000.0)
        new_filled = order.filled_qty + fill_qty
        order.avg_price = (order.avg_price * order.filled_qty + fill_price * fill_qty) / new_filled
        order.filled_qty = new_filled
        order.fees += fee
        order.slippage += abs(slip * fill_qty)
        if order.state == OrderState.ACKNOWLEDGED:
            order.transition(OrderState.PARTIAL if new_filled < order.quantity else OrderState.FILLED)
        elif order.state == OrderState.PARTIAL:
            order.transition(OrderState.PARTIAL if new_filled < order.quantity else OrderState.FILLED)
        return order


class LiveExecutionAdapter:
    kind = "LIVE"

    def submit_live(self, *args, **kwargs):
        raise RuntimeError("LIVE adapter is not authorized")
