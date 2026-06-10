#!/usr/bin/env bash
# Start the LiveKit voice-agent worker (handles inbound phone calls).
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || true
export PYTHONPATH="src:${PYTHONPATH:-}"
# Use "dev" for local hot-reload, "start" for production.
exec python -m visitor_agent.agent "${1:-dev}"
