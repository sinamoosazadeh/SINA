# APEX GEN5 PAPER

APEX GEN5 PAPER is a complete, runnable cryptocurrency-futures **paper-trading** system. It ingests OHLCV + Open Interest, builds point-in-time snapshots, runs Layer-00 features and analyst engines E01–E12, materializes evidence and admitted patterns, evaluates setups and strategy, applies an independent Risk Kernel, and **simulates** execution. It never submits real-capital orders.

**LIVE is blocked** in this repository. PAPER and LIVE adapters are isolated.

## Install

```bash
python -m venv .venv
source .venv/bin/Linux/activate 2>/dev/null || source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Termux: `bash scripts/termux_install.sh`

PAPER starts **without** LIVE credentials and without a Telegram token.

## Initialize & start

```bash
python -m apex.app migrate
python -m apex.app health
python -m apex.app start
```

Startup prints:

- APEX GEN5
- runtime mode, exchange, UTC, versions, adapter
- PAPER SAFETY: orders are simulated; no real-capital order submission is permitted.

## Tests

```bash
python -m pytest -q
python scripts/release_validate.py
```

## Replay

`python -m apex.app replay` runs the deterministic fixture twice-compatible path.

## Telegram

Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_AUTHORIZED_USER_IDS` to enable the control plane. Authorization is server-side. MarkdownV2 is escaped. Telegram cannot bypass Risk Kernel or switch PAPER→LIVE.

## PAPER vs LIVE

| | PAPER | LIVE |
|---|---|---|
| Orders | Simulated | Not authorized in this build |
| Credentials | Must not load LIVE keys | Owner authorization required |
| Default | Yes | Fail-closed |

External gates (real Toobit connectivity, real Telegram delivery, device soak) remain **OPEN / UNVERIFIED** until executed against live infrastructure.
