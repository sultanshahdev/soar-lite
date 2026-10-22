#!/usr/bin/env bash
# Prepare only the private local configuration needed by Docker Compose.
set -euo pipefail

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
env_file="$repo_dir/.env"
example_file="$repo_dir/.env.example"

for tool in docker openssl curl; do
  command -v "$tool" >/dev/null 2>&1 || { echo "Missing required tool: $tool" >&2; exit 1; }
done
docker compose version >/dev/null 2>&1 || { echo "Docker Compose v2 is required." >&2; exit 1; }

if [[ ! -f "$env_file" ]]; then
  cp "$example_file" "$env_file"
  echo "Created private .env from .env.example."
fi

set_value() {
  local key=$1 value=$2 temp
  temp=$(mktemp "${env_file}.XXXXXX")
  awk -v key="$key" -v value="$value" '
    BEGIN { found=0 }
    $0 ~ "^" key "=" { if (!found) print key "=" value; found=1; next }
    { print }
    END { if (!found) print key "=" value }
  ' "$env_file" > "$temp"
  mv "$temp" "$env_file"
}

needs_secret() {
  local key=$1 current
  current=$(sed -n "s/^${key}=//p" "$env_file" | head -n 1 | tr -d '\r')
  [[ -z "$current" || "$current" == replace-with-* ]]
}

for key in WEBHOOK_SECRET ANALYST_API_KEY; do
  if needs_secret "$key"; then
    set_value "$key" "$(openssl rand -hex 32)"
    echo "Generated $key in private .env."
  fi
done

current_abuse=$(sed -n 's/^ABUSEIPDB_API_KEY=//p' "$env_file" | head -n 1 | tr -d '\r')
if [[ -z "$current_abuse" || "$current_abuse" == replace-with-* ]]; then
  echo "An AbuseIPDB key is optional for startup but required for live enrichment."
  echo "Get one at https://www.abuseipdb.com/api.html"
  if [[ -t 0 ]]; then
    read -r -s -p "Paste AbuseIPDB API key now (or press Enter to skip): " entered_key
    echo
    [[ -n "$entered_key" ]] && set_value ABUSEIPDB_API_KEY "$entered_key"
  fi
fi

chmod 600 "$env_file" 2>/dev/null || true
echo "Setup complete. Next: bash scripts/start.sh"
