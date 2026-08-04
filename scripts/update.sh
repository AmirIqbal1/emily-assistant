#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
cd "$PROJECT_ROOT"

music_was_running=false
if [[ -n $(docker compose --profile music ps -q music-assistant-server 2>/dev/null) ]]; then
  music_was_running=true
fi

if git rev-parse --is-inside-work-tree >/dev/null 2>&1 && [[ -n $(git remote) ]]; then
  echo "Updating source with a fast-forward-only pull..."
  git pull --ff-only
else
  echo "No Git remote configured; keeping the current source tree."
fi

docker compose --profile music pull --ignore-buildable
docker compose build --pull emily-core
docker compose up -d --force-recreate
if [[ $music_was_running == true ]]; then
  docker compose --profile music up -d --force-recreate music-assistant-server
fi

EMILY_PORT=8787
if [[ -f .env ]]; then
  configured_port=$(awk -F= '$1 == "EMILY_PORT" {print $2; exit}' .env)
  EMILY_PORT=${configured_port:-8787}
fi

healthy=false
if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required to verify Emily after an update." >&2
  exit 1
fi
for _attempt in $(seq 1 60); do
  if curl --fail --silent --max-time 3 "http://127.0.0.1:${EMILY_PORT}/health" >/dev/null; then healthy=true; break; fi
  sleep 2
done
if [[ $healthy != true ]]; then
  echo "Update completed, but Emily Core did not pass its health check." >&2
  docker compose logs --tail=50 emily-core
  exit 1
fi

echo "Emily has been updated. Persistent runtime data was left intact."
docker compose --profile music ps
