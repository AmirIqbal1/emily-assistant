# Emily

Emily is an open-source, local-first voice assistant intended to become a practical Siri or Alexa replacement. It runs on a home server and will eventually connect to small Linux and Raspberry Pi voice satellites. This repository currently contains **Emily Core v0.2**: deterministic Home Assistant discovery and device control through the local web chat, without microphone streaming or wake-word detection.

The current release provides a FastAPI core, a mobile-friendly local chat page with a device browser, deterministic offline intents, safe Home Assistant tools, optional Music Assistant infrastructure, Docker Compose lifecycle management, and backup/recovery tools. It uses no paid API and sends no analytics.

> [!WARNING]
> Emily v0.2 has no authentication. Use it only on a trusted private LAN or through Tailscale. Never forward ports 8787 or 8123 through your router or expose them directly to the internet.

## Architecture

```mermaid
flowchart LR
    Browser[Browser on trusted LAN] -->|HTTP :8787| Core[Emily Core<br/>FastAPI]
    Core --> Router[Local intent router]
    Router --> Provider[Local provider]
    Provider --> Tools[Tool registry<br/>allow-listed controls]
    Tools --> Resolver[Entity resolver]
    Resolver --> Discovery[Entity discovery cache<br/>safe entity metadata]
    Tools --> Backend[HomeAssistantBackend]
    Backend --> Real[Real HTTP backend]
    Backend --> Mock[Mock in-memory backend]
    Real --> HA[Optional Home Assistant<br/>host network :8123]
    MA[Music Assistant<br/>optional profile] -. future tools .-> Core
    Satellites[Raspberry Pi satellites] -. future voice transport .-> Core
    Runtime[(Local runtime data)] --- Core
    Runtime --- HA
    Runtime --- MA
```

## Requirements

- A headless Linux server; Ubuntu 22.04 or newer is recommended
- A 64-bit x86 or ARM CPU
- 2 GB RAM minimum; 4 GB or more recommended for Home Assistant and future local AI
- 5 GB free disk minimum, plus room for Home Assistant history, music metadata, and backups
- Docker Engine with the Docker Compose plugin
- Git and either `curl` or `wget`
- A user account allowed to run Docker

No microphone, speaker, Raspberry Pi, GPU, or API subscription is needed for v0.2.

## Quick installation

```bash
git clone https://github.com/AmirIqbal1/emily-assistant.git
cd emily-assistant
./scripts/install.sh
```

The installer checks prerequisites, creates local runtime directories, copies `.env.example` to `.env` only when needed, builds Emily Core, starts the default stack, and waits for the health endpoint. It never installs Docker or overwrites an existing `.env`.

Open `http://SERVER-IP:8787` for Emily. Home Assistant is optional; start a local instance later with `make homeassistant-start`.

## Manual installation

```bash
cp .env.example .env
chmod 600 .env
mkdir -p runtime/emily runtime/homeassistant backups
docker compose build emily-core
docker compose up -d
docker compose ps
curl --fail http://127.0.0.1:8787/health
```

Edit `.env` to change the timezone, port, assistant name, log level, service images, or Home Assistant connection. Never commit this file. Image variables make it possible to pin or mirror Home Assistant and Music Assistant images.

## Home Assistant setup

1. Open `http://SERVER-IP:8123` and complete Home Assistant's onboarding flow.
2. In Home Assistant, select your profile in the lower-left corner.
3. Open the **Security** tab, find **Long-lived access tokens**, and choose **Create token**.
4. Name it `Emily`, copy it immediately, and store it in a password manager.
5. Edit Emily's `.env` and set `HOME_ASSISTANT_TOKEN=the-token-you-copied`.
6. Apply it with `docker compose up -d --force-recreate emily-core`.
7. Ask Emily “Is Home Assistant online?” or refresh the status in the web page.

Emily communicates with Home Assistant only from the server: it uses `/api/`, `/api/states`, `/api/states/{entity_id}`, and explicitly allow-listed service calls. The browser never receives the long-lived token, raw Home Assistant response bodies, or arbitrary attributes. A missing, invalid, or unreachable configuration fails cleanly without exposing the token.

Home Assistant uses host networking so mDNS/SSDP discovery works reliably on the local network. It is an optional Compose profile: Emily Core starts and remains healthy with no Home Assistant, token, or internet connection. Emily reaches a real instance from its container through `host.docker.internal`; it is not configured behind a public reverse proxy by this project.

### Home Assistant devices and commands

Emily discovers `light`, `switch`, `fan`, `media_player`, `climate`, `cover`, `lock`, `sensor`, and `binary_sensor` entities. Discovery is cached for 30 seconds by default and is shown in the web chat’s Devices section. Set `ENTITY_CACHE_SECONDS` to adjust that cache.

Device-changing controls are enabled by default with `HOME_ASSISTANT_CONTROL_ENABLED=true`. Set it to `false` to retain discovery and state questions while disabling all device-changing requests.

Supported conversational commands include:

- `turn on the kitchen light`, `switch the kitchen light on`, `turn off the bedroom fan`
- `toggle the hallway light`
- `set kitchen light to 50 percent`, `dim kitchen light to 20 percent`
- `set the living room TV volume to 30 percent`
- `play the living room TV`, `pause the living room TV`
- `is the kitchen light on?`, `what state is the office switch?`
- `what is the temperature sensor reading?`, `what is the living room thermostat set to?`

Names are resolved deterministically from friendly names and entity-ID suffixes. Emily asks which device you mean when a match is ambiguous; it never guesses. Brightness and volume are clamped to 0–100% before conversion to Home Assistant values.

Locks can be discovered and queried, but cannot be controlled in v0.2. Garage doors, alarms, security systems, scripts, shell commands, and generic service execution are intentionally blocked. These sensitive actions require a future confirmation and authorization framework.

### Local mock mode

For laptop development without Home Assistant, set `HOME_ASSISTANT_MOCK=true` in your untracked `.env`, or run `make mock`. Mock mode provides in-memory Kitchen Ceiling, Bedroom Lamp, Office Fan, Living Room TV, Office Temperature, and Front Door entities. State changes persist while Core runs, but are discarded on restart. The UI and status API clearly mark mock mode; no token or network connection is used. See [development notes](docs/development.md) for the full local workflow.

## Optional Music Assistant

Music Assistant is included behind a Compose profile and does not start by default:

```bash
docker compose --profile music up -d
```

Stop only Music Assistant with `make music-stop`. Its data is stored in `runtime/music-assistant`. Emily does not yet send commands to Music Assistant.

## Operations

| Task | Command |
| --- | --- |
| Start default services | `make start` |
| Stop services | `make stop` |
| Restart | `make restart` |
| Follow logs | `make logs` |
| Update safely | `make update` |
| Run diagnostics | `make doctor` |
| Show containers | `docker compose --profile music ps` |

The updater performs a fast-forward-only Git pull when a remote exists, pulls images, rebuilds Emily Core, recreates services, and verifies health. It never removes `runtime/`.

## Backups and restore

Create a backup with:

```bash
make backup
```

The timestamped archive and SHA-256 file are written to `backups/`. Archives include Emily, Home Assistant, and existing Music Assistant runtime data, `compose.yaml`, and a sanitized settings summary. They never include `.env` or its real token. The entire `backups/` directory is excluded from Git; copy important archives to encrypted storage on another device.

Restore interactively, or use `--yes` for deliberate automation:

```bash
./scripts/restore.sh backups/emily-backup-YYYYMMDDTHHMMSSZ.tar.gz
./scripts/restore.sh --yes /secure/path/emily-backup.tar.gz
```

Restore verifies the adjacent `.sha256` when present, rejects unsafe archive paths and links, shows the contents, stops services, creates a safety backup, swaps only runtime components, restarts previously enabled services, and rolls back if Emily does not become healthy. Because `.env` is excluded, restore credentials separately.

## Troubleshooting

- Run `./scripts/doctor.sh`; its report includes system resources, versions, Git state, directories, containers, port listeners, connectivity, health, and the last 50 Core log lines without printing secrets.
- If Docker access fails, confirm the daemon is running and follow Docker's post-install instructions for non-root users, then log out and back in.
- If port 8787 or 8123 is already used, locate the process with `ss -ltnp`. Change `EMILY_PORT` for Core; Home Assistant requires port 8123 in this milestone.
- If Home Assistant is starting for the first time, wait several minutes and inspect `docker compose logs homeassistant`.
- If Home Assistant reports an invalid token, create a new long-lived token, update `.env`, and recreate `emily-core`.
- If the Devices section cannot load, confirm `HOME_ASSISTANT_URL` is reachable from the Emily container and run `make doctor`.
- If Emily cannot identify a device, use its displayed friendly name or rename the entity in Home Assistant. Similar names trigger a clarification instead of an action.
- If a container cannot write its runtime directory, check ownership and permissions under `runtime/`; do not make credentials or backups world-readable.
- Run `docker compose --env-file .env.example --profile music config` to inspect the fully rendered stack without revealing a real token.

## Development

Python 3.12 is required. Create an isolated environment and run the suite:

```bash
cd services/emily-core
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
```

Then validate packaging and deployment from the repository root:

```bash
docker compose --env-file .env.example --profile music config
docker build -t emily-core:test services/emily-core
```

The `AssistantProvider` interface isolates message processing. A future `OllamaProvider` can implement `name`, `is_available()`, and `process(message, context)` and be registered alongside the always-available local provider. Keep new integrations honest: unavailable services must report failure rather than simulate success.

## Roadmap

1. v0.1 Core infrastructure — complete
2. v0.2 Home Assistant tools — complete
3. v0.3 Music Assistant + Spotify — next
4. v0.4 Ollama conversational provider
5. v0.5 Speech-to-text and text-to-speech
6. v0.6 Wake word
7. v0.7 Raspberry Pi/Linux satellites

## Contributing

Issues and focused pull requests are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before starting and use private vulnerability reporting for security issues. Emily is available under the [MIT License](LICENSE).
