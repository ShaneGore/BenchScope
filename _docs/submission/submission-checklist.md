# Submission checklist and dated verification log

The criterion-by-criterion assessment lives in the
[official rubric evidence matrix](./rubric-evidence.md). This page is the
supporting record: the exact verification runs, their revision, and the owner
actions that remain.

**Baseline:** `main` at `dd8064ac6e3ebf505acb23fa01f5da051e07747f` (2026-11-10).

## Phase 4 status at a glance

| Area | State |
|---|---|
| Full-stack app | Working locally and hosted; single-command start and verify |
| Tests | 531 backend, 102 frontend, 10 browser journeys — passed at Phase 4 |
| Containers | `compose.yaml` core stack + observability overlay |
| Deployment | Pages + staging API automatic; production API manual/protected |
| CI/CD | Five required checks; staging CD; manual production; rehearsed rollback |
| Observability | Local correlated metrics/traces/logs with shared trace ID |
| Alerting | Real Grafana availability alert; authenticated receiver |
| AI repair | Supervised alert→draft-PR; recovery independently verified in a disposable environment |
| Private runner | Not integrated; [#25](https://github.com/ShaneGore/BenchScope/issues/25) open |

## Dated verification log

### 2026-11-10 — Phase 4, current `main` (`dd8064a`)

`uv run --no-project python scripts/verify.py` on `main` plus the Phase 4
documentation changes:

- Ruff: all checks passed; 65 files already formatted.
- Backend: **531 passed**, no skips, 159 s, disposable PostgreSQL.
- Frontend: **18 test files, 102 tests passed**.
- Production build: passed.
- API contract: `openapi.yaml` regeneration produced no diff.
- Container browser check: built container frontend read an imported result from
  its real API in Chromium.
- Browser journeys: **6 + 3 + 1 = 10 passed** (import/history/comparison,
  demo immutability, ownership, runner lifecycle, base path).
- Persistence after API restart: passed.
- Disposable containers, network, volumes and images removed.

Live checks:

- Staging `/version` = `dd8064ac6e3ebf505acb23fa01f5da051e07747f`; `/health` 200;
  `/ready` `{"status":"ready"}`.
- Production `/version` = `dd8064ac6e3ebf505acb23fa01f5da051e07747f`; `/health`
  200; `/ready` `{"status":"ready"}`; capabilities `{"enabled":false}`.
- Pages HTTP 200; deployed JS references the staging origin (7 matches) and no
  production origin.
- Main CI [`42714645314`](https://github.com/ShaneGore/BenchScope/actions/runs/42714645314): all five jobs success.
- Staging deploy [`42714879812`](https://github.com/ShaneGore/BenchScope/actions/runs/42714879812) and Pages [`42714879726`](https://github.com/ShaneGore/BenchScope/actions/runs/42714879726): success at `dd8064a`.
- Production promotion [`42726216077`](https://github.com/ShaneGore/BenchScope/actions/runs/42726216077), rollback [`42727553382`](https://github.com/ShaneGore/BenchScope/actions/runs/42727553382), restore [`42728234322`](https://github.com/ShaneGore/BenchScope/actions/runs/42728234322): all success, 13/13 smoke.

### 2026-11-09 — Phase 3C verified recovery (durable)

A fresh disposable Grafana alert on faulty revision `79ce43c` persisted incident
`33173824-ad32-412e-a158-aabe24c5a310` and repair job
`4783dc6e-c4d6-49ad-bafb-59d69090f4dc`. The recorded PR #64 GPT-6 Luna patch
passed the worker's allowlist, boundary and isolated-test validators, then was
applied with owner approval only to the affected disposable checkout; only the
API image/container were rebuilt. `/metrics` exposition restored, Prometheus
`up=1`, Grafana alert resolved, incident `resolved` with an audit event. This was
a labelled replay, not a new model invocation. See
[phase3c-recovery-demo.md](../incidents/phase3c-recovery-demo.md).

### 2026-11-09 — Supervised repair runs (durable)

Two supervised runs on the intentionally faulty
`demo/incident-repair-outage-20261109` branch completed the genuine
alert→investigation→patch→isolated-tests→draft-PR path:

- Run 1, revision `5838236`: incident `e94c84b0`, draft PR #63, recorded
  `ci_failed` because the check watch raced workflow registration; all five
  checks later passed.
- Run 2, revision `79ce43c`: incident `3839ac43`, draft PR #64, recorded
  `ci_passed` with 5/5 green.

Neither PR was merged or released; both are closed evidence-only drafts.

### 2026-11-09 — Local observability correlation (durable)

Isolated current-source verifier at `12c3206` matched a Prometheus exemplar,
Tempo trace, Loki request log and anonymous Grafana trace proxy for trace
`802cccdd7ebb4fc79cdd9750c0f8063d`, span `20e0cee9bf281408`. Local, not hosted.
See [metric-trace-link.md](../observability/metric-trace-link.md).

### 2026-11-09 — Verifier isolation fix

PR #65 (`2be61f5`) removed the defect where the container's `APP_REVISION`
leaked into the backend test environment and produced a false failure. The fix
is on `main`; the 2026-11-10 Phase 4 run above is the authoritative current
result.

### Historical results (do not combine with current totals)

- 2026-11-09, `main` at `c47adc1`: Ruff, 525 backend tests, 102 frontend tests,
  build, contract, container check, 10 browser journeys — passed. Superseded by
  the Phase 4 run; the backend total rose to 531 with later merges.
- 2026-11-08, post-CI-gate: 460 backend tests on disposable PostgreSQL.
- 2026-11-07: metric exemplar matched a trace, but from a cached image of
  unknown source; not current-source evidence.

## Submission platform facts (verified 2026-11-10)

Source: <https://courses.datatalks.club/ai-dev-tools-2026/project/project2>.

| Item | Verified value |
|---|---|
| Active attempt | **Project 2** (Project 1 closed as Completed) |
| Deadline | **16 November 2026 (Mon), 23:00**, shown in the viewer's timezone |
| Submission status | **Not verifiable from the public page.** It shows only a login prompt; the owner's account status must be checked while signed in. |
| Required fields | GitHub link to the project; **exact commit ID** to evaluate |
| Optional fields | Up to 14 learning-in-public links; time spent (hours); FAQ contribution URL; certificate name |
| Video/screenshots | Not requested by the submission form |
| Peer review | Three reviews of other participants' projects; voting happens on each project's page |

The project must therefore be submitted with a **specific commit SHA**, not just
the repository URL. Choose the final reviewed `main` commit at submission time.

## Owner actions

### Completed by the agent/repository

- [x] Repository baseline recorded and all environments SHA-verified.
- [x] Phase 4 documentation set written and corrected.
- [x] Rubric evidence matrix and demo walkthrough prepared.
- [x] Security and privacy review performed.
- [x] Production promotion, rollback and restoration evidenced.
- [x] Course deadline and submission fields checked on the public platform page.

### Owner must complete (not agent-verifiable)

- [ ] **Log in and submit Project 2** before 16 November 2026 23:00 (viewer
      timezone). The exact deadline is displayed on the platform.
- [ ] **Supply the exact commit ID** to evaluate. Merge the Phase 4 PR (or choose
      another reviewed `main` commit) and paste that 40-character SHA.
- [ ] **Complete three peer reviews.** Mandatory to pass, independent of the
      rubric score. Voting is on other participants' project pages.
- [ ] Optionally add learning-in-public links, hours spent, FAQ contribution and
      certificate name.
- [ ] Record the submission receipt outside the repository.

### Not yet verified

- The owner's actual submission status while signed in. The unauthenticated public
  page cannot establish whether a draft or submission exists.
- The exact peer-review window and whether reviews must be completed before or
  after the submission deadline.
- Whether the platform enforces a minimum score for peer reviews to count.

## Honest limitations

See [known-limitations.md](./known-limitations.md). The two most likely to affect
a reviewer's score are the supervised (not autonomous) AI repair and the
local-only observability stack.
