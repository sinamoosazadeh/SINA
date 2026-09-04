#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python -m pip install -r requirements.txt
mkdir -p data logs
python -m apex.app migrate
echo "APEX GEN5 PAPER installed. Configure .env from .env.example then: python -m apex.app start"
