#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
cd "$PROJECT_ROOT"

install -d -m 0750 backups
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
ARCHIVE="$PROJECT_ROOT/backups/emily-backup-${TIMESTAMP}.tar.gz"
CHECKSUM="${ARCHIVE}.sha256"
STAGING=$(mktemp -d)
complete=false

cleanup() {
  rm -rf -- "$STAGING"
  if [[ $complete != true ]]; then
    rm -f -- "$ARCHIVE" "$CHECKSUM"
  fi
}
trap cleanup EXIT

mkdir -p "$STAGING/runtime"
for component in emily homeassistant music-assistant; do
  if [[ -d "runtime/$component" ]]; then
    cp -a -- "runtime/$component" "$STAGING/runtime/$component"
  fi
done
cp -- compose.yaml "$STAGING/compose.yaml"

{
  echo "Emily backup created: $TIMESTAMP"
  echo "The .env file and Home Assistant token are intentionally excluded."
  echo "Configuration summary:"
  if [[ -f .env ]]; then
    while IFS='=' read -r key value; do
      case "$key" in
        TZ|EMILY_PORT|EMILY_NAME|EMILY_LOG_LEVEL|HOME_ASSISTANT_IMAGE|MUSIC_ASSISTANT_IMAGE)
          printf '%s=%s\n' "$key" "$value"
          ;;
        HOME_ASSISTANT_URL)
          if [[ -n $value ]]; then echo "HOME_ASSISTANT_URL=configured"; else echo "HOME_ASSISTANT_URL=not configured"; fi
          ;;
        HOME_ASSISTANT_TOKEN)
          if [[ -n $value ]]; then echo "HOME_ASSISTANT_TOKEN=configured"; else echo "HOME_ASSISTANT_TOKEN=not configured"; fi
          ;;
      esac
    done < .env
  else
    echo ".env=not present"
  fi
} > "$STAGING/config-summary.txt"

tar -C "$STAGING" -czf "$ARCHIVE" .
(
  cd "$(dirname -- "$ARCHIVE")"
  sha256sum "$(basename -- "$ARCHIVE")" > "$(basename -- "$CHECKSUM")"
)
complete=true

echo "Backup created: $ARCHIVE"
echo "Checksum:       $CHECKSUM"
echo "The backups/ directory is excluded from Git. Copy important backups to another secure device."
