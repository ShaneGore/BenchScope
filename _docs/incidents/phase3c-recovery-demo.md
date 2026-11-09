# Phase 3C — Independently verified AI incident recovery

**Status: completed; recovery independently verified in a disposable stack.**
This document records a disposable, local-only recovery demonstration. It does
not modify staging, production, GitHub environments, branch protection, or any
hosted resource. All credentials are generated locally and are never committed.

## Baseline (before the demonstration)

| Item | Value |
|---|---|
| Repository branch used for this work | `feat/phase3c-verified-recovery` |
| Base commit | `c47adc16aa3f4135a2cc1da81ff4cab16b6753b6` (`main` after PR #66) |
| PR #62 | merged as `12c32064f9ef3ac36539fa26cd7a9ccd5315b82b` |
| PR #65 | merged as `2be61f5cfc502a0425719f5f97705e716fb2061e` |
| PR #66 | merged as `c47adc16aa3f4135a2cc1da81ff4cab16b6753b6` |
| PRs #63 / #64 | closed, unmerged, retained as demonstration evidence |
| Faulty demo revision | `79ce43c05dd023d81a660507f2db55d571639444` on `demo/incident-repair-outage-20261109` |

The prior genuine repair run remains the source of the candidate patch:

- incident `3839ac43-47f4-4f27-b3fa-ea9ac62a29f9`;
- repair job `2d68ced3-e56c-4d4b-b66a-58c1a4a62e05`;
- one verified `gpt-6-luna` request, reported premium cost 1;
- draft PR #64, head `b47a520325c189d62167035cf87d8bc6a6acb057`, 5/5 CI green.

No new model invocation is made in this demonstration. The patch is a
**clearly labelled replay** of the genuinely generated candidate. This document
does not claim that the replay is a new end-to-end model run.

## Intended fault

The disposable API is built from the evidence-only demo revision, which changes
`backend/app/main.py` to:

```python
if request_telemetry.enabled and False:
    app.mount("/metrics", request_telemetry.metrics_app)
```

Telemetry is enabled because the local API runs with `APP_MODE=local`, so the
service is healthy but never mounts `/metrics`.

## Observable failure

1. `GET /health` and `GET /ready` still return HTTP 200.
2. `GET /metrics` returns HTTP 404.
3. Prometheus's `api` target becomes `down` and `up{job="api"}` is `0`.
4. After the Grafana rule's 1-minute `for` period, the managed
   `BenchScopeApiUnavailable` alert becomes `firing`.
5. Grafana posts an authenticated webhook to the private `alert-receiver`.
6. The receiver persists an incident with complete evidence and queues a repair
   job bound to the faulty revision.

## Alert and investigation path

- Grafana's provisioned rule evaluates `up{job="api"}` from Prometheus. It
  notifies only the local receiver through the Compose network; no external
  contact point is used.
- The receiver requires the exact bearer from its Compose secret file and
  accepts only `BenchScopeApiUnavailable` firing/resolved payloads.
- The persisted incident retains the sanitized Prometheus, Loki, and Tempo
  evidence, audit events, application revision, and repair-job status.
- The worker is **not** started for this replay, because that would create a
  second model invocation and a second draft PR. Its claim/validation path is
  represented by the prior run's audit evidence and is replayed below with the
  recorded patch.

## Candidate patch and isolated validation

The candidate is the complete PR #64 diff:

- `backend/app/main.py`: restore `if request_telemetry.enabled:`;
- `backend/tests/test_health_contract.py`: add
  `test_metrics_endpoint_is_mounted_when_telemetry_is_enabled`.

Before the running service is touched, the patch is applied to a separate
disposable worktree at the faulty revision and validated with the same worker
code paths:

1. parse/allowlist validation against `REPAIR_SOURCE_FILES`;
2. `apply_repair_patch` with `git apply --recount --whitespace=error-all`;
3. `_validate_application_change` and `_validate_regression_tests`;
4. `run_repair_tests` in the isolated `benchscope-repair-test:py312` container.

The AI-generated regression test is supplementary evidence only.

## Replacement of the running service

After explicit owner approval:

1. Apply the same candidate patch to the disposable checkout that built the
   running faulty API.
2. Commit the repair in that disposable checkout only and record the repaired
   revision identifier.
3. Rebuild only the `api` image and recreate only the `api` container in the
   same Compose project. The database and observability services remain up.
4. Leave staging, production, and all GitHub settings untouched.

## Independent recovery verification

Recovery is established only if all of these independent checks pass:

- `GET /version` on the repaired API returns the repaired revision;
- `GET /metrics` reaches a non-empty Prometheus exposition body. The mounted
  app answers `/metrics` with a `307` redirect to `/metrics/`, which returns
  `200`; the unfaulted `main` code behaves identically, and Prometheus follows
  the redirect;
- the Prometheus target is `up` and `up{job="api"}` is `1`;
- the Grafana `BenchScopeApiUnavailable` rule is normal/not firing;
- the receiver records a resolved alert and the persisted incident changes to
  `alert_status=resolved`;
- `/health`, `/ready`, the anonymous demo runs endpoint, and the existing smoke
  checks still pass;
- the pre-repair failure condition (`/metrics` 404 and `up=0`) is no longer
  present.

A passing AI-generated test alone is not accepted as recovery proof.

## Cleanup

- `docker compose ... down --volumes --remove-orphans --rmi local` for the
  exact disposable project only.
- Remove the disposable worktrees and the ignored local `.env`/secret files.
- Confirm no project containers, volumes, networks, or images remain and that
  the disposable loopback ports have no listeners.
- Do not stop or alter the unrelated `benchscope` stack or any other project.

## Abort criteria

Stop without applying the repair if any of these is true:

- owner approval for the disposable application is absent;
- the selected faulty revision does not match `79ce43c...`;
- `/metrics` is not 404 while `/health` and `/ready` are 200;
- the Grafana alert does not fire or the receiver does not persist complete
  evidence;
- the candidate patch is not the recorded PR #64 diff;
- allowlist, application-boundary, or regression-test validation fails;
- isolated tests fail;
- the disposable stack, ports, or credentials cannot be kept local;
- any step would touch staging, production, GitHub settings, or unrelated
  containers.

## Automatic versus owner-approval actions

Safe to perform automatically:

- read repository and prior evidence;
- create and validate disposable worktrees;
- start the disposable Compose stack on free loopback ports;
- reproduce the fault and trigger the local Grafana alert;
- read receiver, database, Prometheus, and Grafana evidence;
- apply and test the recorded patch in an isolated worktree;
- capture sanitized evidence and tear down the disposable stack.

Requires explicit owner approval:

- applying the candidate patch to the checkout/image that is running the
  affected disposable API, and recreating that API container.

## Execution record

All timestamps are UTC. The record below is transcribed from the disposable
stack's own outputs, the receiver database, and the saved validation logs.

### Revisions and artifacts

| Item | Value |
|---|---|
| Faulty revision (running before repair) | `79ce43c05dd023d81a660507f2db55d571639444` |
| Repaired revision (local commit, disposable checkout only) | `4714610a0e90ba3fde7f0d92e4b2b29f0188c00f` |
| Repaired commit timestamp | `2026-11-09T03:55:10Z` |
| Repaired image | `sha256:ae31c06e8447acec97c229ddd01fec975fa2e7b00f75b43b3956e43ce024fb02` |
| Image revision label | `4714610a0e90ba3fde7f0d92e4b2b29f0188c00f` |
| Compose project | `benchscope-phase3c-20261109` |
| Incident | `33173824-ad32-412e-a158-aabe24c5a310` |
| Repair job | `4783dc6e-c4d6-49ad-bafb-59d69090f4dc` |
| Alert fingerprint | `caf1593e7bd159d2` |

The repaired commit exists only in the disposable worktree. It was not pushed,
merged, or deployed outside the disposable project, and PR #64 remains closed
and unmerged.

### Timeline

| Time (UTC) | Event and result |
|---|---|
| 2026-11-09T03:49:21Z | Started the disposable project on loopback ports with generated local credentials. |
| 03:50:24Z | Fault reproduced: `/health` 200, `/ready` 200, `/version` `79ce43c...`, `/metrics` 404, frontend 200, Prometheus `up{job="api"}` = `0`. |
| 03:51:20Z | Grafana `BenchScopeApiUnavailable` active; `startsAt` `03:51:20Z`; fingerprint `caf1593e7bd159d2`; route `benchscope-alert-receiver`. |
| 03:51:20.026Z | Incident `33173824...` persisted as `firing` / `complete` / `queued` at revision `79ce43c...`. |
| 03:51:20.102Z | Repair job `4783dc6e...` queued with `attempts=0`; audit events `evidence_collected`, `investigation_dispatch`, `repair_dispatch`. |
| 03:53:19Z | Isolated replay validation passed: `changed_paths=backend/app/main.py,backend/tests/test_health_contract.py`; `application_boundary=valid`; `regression_test_boundary=valid`; `isolated_tests=passed`. |
| 03:54:50Z | Pre-apply recheck: faulty worktree clean at `79ce43c...`; all nine services healthy. |
| 03:54:56Z | Applied `pr64-clean.diff` through the worker's own `apply_repair_patch`; exactly the two allowlisted files changed. |
| 03:55:10Z | Committed the replay locally as `4714610...`; updated the disposable `APP_REVISION`. |
| 03:55:26Z–03:55:36Z | Rebuilt only the `api` image (`sha256:ae31c06e...`). |
| 03:55:41Z–03:55:48Z | Recreated only the `api` container; it became healthy at `03:55:42.655Z`. The other eight services kept their previous uptime. |
| 03:55:54Z | `/health` 200, `/ready` 200, `/version` `{"revision":"4714610..."}`, frontend 200; `/metrics` `307` to `/metrics/`; followed body 200, 157 bytes; Prometheus `up{job="api"}` = `1`. |
| 03:56:00Z | `/metrics/` 200 with Prometheus exposition (`# HELP` / `# TYPE` lines); no redirect needed on the trailing-slash path. |
| 03:56:12Z | Independent health smoke passed: health, readiness, anonymous demo runs, synthetic non-empty records, immutable anonymous records, frontend reachable. |
| 03:56:18.675Z | Receiver updated the incident: `alert_status=resolved`, `ends_at=03:55:50Z`, `resolved_at=03:56:18.675499Z`. |
| 03:56:18.676Z | Audit `alert_resolved` / `accepted` / `resolved_notification`; second receiver `POST /grafana/v1` returned 200. |
| 03:58:13Z | Prometheus `ALERTS{alertname="BenchScopeApiUnavailable"}` is empty; Grafana alertmanager alert list is `[]`; `up{job="api"}` = `1`. |
| 03:58:23Z | Container image label and `/version` both report `4714610...`; followed `/metrics` body 200. |
| 04:01:43Z | Repaired-checkout verifier: 524 backend tests passed, 1 failed from a pre-existing demo-branch revision-isolation defect; the verifier stops before the frontend stages (see below). |

### Isolated validation scope

`run_repair_tests` executed in the pinned `benchscope-repair-test:py312` image
with `--network none`, `--read-only`, `--cap-drop=ALL`,
`--security-opt=no-new-privileges`, `--pids-limit=128`, `--memory=2g`,
`--cpus=2`, and user `65534:65534`. It ran:

- the trusted `test_app.py` and `test_health_contract.py`;
- the repaired worktree's `tests/test_health_contract.py`;
- `ruff check` and `ruff format --check` on `app/main.py` and
  `tests/test_health_contract.py`.

The AI-generated regression test is included in that run but is not the
recovery proof. The independent checks below are the proof.

### Persisted evidence

The receiver stored a 365-byte sanitized evidence object with
`status=complete`: Prometheus `api=down` with `status=ok`, Loki `status=ok`
with no entries in the 300-second lookback, Tempo `status=ok` with no traces,
and all truncation flags `false`. The evidence contains no raw logs, prompts,
credentials, or benchmark artifacts.

### Independent recovery evidence

| Check | Pre-repair (03:50:24Z) | Post-repair |
|---|---|---|
| `/version` | `79ce43c...` | `4714610...` |
| `/metrics` (follow redirects) | 404 | 307 → `/metrics/` 200, non-empty exposition |
| Prometheus `up{job="api"}` | `0` | `1` |
| Prometheus `ALERTS` for the rule | `firing` | empty |
| Grafana active alerts | active | `[]` |
| Incident `alert_status` | `firing` | `resolved` |
| Audit resolution event | absent | `alert_resolved/accepted/resolved_notification` |
| `/health`, `/ready`, frontend | 200 | 200 |
| Anonymous demo runs (health smoke) | not run | passed, including immutability |
| Repaired image source (`/app/app/main.py`) | `if ...enabled and False:` | `if request_telemetry.enabled:` |
| In-container probe of `/metrics/` | 404 | 200 with exposition |

The repaired line is identical to the unfaulted `main` line. A control check
against the current `main` app with telemetry enabled returned the same
`307 → /metrics/ 200` behaviour, so the redirect is inherent to the mounted
metrics app rather than an artifact of the repair. Prometheus follows the
redirect and reports the target `up`.

### Repaired-checkout regression run

The one-command verifier was also run from the repaired disposable checkout.
It reported **524 backend tests passed, 1 failed**. Ruff, the container
browser/API persistence check, and the 524 backend tests passed; the verifier
stops at the first failing gate, so the frontend stages did not run in this
checkout. The single failure was
`tests/test_alert_receiver.py::test_firing_alert_queries_fixed_read_only_sources_and_persists_sanitized_evidence`,
which expected `blocked`/`escalated` but received `queued`/`queued`.

This failure is **not** caused by the candidate patch:

- the same test passes on a pristine `79ce43c` checkout when `APP_REVISION` is
  unset, and fails identically when `APP_REVISION` is set to the checkout SHA;
- the evidence-only demo branch's `scripts/verify.py` predates PR #65 and
  forwards an inherited `APP_REVISION` into the backend test environment;
- current `main` (including `2be61f5`) strips `APP_REVISION` and the other
  host variables before running the backend suite, and the full verifier on
  `main` passed 525 tests.

The authoritative one-command result is therefore the full pass on `main` at
`c47adc1`; the demo branch remains evidence-only and is not proposed for
merge.

### What this establishes, and what it does not

Established:

- a genuine local Grafana alert on the faulty revision produced an
  authenticated incident with complete evidence and a revision-bound repair
  job;
- the recorded GPT-6 Luna candidate, replayed through the worker's own patch,
  boundary, and isolated-test validators, fixed the observable failure when
  applied to the affected disposable artifact;
- recovery was demonstrated by independent checks: scrape health, alert
  resolution, resolved incident and audit trail, version identity, and the
  existing health smoke. The AI-generated test was not used as proof.

Not established:

- this replay is not a new model invocation and not a new automatic worker run;
- the repair job remains `queued` because no worker was started, so the
  end-to-end automatic executor is not exercised here;
- the fixed recovery executor remains disabled pending proof of race-safe
  ownership;
- nothing here demonstrates a hosted production alert-to-release flow.

### Cleanup

Teardown ran at `2026-11-09T04:03:31Z`–`04:03:35Z` for project
`benchscope-phase3c-20261109` only:

- `down --volumes --remove-orphans --rmi local` removed all nine containers,
  the project network, the five project volumes, and the three locally built
  project images;
- the three disposable worktrees (`faulty`, `isolated`, `baseline`) were
  removed and pruned;
- the ignored `.env.phase3c` and generated receiver secret were removed with
  the worktree;
- leftover `benchscope-verify-*` images from local verifier runs were removed;
- post-cleanup checks: project containers `0`, project networks `0`, project
  volumes `0`, and no listener on any of the nine loopback ports;
- the unrelated `benchscope` stack remained running and was not touched.

Retained sanitized evidence: the recorded diff (`pr64-clean.diff`), the
isolated validation log, the verifier logs, and the applied commit patch
(`repaired-commit.patch`). These contain no credentials or owner data.
