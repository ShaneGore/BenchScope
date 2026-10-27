# Task 23 — Local API availability exercise

## Result

**Passed as an injected local outage and API-only recovery.** The exercise
used a unique disposable Compose project, synthetic settings/data, and
loopback-published endpoints. The only injected cause was the intentional API
stop. No hosted service or production behavior was involved; no application
or alert-rule fix is claimed.

All timestamps below are UTC. No credentials, owner identifiers, prompts,
benchmark output, or raw benchmark artifacts were recorded.

## Timeline and sanitized evidence

| Time | Event and result |
|---|---|
| 2026-10-27 05:48:57.675Z | Initial preflight found `127.0.0.1:5432` occupied; fixed API/observability ports were free. Per the then-current gate, the attempt was correctly aborted without starting services or altering the listener. |
| 2026-10-27 05:56:30.443Z | After the PM approved `POSTGRES_PORT`, rechecked fixed ports `8000`, `4318`, `9090`, `3100`, `3200`, `3000` and the DB candidates. All fixed ports and DB host port `15441` were free; selected `15441`. |
| 2026-10-27 05:58:23.347Z | Started local project `benchscope-task23-f5ecf142d10e4cad873d5ad4299a1b4d` in Docker context `desktop-linux` (local Docker Desktop named pipe). The temporary, ignored `.env.task23` contained only synthetic DB/API settings and was not committed. |
| 2026-10-27 05:59:24.570Z | Baseline: DB, API, Prometheus, Grafana, Loki, and Tempo were healthy; collector was running. API `/health` returned HTTP 200; `/ready` returned `{"status":"ready"}`. Prometheus target `api:8000` was `up`, `up{job="api"}` was `1`, and the alert was inactive. |
| 2026-10-27 06:01:54.630Z | Issued `docker compose --env-file .env.task23 -p benchscope-task23-f5ecf142d10e4cad873d5ad4299a1b4d stop api`; API stop completed at 06:01:55.327Z. No other service was stopped. |
| 2026-10-27 06:02:27.633Z | Pending observed: `/health` and `/ready` returned no HTTP response; Prometheus query was `api:8000=0`, target health `down`, `ALERTS{alertname="BenchScopeApiUnavailable"}` had state `pending`, value `1`. Grafana dashboard returned HTTP 200 and its “Local API availability alert” panel displayed `pending`. |
| 2026-10-27 06:04:48.643Z | Firing observed after 173.3 seconds stopped: both API endpoint checks still had no HTTP response; `up` remained `0`; alert state/series was `firing`, value `1`; Grafana dashboard returned HTTP 200. Its alert panel showed the pending and firing states. Compose showed only the API exited (143); DB and observability services remained healthy/running. |
| 2026-10-27 06:05:20.988Z | Before recovery, `pg_isready` reported the disposable DB accepting connections. Sanitized API configuration: `APP_MODE=local`, `APP_ENV=development`, `LOCAL_AUTH_BYPASS=false`, database target `db:5432/benchscope_incident` (credentials redacted). DB config was synthetic user `incident`, database `benchscope_incident` (password redacted). |
| 2026-10-27 06:05:20.988Z | Relevant sanitized logs showed API readiness health checks returning 200 before the stop and a graceful Uvicorn shutdown; PostgreSQL initialization completed and the database reported ready to accept connections. No API trace is expected while its process is stopped. |
| 2026-10-27 06:05:37.435Z | Started only the same project's API. `/ready` succeeded at 06:05:41.545Z. At 06:05:56.601Z, API health was HTTP 200, Prometheus returned `up=1`, and the active alert list no longer contained `BenchScopeApiUnavailable`. |
| 2026-10-27 06:08:26.569Z | Ran the exact project-scoped `promtool test rules /etc/prometheus/api-alert-test.yml`; it returned `SUCCESS` (exit 0) at 06:08:27.653Z, including pending, firing, and resolution expectations. |
| 2026-10-27 06:09:14.666Z | Removed only this project with `down --volumes --remove-orphans --rmi local`; removed `.env.task23`. Cleanup completed at 06:09:18.374Z. |

Compose published only loopback endpoints: DB `127.0.0.1:15441->5432`,
API `127.0.0.1:8000->8000`, OTLP `127.0.0.1:4318->4318`, Prometheus
`127.0.0.1:9090->9090`, Loki `127.0.0.1:3100->3100`, Tempo
`127.0.0.1:3200->3200`, and Grafana `127.0.0.1:3000->3000`. The API retained
its internal `db:5432` database URL. `POSTGRES_PORT=15441` changed only the
disposable database's host publication. The listener previously observed on
host port 5432 was not touched.

## Cause, impact, and recovery

The injected cause was the deliberate stop of only this project's API. It
remained stopped for about 222.1 seconds through the API restart. Impact was
limited to the disposable local stack; PostgreSQL and the observability
services stayed healthy. No product/database root cause was inferred and no
application code or alert rule was changed. Recovery was starting the stopped
API after confirming DB health and sanitized API/DB configuration/logs.

## Cleanup verification

After teardown, the exact project had zero containers, volumes, networks, or
project-built API images. `.env.task23` was absent. The selected published
ports `8000`, `4318`, `9090`, `3100`, `3200`, `3000`, and `15441` had no
listeners. No other Compose project or the original 5432 listener was
stopped, altered, or cleaned up.
