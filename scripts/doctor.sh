#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
cd "$PROJECT_ROOT" || exit 1

EMILY_PORT=8787
HOME_ASSISTANT_URL=http://127.0.0.1:8123
HOME_ASSISTANT_CONFIGURED=no
HOME_ASSISTANT_TOKEN_CONFIGURED=no
HOME_ASSISTANT_CONTROL_ENABLED=true
if [[ -f .env ]]; then
  configured_port=$(awk -F= '$1 == "EMILY_PORT" {print $2; exit}' .env)
  EMILY_PORT=${configured_port:-8787}
  configured_ha_url=$(awk -F= '$1 == "HOME_ASSISTANT_URL" {print substr($0, index($0, "=") + 1); exit}' .env)
  if [[ $configured_ha_url != *host.docker.internal* && -n $configured_ha_url ]]; then HOME_ASSISTANT_URL=$configured_ha_url; fi
  [[ -n $configured_ha_url ]] && HOME_ASSISTANT_CONFIGURED=yes
  configured_ha_token=$(awk -F= '$1 == "HOME_ASSISTANT_TOKEN" {print substr($0, index($0, "=") + 1); exit}' .env)
  [[ -n $configured_ha_token ]] && HOME_ASSISTANT_TOKEN_CONFIGURED=yes
  configured_control=$(awk -F= '$1 == "HOME_ASSISTANT_CONTROL_ENABLED" {print substr($0, index($0, "=") + 1); exit}' .env)
  HOME_ASSISTANT_CONTROL_ENABLED=${configured_control:-true}
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
ha_http_code=$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 5 "$HOME_ASSISTANT_URL/api/" 2>/dev/null || true)
if [[ $ha_http_code == 000 || -z $ha_http_code ]]; then echo "unavailable"; else echo "HTTP $ha_http_code"; fi

echo
echo "Home Assistant integration:"
echo "Home Assistant URL configured:   $HOME_ASSISTANT_CONFIGURED"
echo "Home Assistant token configured: $HOME_ASSISTANT_TOKEN_CONFIGURED"
if [[ $ha_http_code == 000 || -z $ha_http_code ]]; then
  echo "Home Assistant reachable:        no"
else
  echo "Home Assistant reachable:        yes"
fi
core_status=$(curl --silent --max-time 5 "http://127.0.0.1:${EMILY_PORT}/api/status" 2>/dev/null || true)
if [[ $core_status == *'"connected":true'* ]]; then
  echo "Home Assistant authenticated:     yes"
elif [[ -n $core_status ]]; then
  echo "Home Assistant authenticated:     no"
else
  echo "Home Assistant authenticated:     unavailable"
fi
echo "Home Assistant control enabled:   $HOME_ASSISTANT_CONTROL_ENABLED"
entity_payload=$(curl --silent --max-time 5 "http://127.0.0.1:${EMILY_PORT}/api/entities" 2>/dev/null || true)
entity_count=$(printf '%s' "$entity_payload" | sed -n 's/.*"count":\([0-9][0-9]*\).*/\1/p' | head -n 1)
if [[ -n $entity_count ]]; then echo "Discovered entity count:          $entity_count"; else echo "Discovered entity count:          unavailable"; fi

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
