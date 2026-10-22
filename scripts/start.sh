#!/usr/bin/env bash
# Start the existing Compose stack without removing its persistent database volume.
set -euo pipefail

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
[[ -f "$repo_dir/.env" ]] || { echo "Missing .env. Run: bash scripts/setup.sh" >&2; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "Docker is required." >&2; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "Docker Compose v2 is required." >&2; exit 1; }

if ! docker compose --env-file "$repo_dir/.env" -f "$repo_dir/infra/compose.yaml" up -d --build; then
  echo "Startup failed. If Docker reports permission denied, ensure your user can access the Docker socket." >&2
  exit 1
fi
echo "SOAR Lite is starting. Dashboard: http://127.0.0.1:5173"
echo "Health: http://127.0.0.1:8000/api/v1/health"
