#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
cd "$PROJECT_ROOT"

trap 'echo "Installation failed on line $LINENO. Review the message above and run ./scripts/doctor.sh for diagnostics." >&2' ERR

if [[ $(uname -s) != "Linux" ]]; then
  echo "Emily currently supports Linux hosts only." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed. Install Docker Engine from https://docs.docker.com/engine/install/ and rerun this script." >&2
  echo "Emily will not install Docker without your approval." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "The Docker Compose plugin is required (the 'docker compose' command)." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "The current user cannot access Docker. Check that Docker is running and that your user has permission." >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1 && ! command -v wget >/dev/null 2>&1; then
  echo "Either curl or wget is required to verify Emily's health endpoint." >&2
  exit 1
fi

install -d -m 0750 runtime runtime/emily runtime/homeassistant backups

if [[ ! -f .env ]]; then
  cp .env.example .env
  chmod 0600 .env
  echo "Created .env from .env.example. No credentials were added."
else
  echo "Keeping the existing .env file unchanged."
fi

echo "Building Emily Core..."
docker compose build emily-core

echo "Starting Emily Core..."
docker compose up -d

EMILY_PORT=$(awk -F= '$1 == "EMILY_PORT" {print $2; exit}' .env)
EMILY_PORT=${EMILY_PORT:-8787}
HEALTH_URL="http://127.0.0.1:${EMILY_PORT}/health"

echo "Waiting for Emily Core to become healthy..."
healthy=false
for _attempt in $(seq 1 60); do
  if command -v curl >/dev/null 2>&1 && curl --fail --silent --max-time 3 "$HEALTH_URL" >/dev/null; then
    healthy=true
    break
  fi
  if ! command -v curl >/dev/null 2>&1 && command -v wget >/dev/null 2>&1 && wget -q -T 3 -O /dev/null "$HEALTH_URL"; then
    healthy=true
    break
  fi
  sleep 2
done

if [[ $healthy != true ]]; then
  echo "Emily Core did not become healthy at $HEALTH_URL." >&2
  docker compose ps
  docker compose logs --tail=50 emily-core
  exit 1
fi

SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
SERVER_IP=${SERVER_IP:-SERVER-IP}
echo
echo "Emily Core is ready: http://${SERVER_IP}:${EMILY_PORT}"
echo "Home Assistant is optional. Start it later with: make homeassistant-start"
echo "Enable Music Assistant later with: docker compose --profile music up -d"
