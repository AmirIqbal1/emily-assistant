# Installation

Install Emily on a trusted private Linux host with Docker Engine and the Docker Compose plugin. Follow the [README](../README.md#quick-installation) for the complete install and health-check commands.

Music Assistant is optional. Emily Core starts without it; start the profile only when you have configured it with `make music-start`. Add a Music Assistant long-lived token to the untracked `.env` as `MUSIC_ASSISTANT_TOKEN`; never put it in source control. See [Music Assistant](music-assistant.md) for the full configuration and Linux host-networking note.
