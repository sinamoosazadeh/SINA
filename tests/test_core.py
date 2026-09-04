import os
from datetime import datetime, timezone, timedelta

import pytest

from apex.config import load_config, ConfigError
from apex.execution import PaperOrder, PaperExecutionAdapter, OrderState, InvalidTransition, LiveExecutionAdapter
from apex.features import registry_74, compute_all_features, compute_feature
from apex.identity import snapshot_identity
from apex.ledger import Ledger
from apex.market import MarketObservation, validate_observation, SUPPORTED_TIMEFRAMES
from apex.nonfinite import sanitize_number
from apex.persistence import Database
from apex.pipeline import PaperRuntime
from apex.quality import Quality
from apex.risk import evaluate_risk, HARD_VETOES
from apex.runtime_mode import parse_runtime_mode, RuntimeModeError, assert_paper_live_isolation, RuntimeMode
from apex.setup_strategy import evaluate_setups, propose_strategy, HARD_SETUP_GATES
from apex.snapshot import build_snapshot
from apex.telegram_plane import escape_mdv2, TelegramControlPlane, render_message
from apex.app import make_fixture_candles
from apex.engines import run_engines
from apex.patterns import OPERATIONAL_PATTERNS, detect_patterns


def test_runtime_mode_fail_closed():
    assert parse_runtime_mode(None) == RuntimeMode.PAPER
    with pytest.raises(RuntimeModeError):
        parse_runtime_mode("PAPER+LIVE")
    with pytest.raises(RuntimeModeError):
        parse_runtime_mode("FOO")
    with pytest.raises(RuntimeModeError):
        assert_paper_live_isolation(RuntimeMode.PAPER, "LIVE")


def test_paper_rejects_live_credentials(tmp_path, monkeypatch):
    with pytest.raises(ConfigError):
        load_config({"APEX_RUNTIME_MODE": "PAPER", "TOOBIT_LIVE_API_KEY": "secret", "APEX_EXCHANGE": "TOOBIT"})


def test_live_not_authorized():
    with pytest.raises(ConfigError):
        load_config({"APEX_RUNTIME_MODE": "LIVE", "APEX_EXCHANGE": "TOOBIT"})


def test_toobit_only():
    with pytest.raises(ConfigError):
        load_config({"APEX_EXCHANGE": "BINANCE"})


def test_snapshot_identity_deterministic():
    a = snapshot_identity({"x": 1, "y": [2, 3]})
    b = snapshot_identity({"y": [2, 3], "x": 1})
    assert a == b
    assert len(a) == 64


def test_timeframes():
    assert len(SUPPORTED_TIMEFRAMES) == 14


def test_invalid_ohlc():
    t = datetime(2024, 1, 1, tzinfo=timezone.utc)
    obs = MarketObservation("BTCUSDT", "1h", 1, 0.5, 2, 1, 1, None, t, t, t, t, True, Quality.VALID, Quality.UNAVAILABLE)
    assert validate_observation(obs).quality == Quality.INVALID


def test_missing_oi_not_zero():
    candles = make_fixture_candles(5)
    for c in candles:
        c.open_interest = None
        c.oi_quality = Quality.UNAVAILABLE
    snap = build_snapshot(candles, "BTCUSDT", "1h", "pp", "v")
    v, q = compute_feature("F30", snap.candles)
    assert v is None
    assert q == Quality.UNAVAILABLE


def test_nonfinite_not_zero():
    b = sanitize_number(float("nan"))
    assert not b.is_value()
    assert b.value is not None or b.quality == Quality.INVALID


def test_feature_registry_74():
    r = registry_74()
    assert len(r) == 74
    ids = [x.feature_id for x in r]
    assert len(set(ids)) == 74


def test_engines_twelve():
    candles = [c.to_dict() for c in make_fixture_candles(80)]
    outs = run_engines(candles)
    assert [e.engine_id for e in outs] == [f"E{i:02d}" for i in range(1, 13)]


def test_warmup_insufficient():
    candles = [c.to_dict() for c in make_fixture_candles(3)]
    v, q = compute_feature("F11", candles)
    assert v is None
    assert q == Quality.INSUFFICIENT_HISTORY


def test_pit_rejects_future():
    candles = make_fixture_candles(10)
    as_of = candles[5].availability_time
    snap = build_snapshot(candles, "BTCUSDT", "1h", "pp", "v", as_of=as_of)
    last = datetime.fromisoformat(snap.candles[-1]["availability_time"].replace("Z", "+00:00"))
    assert last <= as_of


def test_risk_cannot_be_overridden():
    from apex.setup_strategy import StrategyProposal
    p = StrategyProposal("x", "s", "BULLISH", "TREND", 0.9, 0.1, 0.9, "VALID", True)
    d = evaluate_risk(
        p, kill_switch=True, requested_qty=1, price=100, max_position_qty=10,
        max_exposure=1e9, max_allocation=1, equity=1e6, ledger_healthy=True,
        adapter_kind="PAPER", duplicate=False, quality_ok=True,
    )
    assert d.status == "REJECT"
    assert "V01_KILL_SWITCH" in d.fired_vetoes
    assert len(HARD_VETOES) == 14


def test_capital_ceiling():
    from apex.setup_strategy import StrategyProposal
    p = StrategyProposal("x", "s", "BULLISH", "TREND", 0.9, 0.1, 0.9, "VALID", True)
    d = evaluate_risk(
        p, kill_switch=False, requested_qty=100, price=1000, max_position_qty=1,
        max_exposure=50, max_allocation=0.01, equity=100, ledger_healthy=True,
        adapter_kind="PAPER", duplicate=False, quality_ok=True,
    )
    assert d.status in {"REDUCE", "REJECT"}
    assert d.quantity <= 1


def test_paper_adapter_no_live():
    a = PaperExecutionAdapter()
    with pytest.raises(RuntimeError):
        a.submit_live()
    live = LiveExecutionAdapter()
    with pytest.raises(RuntimeError):
        live.submit_live()


def test_fsm_invalid_skip():
    o = PaperOrder("1", "BTCUSDT", "BUY", 1)
    with pytest.raises(InvalidTransition):
        o.transition(OrderState.FILLED)


def test_ledger_append_only():
    l = Ledger()
    l.append("A", "e1", {"k": 1}, "PAPER")
    l.append("B", "e2", {"k": 2}, "PAPER")
    assert l.verify_chain()
    l._events[0].payload["k"] = 99
    assert not l.verify_chain()


def test_telegram_escape_and_auth():
    assert "\\." in escape_mdv2("1.2")
    tg = TelegramControlPlane([42], lambda: {"runtime_mode": "PAPER", "health": "H", "symbol": "BTC_USDT", "equity": -1.5, "kill_switch": False})
    assert "unauthorized" in tg.handle_command(1, "/status")
    msg = tg.handle_command(42, "/status")
    assert "PAPER" in msg
    assert tg.handle_callback(42, "c1", "HEALTH")
    assert "ignored" in tg.handle_callback(42, "c1", "HEALTH")


def test_markdown_property():
    nasty = "BTC_USDT (perp) *x* 1.2 -3 [a]"
    text = render_message("sym={s}", s=nasty)
    assert "_" not in text or "\\_" in text


def test_e2e_paper(tmp_path, monkeypatch):
    dbp = tmp_path / "t.db"
    monkeypatch.setenv("APEX_RUNTIME_MODE", "PAPER")
    monkeypatch.setenv("APEX_DB_PATH", str(dbp))
    monkeypatch.setenv("APEX_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TOOBIT_LIVE_API_KEY", "")
    cfg = load_config()
    db = Database(cfg.db_path)
    rt = PaperRuntime(cfg, db)
    assert rt.adapter.kind == "PAPER"
    candles = make_fixture_candles(80)
    d1 = rt.ingest_and_decide(candles)
    assert d1["snapshot_id"]
    assert "E01" in d1["engines"] and "E12" in d1["engines"]
    # restart
    db2 = Database(cfg.db_path)
    rt2 = PaperRuntime(cfg, db2)
    rt2.restore()
    assert rt2.ledger.verify_chain()
    d2 = rt2.ingest_and_decide(candles)
    assert d1["snapshot_id"] == d2["snapshot_id"]


def test_replay_equality(tmp_path, monkeypatch):
    monkeypatch.setenv("APEX_RUNTIME_MODE", "PAPER")
    monkeypatch.setenv("APEX_DB_PATH", str(tmp_path / "a.db"))
    monkeypatch.setenv("APEX_DATA_DIR", str(tmp_path))
    cfg = load_config()
    candles = make_fixture_candles(60)
    r1 = PaperRuntime(cfg, Database(tmp_path / "a.db"))
    r2 = PaperRuntime(cfg, Database(tmp_path / "b.db"))
    d1 = r1.ingest_and_decide(candles)
    d2 = r2.ingest_and_decide(candles)
    assert d1["snapshot_id"] == d2["snapshot_id"]


def test_timezone_independence(monkeypatch, tmp_path):
    monkeypatch.setenv("APEX_RUNTIME_MODE", "PAPER")
    monkeypatch.setenv("APEX_DATA_DIR", str(tmp_path))
    candles = make_fixture_candles(40)
    ids = []
    for tz in ["UTC", "America/New_York", "Asia/Tehran"]:
        monkeypatch.setenv("TZ", tz)
        monkeypatch.setenv("APEX_DB_PATH", str(tmp_path / f"{tz}.db"))
        cfg = load_config()
        rt = PaperRuntime(cfg, Database(cfg.db_path))
        ids.append(rt.ingest_and_decide(candles)["snapshot_id"])
    assert len(set(ids)) == 1


def test_setup_gates_count():
    assert len(HARD_SETUP_GATES) == 13


def test_pattern_admission():
    assert any(p.admission == "EXCLUDED" and p.pat_id == "PAT12" for p in OPERATIONAL_PATTERNS)
    candles = [c.to_dict() for c in make_fixture_candles(80)]
    pats = detect_patterns(run_engines(candles))
    excluded = [p for p in pats if p["pat_id"] == "PAT12"][0]
    assert excluded["active"] is False


def test_open_candle_not_in_snapshot():
    candles = make_fixture_candles(5)
    candles[-1].closed = False
    candles[-1].quality = Quality.PENDING
    snap = build_snapshot(candles, "BTCUSDT", "1h", "pp", "v")
    assert all(c["closed"] for c in snap.candles)
