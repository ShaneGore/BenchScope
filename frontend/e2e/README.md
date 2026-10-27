# Playwright journeys

`pnpm test:journey` runs local-authenticated, hosted-anonymous, and Pages-base
journeys. Set `TEST_DATABASE_URL` to a disposable local PostgreSQL database;
each API process creates and drops its own isolated schema, so no database seed
is needed. Install Chromium once with `pnpm exec playwright install chromium`.

The local profile uses `APP_MODE=local`, `APP_ENV=test`,
`LOCAL_AUTH_BYPASS=false`, and an API bound to `127.0.0.1`. Its harness creates
per-run RSA keys/tokens for two synthetic subjects and serves public JWKS only
over loopback. The fake benchmark adapter is injected only by
`backend/tests/e2e_server.py`.

The hosted profile uses `APP_MODE=hosted`, `APP_ENV=test`,
`LOCAL_AUTH_BYPASS=false`, a disabled runner, an explicit local CORS origin, and
reserved `.invalid` Clerk placeholders. A Vite-only Clerk stub keeps the demo
anonymous and offline; the browser is checked for demo GETs only and zero JWKS
fetches. Neither profile changes Compose or deployment settings.
