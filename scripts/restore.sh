#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
cd "$PROJECT_ROOT"

assume_yes=false
archive_arg=""
for arg in "$@"; do
  case "$arg" in
    --yes) assume_yes=true ;;
    -*) echo "Unknown option: $arg" >&2; exit 2 ;;
    *)
      if [[ -n $archive_arg ]]; then echo "Only one archive path may be supplied." >&2; exit 2; fi
      archive_arg=$arg
      ;;
  esac
done

if [[ -z $archive_arg ]]; then
  echo "Usage: ./scripts/restore.sh [--yes] /path/to/emily-backup.tar.gz" >&2
  exit 2
fi
if [[ ! -f $archive_arg ]]; then
  echo "Backup archive not found: $archive_arg" >&2
  exit 1
fi

ARCHIVE=$(realpath -- "$archive_arg")
CHECKSUM="${ARCHIVE}.sha256"
if [[ -f $CHECKSUM ]]; then
  expected=$(awk 'NR == 1 {print $1}' "$CHECKSUM")
  actual=$(sha256sum "$ARCHIVE" | awk '{print $1}')
  if [[ -z $expected || $expected != "$actual" ]]; then
    echo "Checksum verification failed. Nothing was restored." >&2
    exit 1
  fi
  echo "Checksum verified."
else
  echo "Warning: no checksum file found at $CHECKSUM; integrity cannot be verified."
fi

if ! tar -tzf "$ARCHIVE" | awk '
  /^\// { bad=1 }
  {
    count=split($0, parts, "/")
    for (i=1; i<=count; i++) if (parts[i] == "..") bad=1
  }
  END { exit bad }
'; then
  echo "Unsafe archive path detected. Nothing was restored." >&2
  exit 1
fi
if tar -tvzf "$ARCHIVE" | awk 'substr($1, 1, 1) ~ /[lh]/ { found=1 } END { exit !found }'; then
  echo "Archive contains links and will not be restored for safety." >&2
  exit 1
fi

echo "Archive contents to restore:"
tar -tzf "$ARCHIVE"
if [[ $assume_yes != true ]]; then
  read -r -p "Stop Emily and replace the listed runtime data? Type 'restore' to continue: " confirmation
  if [[ $confirmation != "restore" ]]; then
    echo "Restore cancelled."
    exit 0
  fi
fi

STAGING=$(mktemp -d)
ROLLBACK_DIR=$(mktemp -d "$PROJECT_ROOT/runtime/.rollback.XXXXXX")
declare -a REPLACED=()
services_stopped=false
success=false
music_was_running=false

rollback() {
  set +e
  if [[ $success != true ]]; then
    echo "Restore failed; rolling runtime data back to its previous state." >&2
    for component in "${REPLACED[@]}"; do
      rm -rf -- "$PROJECT_ROOT/runtime/$component"
      if [[ -e "$ROLLBACK_DIR/$component" ]]; then
        mv -- "$ROLLBACK_DIR/$component" "$PROJECT_ROOT/runtime/$component"
      fi
    done
    if [[ $services_stopped == true ]]; then
      docker compose up -d
      if [[ $music_was_running == true ]]; then docker compose --profile music up -d music-assistant-server; fi
    fi
  fi
  rm -rf -- "$STAGING" "$ROLLBACK_DIR"
}
trap rollback EXIT

tar --extract --gzip --file "$ARCHIVE" --directory "$STAGING" --no-same-owner --no-same-permissions
if find "$STAGING" -type l -print -quit | grep -q .; then
  echo "Archive extracted a symbolic link and was rejected." >&2
  exit 1
fi

if [[ -n $(docker compose --profile music ps -q music-assistant-server 2>/dev/null) ]]; then
  music_was_running=true
fi
docker compose --profile music stop
services_stopped=true

echo "Creating a safety backup of current runtime data..."
"$SCRIPT_DIR/backup.sh"

for component in emily homeassistant music-assistant; do
  source_dir="$STAGING/runtime/$component"
  target_dir="$PROJECT_ROOT/runtime/$component"
  if [[ -d $source_dir ]]; then
    incoming="$PROJECT_ROOT/runtime/.incoming-${component}-${RANDOM}"
    cp -a -- "$source_dir" "$incoming"
    REPLACED+=("$component")
    if [[ -e $target_dir ]]; then mv -- "$target_dir" "$ROLLBACK_DIR/$component"; fi
    mv -- "$incoming" "$target_dir"
  fi
done

docker compose up -d
if [[ $music_was_running == true ]]; then docker compose --profile music up -d music-assistant-server; fi

EMILY_PORT=8787
if [[ -f .env ]]; then
  configured_port=$(awk -F= '$1 == "EMILY_PORT" {print $2; exit}' .env)
  EMILY_PORT=${configured_port:-8787}
fi

healthy=false
if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required to verify Emily after restoration." >&2
  exit 1
fi
for _attempt in $(seq 1 60); do
  if curl --fail --silent --max-time 3 "http://127.0.0.1:${EMILY_PORT}/health" >/dev/null; then healthy=true; break; fi
  sleep 2
done
if [[ $healthy != true ]]; then
  echo "Emily did not become healthy after restoration." >&2
  exit 1
fi

success=true
echo "Restore completed successfully. Emily Core is healthy."
