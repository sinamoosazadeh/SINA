"""SQLite persistence + migrations."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS market_observations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL,
  timeframe TEXT NOT NULL,
  payload TEXT NOT NULL,
  availability_time TEXT NOT NULL,
  UNIQUE(symbol, timeframe, availability_time)
);
CREATE TABLE IF NOT EXISTS snapshots (
  snapshot_id TEXT PRIMARY KEY,
  payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_events (
  evidence_id TEXT PRIMARY KEY,
  payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS patterns (
  pat_id TEXT PRIMARY KEY,
  payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS setups (
  setup_id TEXT PRIMARY KEY,
  payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strategy_proposals (
  proposal_id TEXT PRIMARY KEY,
  payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS forecasts (
  forecast_id TEXT PRIMARY KEY,
  payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS risk_decisions (
  risk_decision_id TEXT PRIMARY KEY,
  payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS paper_orders (
  order_id TEXT PRIMARY KEY,
  payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fills (
  fill_id TEXT PRIMARY KEY,
  payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS positions (
  position_id TEXT PRIMARY KEY,
  payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pnl (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ledger_events (
  sequence INTEGER PRIMARY KEY,
  event_id TEXT UNIQUE NOT NULL,
  payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_events (
  event_id TEXT PRIMARY KEY,
  payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS parameter_packages (
  package_id TEXT PRIMARY KEY,
  active INTEGER NOT NULL,
  payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS idempotency (
  key TEXT PRIMARY KEY,
  result TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reconciliation (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS feature_state (
  snapshot_id TEXT PRIMARY KEY,
  payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS playbooks (
  playbook_id TEXT PRIMARY KEY,
  payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS health (
  k TEXT PRIMARY KEY,
  v TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS kill_switch (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  active INTEGER NOT NULL
);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.migrate()

    def migrate(self) -> None:
        self.conn.executescript(SCHEMA)
        cur = self.conn.execute("SELECT COALESCE(MAX(version),0) FROM schema_meta")
        v = cur.fetchone()[0]
        if v < 1:
            from apex.time_model import isoformat_utc, utc_now
            self.conn.execute("INSERT INTO schema_meta(version, applied_at) VALUES (?, ?)", (1, isoformat_utc(utc_now())))
            self.conn.execute("INSERT OR IGNORE INTO kill_switch(id, active) VALUES (1, 0)")
            self.conn.commit()

    def put_json(self, table: str, key_col: str, key: str, payload: dict[str, Any]) -> None:
        self.conn.execute(
            f"INSERT OR REPLACE INTO {table}({key_col}, payload) VALUES (?, ?)",
            (key, json.dumps(payload, sort_keys=True)),
        )
        self.conn.commit()

    def get_json(self, table: str, key_col: str, key: str) -> dict[str, Any] | None:
        cur = self.conn.execute(f"SELECT payload FROM {table} WHERE {key_col}=?", (key,))
        row = cur.fetchone()
        return json.loads(row[0]) if row else None

    def append_ledger(self, sequence: int, event_id: str, payload: dict[str, Any]) -> None:
        self.conn.execute(
            "INSERT INTO ledger_events(sequence, event_id, payload) VALUES (?, ?, ?)",
            (sequence, event_id, json.dumps(payload, sort_keys=True)),
        )
        self.conn.commit()

    def load_ledger(self) -> list[dict[str, Any]]:
        cur = self.conn.execute("SELECT payload FROM ledger_events ORDER BY sequence")
        return [json.loads(r[0]) for r in cur.fetchall()]

    def idempotent(self, key: str, compute) -> Any:
        cur = self.conn.execute("SELECT result FROM idempotency WHERE key=?", (key,))
        row = cur.fetchone()
        if row:
            return json.loads(row[0])
        result = compute()
        self.conn.execute("INSERT INTO idempotency(key, result) VALUES (?, ?)", (key, json.dumps(result, sort_keys=True)))
        self.conn.commit()
        return result

    def set_kill_switch(self, active: bool) -> None:
        self.conn.execute("UPDATE kill_switch SET active=? WHERE id=1", (1 if active else 0,))
        self.conn.commit()

    def kill_switch_active(self) -> bool:
        cur = self.conn.execute("SELECT active FROM kill_switch WHERE id=1")
        row = cur.fetchone()
        return bool(row[0]) if row else False

    def insert_observation(self, payload: dict[str, Any]) -> None:
        try:
            self.conn.execute(
                "INSERT INTO market_observations(symbol, timeframe, payload, availability_time) VALUES (?, ?, ?, ?)",
                (payload["symbol"], payload["timeframe"], json.dumps(payload, sort_keys=True), payload["availability_time"]),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass  # duplicate idempotent

    def close(self) -> None:
        self.conn.close()
