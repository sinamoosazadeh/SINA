# PAPER Acceptance

Local executable proof (pytest): **26 passed**.

- Installation: `pip install -r requirements.txt` (venv)
- Database migration: `python -m apex.app migrate`
- Startup banner includes PAPER SAFETY
- PAPER t0 does not require LIVE credentials
- End-to-end fixture: ingest → snapshot → features → E01–E12 → evidence → patterns → setup → strategy → risk → paper order → fill → position → ledger → restart

**PAPER_READY** for local/synthetic path.

External: real Toobit websocket, real Telegram delivery, Termux-on-device soak = **OPEN / UNVERIFIED**.
LIVE = **BLOCKED**.
