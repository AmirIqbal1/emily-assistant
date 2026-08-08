# Music Assistant

Emily Core v0.3 uses Music Assistant as its only music-catalogue and playback integration. It does not connect directly to Spotify or any other provider. Configure providers and players in Music Assistant, then give Emily a long-lived token from the Music Assistant profile settings.

```dotenv
MUSIC_ASSISTANT_URL=http://host.docker.internal:8095
MUSIC_ASSISTANT_TOKEN=
MUSIC_ASSISTANT_MOCK=false
MUSIC_ASSISTANT_CONTROL_ENABLED=true
MUSIC_ASSISTANT_DEFAULT_PLAYER=Living Room Speaker
MUSIC_ASSISTANT_CACHE_SECONDS=30
```

The token stays in the untracked `.env`; it is never returned by the browser APIs, status endpoint, or logs. A missing token is reported safely as “Music Assistant requires authentication.” Music Assistant remains optional: Core and Home Assistant features continue to work if it is absent or unavailable.

Start the optional server with `make music-start`, stop it with `make music-stop`, and follow its logs with `make music-logs`. It uses host networking for LAN player discovery and is not published through Emily's Compose port mapping. On Linux this means it binds directly to the host network; keep the host firewall/private-LAN posture appropriate for your installation.

For offline local work use `make mock-all`, which enables both in-memory integrations. The Music Assistant mock offers Living Room Speaker, Bedroom Speaker, and an unavailable Car player plus a small, stateful catalogue. Try `play Wonderwall on living room speaker`, `what song is playing in living room?`, `pause the music in living room`, and `next song`.

Set `MUSIC_ASSISTANT_CONTROL_ENABLED=false` to keep player listing, search, and now-playing queries while preventing play, pause, resume, skip, stop, and volume changes.

## Real setup and Spotify

1. Run `make music-start` and open `http://localhost:8095` on the host.
2. Complete Music Assistant setup, add your music sources (including Spotify if it is supported for your account), and configure players there.
3. Create a Music Assistant long-lived access token in its profile settings.
4. Put only that token in Emily's untracked `.env`, set `MUSIC_ASSISTANT_MOCK=false`, and restart Emily.

Spotify authentication, credentials, and provider support remain wholly inside Music Assistant. Emily stores no Spotify credentials and support depends on Music Assistant and Spotify's current restrictions.

## Commands and troubleshooting

Try `play Oasis`, `play Wonderwall in the living room`, `play my Driving playlist`, `pause the music`, `resume the music`, `skip this song`, `go back a song`, `set music volume to 30 percent`, `what song is playing?`, and `what music players are available?`.

If Emily reports that Music Assistant is unavailable, check the URL from inside the Core container and run `make music-logs`. A missing token is normal for local mock work; a real server requiring authentication needs a fresh Music Assistant long-lived token. Set `MUSIC_ASSISTANT_DEFAULT_PLAYER` to an exact player ID or uniquely resolvable player name so unqualified playback commands have a destination.
