#!/usr/bin/env bash
# Submit one fictional suspicious-login alert to the existing authenticated webhook.
set -euo pipefail

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
env_file="$repo_dir/.env"
[[ -f "$env_file" ]] || { echo "Missing .env. Run: bash scripts/setup.sh" >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "curl is required." >&2; exit 1; }

webhook_secret=$(sed -n 's/^WEBHOOK_SECRET=//p' "$env_file" | head -n 1 | tr -d '\r')
if [[ -z "$webhook_secret" || "$webhook_secret" == replace-with-* ]]; then
  echo "WEBHOOK_SECRET is missing or still a placeholder. Run: bash scripts/setup.sh" >&2
  exit 1
fi

event_id="demo-suspicious-login-$(date -u +%Y%m%dT%H%M%SZ)-${RANDOM}${RANDOM}"
observed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
payload=$(printf '{"event_id":"%s","event_type":"suspicious_login","severity":"high","observed_at":"%s","source_ip":"8.8.8.8","destination_host":"lab-server-01","rule":"Repeated failed login attempts","metadata":{"failed_attempts":12,"window_seconds":60,"demo":true}}' "$event_id" "$observed_at")
body_file=$(mktemp)
trap 'rm -f "$body_file"' EXIT
status=$(curl --connect-timeout 5 --max-time 15 -sS -o "$body_file" -w '%{http_code}' \
  -X POST http://127.0.0.1:8000/api/v1/ingest/generic \
  -H "Authorization: Bearer $webhook_secret" \
  -H 'Content-Type: application/json' \
  --data "$payload" || true)

case "$status" in
  200|201)
    incident_id=$(sed -n 's/.*"incident_id":"\([^"]*\)".*/\1/p' "$body_file")
    echo "Demo alert accepted (HTTP $status)."
    [[ -n "$incident_id" ]] && echo "Incident ID: $incident_id"
    echo "Open the dashboard and inspect Incidents, Investigations, then Response Actions."
    ;;
  000) echo "Could not reach the backend. Start it with: bash scripts/start.sh" >&2; exit 1 ;;
  401) echo "Webhook authentication failed. Check WEBHOOK_SECRET in private .env." >&2; exit 1 ;;
  *) echo "Alert submission failed (HTTP $status): $(tr '\n' ' ' < "$body_file")" >&2; exit 1 ;;
esac
