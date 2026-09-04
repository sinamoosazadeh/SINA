"""Toobit adapter boundary — market data only for PAPER; no live orders."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from apex.market import MarketObservation, validate_observation
from apex.quality import Quality
from apex.runtime_mode import RuntimeMode


@dataclass
class SymbolMeta:
    canonical_symbol: str
    provider_symbol: str
    base_asset: str
    quote_asset: str
    settlement_asset: str
    contract_type: str
    quantity_step: float
    price_tick: float
    min_order_quantity: float
    max_order_quantity: float
    min_notional: float
    contract_multiplier: float
    version: str = "meta-1"


DEFAULT_BTC = SymbolMeta(
    canonical_symbol="BTCUSDT",
    provider_symbol="BTC-SWAP-USDT",
    base_asset="BTC",
    quote_asset="USDT",
    settlement_asset="USDT",
    contract_type="PERP",
    quantity_step=0.001,
    price_tick=0.1,
    min_order_quantity=0.001,
    max_order_quantity=100.0,
    min_notional=5.0,
    contract_multiplier=1.0,
)


class ToobitAdapter:
    def __init__(self, mode: RuntimeMode):
        self.mode = mode
        self.capability_live_orders = "CAPABILITY_UNKNOWN" if mode != RuntimeMode.LIVE else "FORBIDDEN_IN_THIS_BUILD"

    def normalize_quantity(self, qty: float, meta: SymbolMeta) -> float:
        if qty < meta.min_order_quantity:
            raise ValueError("quantity below min")
        steps = round(qty / meta.quantity_step)
        return steps * meta.quantity_step

    def observation_from_kline(
        self,
        symbol: str,
        timeframe: str,
        open_: float,
        high: float,
        low: float,
        close: float,
        volume: float,
        oi: float | None,
        event_time: datetime,
        available_time: datetime,
        closed: bool,
    ) -> MarketObservation:
        now = datetime.now(timezone.utc)
        obs = MarketObservation(
            symbol=symbol,
            timeframe=timeframe,
            open=open_,
            high=high,
            low=low,
            close=close,
            volume=volume,
            open_interest=oi,
            exchange_event_time=event_time,
            availability_time=available_time,
            ingestion_time=now,
            received_at=now,
            closed=closed,
            quality=Quality.VALID,
            oi_quality=Quality.VALID if oi is not None else Quality.UNAVAILABLE,
        )
        return validate_observation(obs)
