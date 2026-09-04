"""Configuration loading and fail-closed validation."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from apex.runtime_mode import RuntimeMode, parse_runtime_mode, assert_paper_live_isolation


class ConfigError(Exception):
    pass


@dataclass
class ApexConfig:
    runtime_mode: RuntimeMode
    exchange: str
    time_basis: str
    data_dir: Path
    db_path: Path
    code_version: str
    schema_version: int
    parameter_package: str
    telegram_token: str | None
    telegram_authorized_user_ids: list[int]
    execution_adapter: str
    fee_bps: float = 4.0
    slippage_bps: float = 2.0
    max_position_qty: float = 10.0
    max_exposure: float = 50_000.0
    max_allocation: float = 0.25
    symbols: list[str] = field(default_factory=lambda: ["BTCUSDT"])
    timeframes: list[str] = field(
        default_factory=lambda: [
            "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d", "3d", "1w", "1mo",
        ]
    )

    def banner_lines(self) -> list[str]:
        lines = [
            "APEX GEN5",
            f"runtime_mode={self.runtime_mode.value}",
            f"exchange={self.exchange}",
            f"time_basis={self.time_basis}",
            f"code_version={self.code_version}",
            f"schema_version={self.schema_version}",
            f"parameter_package={self.parameter_package}",
            f"execution_adapter={self.execution_adapter}",
        ]
        if self.runtime_mode == RuntimeMode.PAPER:
            lines.append("PAPER SAFETY: orders are simulated; no real-capital order submission is permitted.")
        return lines


def load_config(environ: dict[str, str] | None = None) -> ApexConfig:
    env = environ if environ is not None else dict(os.environ)
    mode = parse_runtime_mode(env.get("APEX_RUNTIME_MODE", "PAPER"))
    exchange = env.get("APEX_EXCHANGE", "TOOBIT").upper()
    if exchange != "TOOBIT":
        raise ConfigError(f"unsupported exchange {exchange}; Toobit is the sole exchange boundary")
    time_basis = env.get("APEX_TIME_BASIS", "UTC")
    if time_basis != "UTC":
        raise ConfigError("time basis must be UTC")
    adapter = env.get("APEX_EXECUTION_ADAPTER")
    if adapter is None:
        adapter = "PAPER" if mode != RuntimeMode.LIVE else "LIVE"
    adapter = adapter.upper()
    assert_paper_live_isolation(mode, adapter)
    if mode == RuntimeMode.PAPER:
        if env.get("TOOBIT_LIVE_API_KEY") or env.get("TOOBIT_LIVE_API_SECRET"):
            # PAPER may see empty placeholders; non-empty LIVE secrets fail closed.
            if env.get("TOOBIT_LIVE_API_KEY", "").strip() or env.get("TOOBIT_LIVE_API_SECRET", "").strip():
                raise ConfigError("PAPER must not load LIVE credentials")
    if mode == RuntimeMode.LIVE:
        raise ConfigError("LIVE is not authorized in this PAPER implementation target")

    data_dir = Path(env.get("APEX_DATA_DIR", "./data"))
    db_path = Path(env.get("APEX_DB_PATH", str(data_dir / "apex_paper.db")))
    ids_raw = env.get("TELEGRAM_AUTHORIZED_USER_IDS", "")
    user_ids = [int(x) for x in ids_raw.split(",") if x.strip().isdigit()]
    token = env.get("TELEGRAM_BOT_TOKEN") or None
    if token == "":
        token = None
    return ApexConfig(
        runtime_mode=mode,
        exchange=exchange,
        time_basis=time_basis,
        data_dir=data_dir,
        db_path=db_path,
        code_version=env.get("APEX_CODE_VERSION", "5.0.0-paper"),
        schema_version=int(env.get("APEX_SCHEMA_VERSION", "1")),
        parameter_package=env.get("APEX_PARAMETER_PACKAGE", "pp-default-1"),
        telegram_token=token,
        telegram_authorized_user_ids=user_ids,
        execution_adapter=adapter,
    )
