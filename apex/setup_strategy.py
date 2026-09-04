"""Setup, playbook, strategy, forecast, P-U-C, decision."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from apex.quality import Quality


HARD_SETUP_GATES = [
    "G01_QUALITY_VALID",
    "G02_PIT_OK",
    "G03_PATTERN_ADMITTED",
    "G04_DIRECTION_ALIGNED",
    "G05_WARMUP_COMPLETE",
    "G06_NO_EXTERNAL_NATIVE_MASQUERADE",
    "G07_OI_NOT_FABRICATED",
    "G08_CLOSED_CANDLE",
    "G09_NO_FUNDING_INPUT",
    "G10_NO_FOREX_SESSION_GATE",
    "G11_SNAPSHOT_BOUND",
    "G12_PARAMETER_ACTIVE",
    "G13_RUNTIME_PAPER_SAFE",
]


@dataclass
class Setup:
    setup_id: str
    pattern_id: str
    direction: str
    strength: float
    gates: dict[str, bool]
    active: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_setups(patterns: list[dict], snapshot_quality: str, closed: bool) -> list[Setup]:
    setups = []
    for p in patterns:
        gates = {g: True for g in HARD_SETUP_GATES}
        gates["G01_QUALITY_VALID"] = snapshot_quality == Quality.VALID.value and p.get("quality") == Quality.VALID.value
        gates["G03_PATTERN_ADMITTED"] = p.get("admission") == "RUNTIME_ADMITTED"
        gates["G04_DIRECTION_ALIGNED"] = p.get("active") is True and p.get("direction") in {"BULLISH", "BEARISH"}
        gates["G08_CLOSED_CANDLE"] = closed
        gates["G05_WARMUP_COMPLETE"] = p.get("quality") != Quality.INSUFFICIENT_HISTORY.value
        active = all(gates.values()) and p.get("active") is True
        setups.append(
            Setup(
                setup_id=f"SET-{p['pat_id']}",
                pattern_id=p["pat_id"],
                direction=p.get("direction", "FLAT"),
                strength=float(p.get("strength") or 0.0),
                gates=gates,
                active=active,
            )
        )
    return setups


def rank_setups(setups: list[Setup]) -> list[Setup]:
    return sorted(setups, key=lambda s: (-int(s.active), -s.strength, s.setup_id))


@dataclass
class StrategyProposal:
    proposal_id: str
    setup_id: str
    direction: str
    playbook: str
    probability: float
    uncertainty: float
    confidence: float
    quality: str
    eligible: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def playbook_for(setup: Setup) -> str:
    mapping = {
        "PAT01": "TREND_CONTINUATION",
        "PAT02": "REVERSAL",
        "PAT03": "LIQUIDITY",
        "PAT04": "IMBALANCE",
        "PAT05": "SMART_MONEY_OB",
        "PAT06": "TREND_CONTINUATION",
        "PAT07": "BREAKOUT",
        "PAT08": "VOL_EXPANSION",
    }
    return mapping.get(setup.pattern_id, "NO_TRADE")


def forecast_puc(setup: Setup) -> tuple[float, float, float]:
    # Deterministic baseline — not a trained AI model.
    p = 0.5 + min(0.25, setup.strength)
    if setup.direction == "BEARISH":
        p = 1.0 - p
    u = max(0.05, 0.4 - setup.strength)
    c = max(0.0, min(1.0, 1.0 - u))
    return p, u, c


def propose_strategy(setups: list[Setup], snapshot_id: str) -> StrategyProposal | None:
    ranked = rank_setups(setups)
    active = [s for s in ranked if s.active]
    if not active:
        return None
    s = active[0]
    p, u, c = forecast_puc(s)
    eligible = c >= 0.4 and u <= 0.5
    return StrategyProposal(
        proposal_id=f"STRAT-{snapshot_id[:12]}-{s.setup_id}",
        setup_id=s.setup_id,
        direction=s.direction,
        playbook=playbook_for(s),
        probability=p,
        uncertainty=u,
        confidence=c,
        quality=Quality.VALID.value,
        eligible=eligible,
    )
