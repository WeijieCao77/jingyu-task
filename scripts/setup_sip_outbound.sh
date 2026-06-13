#!/usr/bin/env bash
# Create a LiveKit OUTBOUND SIP trunk so 转人工 can dial the guard's phone and
# bridge them into the live call. Prints the ST_... id → put it in .env as
# SIP_OUTBOUND_TRUNK_ID (and set GUARD_DIAL_NUMBER to the guard's mobile).
#
# Prereqs: `lk` CLI authed; a Twilio Elastic SIP Trunk with **Termination**
# enabled + a Credential List (username/password). See TELEPHONY.md §5.6.
#
# Env:
#   SIP_TERMINATION_URI   e.g. yourtrunk.pstn.twilio.com   (Twilio Termination SIP URI)
#   SIP_OUTBOUND_NUMBER   your Twilio number, E.164        (caller id for the dial)
#   SIP_TERM_USER         Twilio credential-list username
#   SIP_TERM_PASS         Twilio credential-list password
set -euo pipefail

: "${SIP_TERMINATION_URI:?set SIP_TERMINATION_URI (e.g. yourtrunk.pstn.twilio.com)}"
: "${SIP_OUTBOUND_NUMBER:?set SIP_OUTBOUND_NUMBER (your Twilio number, E.164)}"
command -v lk >/dev/null 2>&1 || { echo "✗ 'lk' CLI not found. https://docs.livekit.io/home/cli/cli-setup/" >&2; exit 1; }

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
cat > "$TMP/outbound.json" <<JSON
{ "trunk": { "name": "guard outbound", "address": "$SIP_TERMINATION_URI",
  "numbers": ["$SIP_OUTBOUND_NUMBER"],
  "auth_username": "${SIP_TERM_USER:-}", "auth_password": "${SIP_TERM_PASS:-}" } }
JSON

echo "→ creating LiveKit outbound trunk via $SIP_TERMINATION_URI ..."
lk sip outbound create "$TMP/outbound.json"
echo
echo "✓ 把上面返回的 ST_... 填进 .env：SIP_OUTBOUND_TRUNK_ID=ST_..."
echo "  再设 GUARD_DIAL_NUMBER=<门卫手机号>，重启 agent worker。"
echo "  （若 lk 版本字段不同，见 docs.livekit.io/sip。）"
