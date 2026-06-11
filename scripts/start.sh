#!/usr/bin/env bash
# Cloud entrypoint: run the agent worker + the web server in one container.
# The agent worker connects out to LiveKit Cloud (it's a room participant); the
# phone connects to LiveKit Cloud directly — so this container only needs the
# HTTP port ($PORT) exposed. DB = Neon Postgres via DATABASE_URL.
set -euo pipefail
export PYTHONPATH="${PYTHONPATH:-/app/src}"
export PYTHONUNBUFFERED=1

# Agent worker in the background (production mode = "start").
python -m visitor_agent.agent start &
AGENT_PID=$!

# If the agent dies, take the container down so the platform restarts it.
trap 'kill -TERM "$AGENT_PID" 2>/dev/null || true' EXIT

# Web server in the foreground (binds 0.0.0.0:$PORT).
exec python -m visitor_agent.web.server
