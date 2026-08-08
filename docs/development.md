# Local development

Emily Core is designed to run on a laptop without Home Assistant, Music Assistant, internet access, or paid services.

## Normal development

```bash
make dev
```

This starts only Emily Core with source-mounted live reload. It is healthy even when Home Assistant is unavailable; `/api/status` reports that integration separately. Stop it with `make dev-stop`.

## Mock Home Assistant

```bash
make mock
```

This starts the same development stack with `HOME_ASSISTANT_MOCK=true` for the process only. It never rewrites `.env` and makes no network calls. Use the browser at `http://localhost:8787`, then try `turn on kitchen ceiling` followed by `is kitchen ceiling on?`.

Mock entities are in memory and reset when Core restarts. The interface labels them as mock entities.

## Real Home Assistant

Set `HOME_ASSISTANT_URL` and `HOME_ASSISTANT_TOKEN` in your untracked `.env`. Create a long-lived token in Home Assistant under Profile → Security → Long-lived access tokens. Start the optional local Home Assistant Compose profile only when needed:

```bash
make homeassistant-start
```

Use `make homeassistant-stop` to stop it. A 401 or 403 means the token is invalid or lacks permission; connection refused or timeout usually means the URL is unreachable from Core.

Device-changing commands require `HOME_ASSISTANT_CONTROL_ENABLED=true`. Locks are discovery and query only: all lock control remains blocked pending a future authorization and confirmation layer.

## Mock Music Assistant

Run both integrations locally without a server, speakers, or provider accounts:

```bash
make mock-all
```

Music state is retained while Core runs. Set `MUSIC_ASSISTANT_DEFAULT_PLAYER=Living Room Speaker` in `.env` if you want unqualified requests such as `play Oasis` to select that speaker. Otherwise Emily asks when more than one available player exists. See [Music Assistant](music-assistant.md) for real-server setup and the control-disable switch.
