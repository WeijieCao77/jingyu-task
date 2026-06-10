#!/usr/bin/env bash
# Run the offline text simulator (validate dialogue + slot extraction; needs ANTHROPIC_API_KEY).
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || true
export PYTHONPATH="src:${PYTHONPATH:-}"
exec python -m visitor_agent.sim.run_text "$@"
