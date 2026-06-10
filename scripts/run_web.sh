#!/usr/bin/env bash
# Start the confirm + guard-query web server (FastAPI).
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || true
export PYTHONPATH="src:${PYTHONPATH:-}"
exec python -m visitor_agent.web.server
