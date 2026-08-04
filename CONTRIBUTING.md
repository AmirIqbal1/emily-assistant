# Contributing to Emily

Thank you for helping build a private, local-first voice assistant.

1. Open an issue before a substantial change so its scope can be discussed.
2. Fork the repository and create a focused branch from `develop`.
3. Keep integrations optional, local-first, and usable without paid APIs.
4. Add type hints and tests for changed behavior.
5. Run `make test`, `docker compose --env-file .env.example --profile music config`, and a Docker build before opening a pull request.
6. Do not commit `.env`, tokens, runtime data, recordings, backups, or other personal data.

Pull requests should explain the user-visible behavior, tests performed, security implications, and any documentation changes. By contributing, you agree that your contribution is licensed under the MIT License.
