#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
cd "$PROJECT_ROOT" || exit 1

EMILY_PORT=8787
HOME_ASSISTANT_URL=http://127.0.0.1:8123
if [[ -f .env ]]; then
  configured_port=$(awk -F= '$1 == "EMILY_PORT" {print $2; exit}' .env)
  EMILY_PORT=${configured_port:-8787}
  configured_ha_url=$(awk -F= '$1 == "HOME_ASSISTANT_URL" {print substr($0, index($0, "=") + 1); exit}' .env)
  if [[ $configured_ha_url != *host.docker.internal* && -n $configured_ha_url ]]; then HOME_ASSISTANT_URL=$configured_ha_url; fi
fi

echo "Emily Doctor"
OS_NAME=$(awk -F= '$1 == "PRETTY_NAME" {value=substr($0, index($0, "=") + 1); gsub(/^"|"$/, "", value); print value; exit}' /etc/os-release 2>/dev/null)
echo "OS:              ${OS_NAME:-unknown}"
echo "Architecture:    $(uname -m)"
echo "Memory:          $(free -h 2>/dev/null | awk '/^Mem:/ {print $7 " available of " $2}' || echo unknown)"
echo "Disk:            $(df -h "$PROJECT_ROOT" 2>/dev/null | awk 'NR == 2 {print $4 " available of " $2}')"
echo "Docker:          $(docker --version 2>/dev/null || echo unavailable)"
echo "Compose:         $(docker compose version 2>/dev/null || echo unavailable)"
echo "Git branch:      $(git branch --show-current 2>/dev/null || echo unavailable)"
echo "Git commit:      $(git rev-parse --short HEAD 2>/dev/null || echo unavailable)"
if [[ -f .env ]]; then echo ".env:            present"; else echo ".env:            MISSING"; fi

for directory in runtime/emily runtime/homeassistant backups; do
  if [[ -d $directory ]]; then echo "Directory:       $directory present"; else echo "Directory:       $directory MISSING"; fi
done

echo
echo "Container status:"
docker compose --profile music ps 2>&1 || true

echo
echo "Emily health:"
curl --silent --show-error --max-time 5 "http://127.0.0.1:${EMILY_PORT}/health" 2>&1 || echo "unavailable"
echo
echo "Home Assistant API connectivity (no credentials sent):"
curl --silent --show-error --output /dev/null --write-out 'HTTP %{http_code}\n' --max-time 5 "$HOME_ASSISTANT_URL/api/" 2>&1 || echo "unavailable"

echo
echo "Listening ports:"
if command -v ss >/dev/null 2>&1; then
  ss -ltn 2>/dev/null | awk -v emily=":${EMILY_PORT}" '$4 ~ emily || $4 ~ /:8123$/ {print}'
else
  echo "ss command unavailable"
fi

echo
echo "Last 50 Emily Core log lines (tokens are never logged by Emily Core):"
docker compose logs --tail=50 emily-core 2>&1 || true
