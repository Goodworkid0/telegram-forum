# Telegram Forum

Telegram-connected discussion platform with moderation, messaging and escrow workflows.

Solo-developed by [Vojislav Beric](https://github.com/Goodworkid0).

## What it does

- Discussion threads, moderation and direct messaging.
- Escrow workflows, append-only balance accounting and reconciliation.
- Post-commit live updates; PostgreSQL/Redis services and a React interface.

## Stack

Python · FastAPI · PostgreSQL · Redis · React · Vite

## Getting started

Copy `.env.example` to `.env`. Set your own database password, application secret, bot token, web-app URL and allowed origins. Payment-provider variables are optional integrations and need separate credentials.

```sh
cp .env.example .env
# Configure .env before starting the services.
docker compose --env-file .env up --build
```

The Compose file includes PostgreSQL, Redis, API and worker services. The API binds to localhost on port 8000. Review proxy and HTTPS configuration for your environment. Backend source and migrations are in `backend/`; the Vite application is in `frontend/`.

## Project status

Initial public source snapshot. Python syntax and source manifests were checked for publication; full application, infrastructure and external-service integration tests have not been run for this release. Local credentials, databases, sessions, uploaded content and machine-specific deployment files are excluded.

## License

Original project code is available under the [MIT License](LICENSE). External dependencies retain their respective licences.
