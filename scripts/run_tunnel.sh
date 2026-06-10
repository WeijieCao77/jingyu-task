#!/usr/bin/env bash
# Expose the local web server (:8080) on a public https URL so a phone can scan
# the QR and reach /voice. Uses cloudflared "quick tunnel" — no account needed.
#
# After it prints a https URL, put it in .env as PUBLIC_BASE_URL and restart the
# web server, then open <that-url>/qr to get a scannable code.
set -euo pipefail
PORT="${1:-8080}"
if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared 未安装。安装方式："
  echo "  macOS:  brew install cloudflared"
  echo "  Linux:  see https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
  exit 1
fi
echo "启动公网隧道 → http://localhost:${PORT} ..."
exec cloudflared tunnel --url "http://localhost:${PORT}"
