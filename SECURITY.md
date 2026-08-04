# Security policy

## Supported version

Emily Core 0.1 receives security fixes while it is the current release.

## Private-network deployment only

Emily v0.1 has no user authentication. Run ports 8787 and 8123 only on a trusted private LAN or access them through a private overlay network such as Tailscale. **Do not forward either port through your router and do not expose them directly to the public internet.**

Home Assistant's long-lived access token is stored only in the local `.env` file, which is excluded from Git. Emily does not log the token or return upstream response bodies. Backups intentionally exclude `.env`; credentials must be restored separately.

Review file permissions on `.env`, backups, and `runtime/` according to the other users present on your server. Keep Docker, the host OS, Emily, and integrated services updated.

## Reporting a vulnerability

Please do not open a public issue for a suspected vulnerability. Use GitHub's private vulnerability reporting feature for this repository. Include reproduction steps, affected versions, and the impact. Maintainers should acknowledge a report within seven days and coordinate disclosure after a fix is available.

