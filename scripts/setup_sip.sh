#!/usr/bin/env bash
# Provision LiveKit inbound SIP so a visitor can DIAL A PHONE NUMBER and reach
# the agent (the take-home's core requirement). One-time setup.
#
# Prereqs:
#   1. LiveKit *Cloud* project (self-hosted livekit-server.exe --dev is NOT
#      publicly reachable, so Twilio can't deliver calls to it). Free tier is fine.
#   2. `lk` CLI installed + authenticated:  lk cloud auth   (or set
#      LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET in env).
#   3. A phone number from Twilio (or any SIP provider) whose Elastic SIP Trunk
#      origination URI points at your LiveKit Cloud SIP host (see TELEPHONY.md).
#   4. SIP_INBOUND_NUMBER set to that number in E.164, e.g. +14155550123.
#
# Then:  SIP_INBOUND_NUMBER=+1... ./scripts/setup_sip.sh
#
# The running agent worker (python -m visitor_agent.agent start) is dispatched
# automatically into each call room — no agent_name needed.
set -euo pipefail

NUM="${SIP_INBOUND_NUMBER:-}"
if [[ -z "$NUM" ]]; then
  echo "✗ Set SIP_INBOUND_NUMBER to your phone number in E.164 (e.g. +14155550123)." >&2
  exit 1
fi
if ! command -v lk >/dev/null 2>&1; then
  echo "✗ 'lk' CLI not found. Install: https://docs.livekit.io/home/cli/cli-setup/" >&2
  exit 1
fi

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

cat > "$TMP/inbound-trunk.json" <<JSON
{ "trunk": { "name": "Visitor inbound", "numbers": ["$NUM"] } }
JSON

# Individual rooms: each caller gets their own room (call-xxxx) → naturally
# concurrent (multiple cars calling at once = independent agent jobs).
cat > "$TMP/dispatch-rule.json" <<JSON
{ "name": "Visitor dispatch", "rule": { "dispatchRuleIndividual": { "roomPrefix": "call" } } }
JSON

echo "→ creating inbound trunk for $NUM ..."
lk sip inbound create "$TMP/inbound-trunk.json"
echo "→ creating dispatch rule (individual rooms, prefix 'call') ..."
lk sip dispatch create "$TMP/dispatch-rule.json"

echo
echo "✓ Done. Verify:  lk sip inbound list   &&   lk sip dispatch list"
echo "  Now run the worker:  python -m visitor_agent.agent start"
echo "  Then DIAL $NUM — the AI gatekeeper should answer."
echo "  (If your lk version rejects the JSON, see TELEPHONY.md / docs.livekit.io/sip.)"
