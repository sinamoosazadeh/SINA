"""APEX GEN5 PAPER entrypoint."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from apex import __version__
from apex.config import load_config
from apex.market import MarketObservation, validate_observation
from apex.persistence import Database
from apex.pipeline import PaperRuntime
from apex.quality import Quality
from apex.telegram_plane import TelegramControlPlane


def make_fixture_candles(n: int = 80, symbol: str = "BTCUSDT", timeframe: str = "1h") -> list[MarketObservation]:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    out = []
    price = 40_000.0
    for i in range(n):
        o = price
        price = price * (1.0 + (0.001 if i % 7 else -0.0004))
        h = max(o, price) * 1.001
        l = min(o, price) * 0.999
        vol = 100 + i
        t = base + timedelta(hours=i)
        avail = t + timedelta(hours=1)
        obs = MarketObservation(
            symbol=symbol,
            timeframe=timeframe,
            open=o,
            high=h,
            low=l,
            close=price,
            volume=vol,
            open_interest=1_000_000 + i * 10,
            exchange_event_time=t,
            availability_time=avail,
            ingestion_time=avail,
            received_at=avail,
            closed=True,
            quality=Quality.VALID,
            oi_quality=Quality.VALID,
        )
        out.append(validate_observation(obs))
    return out


def startup() -> PaperRuntime:
    cfg = load_config()
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    for line in cfg.banner_lines():
        print(line, flush=True)
    db = Database(cfg.db_path)
    rt = PaperRuntime(cfg, db)
    rt.restore()
    print(f"health={rt.overall_health()}", flush=True)
    return rt


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="apex")
    p.add_argument("command", nargs="?", default="start", choices=["start", "health", "replay", "migrate", "demo"])
    args = p.parse_args(argv)
    if args.command == "migrate":
        cfg = load_config()
        Database(cfg.db_path)
        print("migrated", cfg.db_path)
        return 0
    rt = startup()
    if args.command == "health":
        print(json.dumps(rt.status(), indent=2))
        return 0
    candles = make_fixture_candles()
    decision = rt.ingest_and_decide(candles)
    if args.command in {"start", "demo", "replay"}:
        print(json.dumps({k: decision[k] for k in ("decision_id", "snapshot_id", "risk", "order", "equity") if k in decision}, indent=2, default=str))
    tg = TelegramControlPlane(rt.config.telegram_authorized_user_ids or [1], rt.status)
    if rt.config.telegram_authorized_user_ids:
        print(tg.handle_command(rt.config.telegram_authorized_user_ids[0], "/status"))
    else:
        print(tg.handle_command(1, "/status"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
