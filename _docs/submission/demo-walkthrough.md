# Reviewer demonstration walkthrough (5–8 minutes)

A scripted walkthrough for a course reviewer or portfolio visitor. It needs no
private credentials and never runs the private benchmark. Timings are
approximate; total ≈ 7 minutes.

**Legend:** 🟢 live and clickable · 🟡 recorded evidence in the repository ·
⚪ historical evidence, not interactive.

**Open before you start:** <https://shanegore.github.io/BenchScope/> and
<https://github.com/ShaneGore/BenchScope>.

> Free-tier cold start: the first API call can take ~1 minute. If the demo shows
> a loading error, press **Retry**. Do not interpret a cold start as a failure.

---

## 0. Introduction — 30 s 🟢

**Narration:** "BenchScope is a local-first observatory for coding-benchmark
results. Local-LLM evaluations usually end up as scattered JSON files; BenchScope
imports a supported result once, keeps an inspectable history, and compares
coding accuracy, generation speed and configuration choices — without ever
publishing the private benchmark."

**Screen:** README top section.

---

## 1. The public application — 45 s 🟢

1. Open <https://shanegore.github.io/BenchScope/>.
2. Confirm the landing page loads without signing in.
3. Point out the demo is read-only and needs no account.

**Expected:** dashboard with published configurations; no sign-in prompt.

**Screenshot to capture:** landing page (`_docs/images/dashboard.png` is the
committed example).

---

## 2. Anonymous demo — 60 s 🟢

1. Navigate to **`#/demo`** (or click the demo entry point).
2. Show the list of 15 configurations — 13 local, 2 hosted OpenRouter — each
   recording 47 tasks.
3. Open one result (`#/demo/runs/demo-run-01`).
4. Highlight that some metrics are **unavailable**, not zero.

**Expected:** run detail shows model, quantisation, reasoning setting, task
outcomes, and `null` where a metric was not measured.

**Narration:** "This catalogue is an immutable synthetic fixture derived from
the owner's Local-LLM-Coding-Benchmark-v2 aggregate summaries. It is not
produced by BenchScope and is not a controlled ranking."

---

## 3. Comparison — 60 s 🟢

1. Go to **`#/demo/compare`**.
2. Select two or more configurations.
3. Show the side-by-side metrics and the explicit configuration differences.

**Expected:** comparison renders pass rate and throughput where available; the
UI explains that differing reasoning/MTP/context settings limit comparability.

**Screenshot to capture:** comparison view (`_docs/images/comparison.png` is the
committed example).

**Narration:** "Missing measurements stay missing. Incomplete task coverage is
never presented as a complete score."

---

## 4. Architecture — 45 s 🟢/🟡

Open the README architecture diagram and the stack table.

**Narration:** "React + Vite + TypeScript on GitHub Pages; FastAPI on Render;
PostgreSQL on Neon with Alembic migrations; Clerk for hosted auth; and a
local-only benchmark runner seam that hosted mode never mounts."

**Evidence:** [README — Architecture](../../README.md#architecture),
[boundaries](../architecture/boundaries.md).

---

## 5. Single-command startup and verification — 60 s 🟡

In the repository:

```powershell
uv run --no-project python scripts/start.py      # start the full stack
uv run --no-project python scripts/verify.py     # run every check
```

**Narration:** "One command starts the frontend, API and database; one command
runs lint, 531 backend tests, 102 frontend tests, the production build, the API
contract check, a container browser check and 10 browser journeys."

**Expected on screen:** the recorded Phase 4 result.

**Evidence:** [Dated verification log](./submission-checklist.md#dated-verification-log).

**Fallback:** if Docker is unavailable, show the log rather than attempting a
live run.

---

## 6. Public task tracker and acceptance criteria — 45 s 🟢

1. Open <https://github.com/ShaneGore/BenchScope/issues>.
2. Show a closed issue with groomed acceptance criteria, implementation notes
   and a QA verdict (e.g. [#56](https://github.com/ShaneGore/BenchScope/issues/56),
   [#70](https://github.com/ShaneGore/BenchScope/issues/70)).
3. Show [#25](https://github.com/ShaneGore/BenchScope/issues/25) still open and
   labelled `status: in-progress`.

**Narration:** "The tracker is the single source of truth. The open issue is a
genuine deferred item, not a hidden failure: the private benchmark adapter
contract is intentionally not integrated."

---

## 7. Agent team and context management — 45 s 🟡

Open [`AGENTS.md`](../../AGENTS.md) → [`_docs/process.md`](../process.md) →
[`_docs/team/`](../team/).

**Narration:** "Three roles — PM grooms, engineer implements, QA verifies and
does not fix code. The orchestrator closes an issue only after QA passes.
`AGENTS.md` is a short index into modular docs, so an agent loads only the
context a task needs."

**Evidence:** [`.github/agents/`](../../.github/agents/).

---

## 8. Automated CI and the five required checks — 45 s 🟢

1. Open Actions → **CI**.
2. Open run [`42714645314`](https://github.com/ShaneGore/BenchScope/actions/runs/42714645314).
3. Show `backend`, `frontend`, `journey`, `container-images`,
   `backend-windows` all green.
4. Open Settings → Rules → "Protect main" to show the five required checks, PR
   requirement, thread resolution and **0 required approvals**.

**Narration:** "Every PR must pass all five checks. The zero-approval rule is an
honest limitation — review is procedural, not enforced."

---

## 9. Automatic staging deployment — 30 s 🟢

1. Open run [`42714879812`](https://github.com/ShaneGore/BenchScope/actions/runs/42714879812)
   (Deploy Backend) and [`42714879726`](https://github.com/ShaneGore/BenchScope/actions/runs/42714879726)
   (Deploy GitHub Pages).
2. Open <https://benchscope-staging-api.onrender.com/version>.

**Expected:** `{"revision":"dd8064ac6e3ebf505acb23fa01f5da051e07747f"}`.

---

## 10. Manual production promotion and rollback — 75 s 🟢/🟡

1. Open **Promote Production** run [`42726216077`](https://github.com/ShaneGore/BenchScope/actions/runs/42726216077).
2. Point out `workflow_dispatch`, the protected `production` environment gate,
   the SHA, migrations, deploy hook, `/version` verification and 13/13 smoke.
3. Open rollback [`42727553382`](https://github.com/ShaneGore/BenchScope/actions/runs/42727553382)
   and restore [`42728234322`](https://github.com/ShaneGore/BenchScope/actions/runs/42728234322).
4. Open <https://benchscope-production-api.onrender.com/version>.

**Narration:** "Production is a separate API and database. Promotion is manual
and protected. The rollback rehearsal redeployed the previous schema-compatible
revision, passed 13/13 smoke, kept the same four synthetic run UUIDs, and then
restored the approved revision. No database downgrade was performed."

**Evidence:** [production-release.md](../architecture/production-release.md#rollback-and-restoration-evidence-executed)
and <https://github.com/ShaneGore/BenchScope/issues/70#issuecomment-6755310213>.

**Do not claim** the Pages frontend was promoted to production — it remains
staging-backed.

---

## 11. Correlated observability — 45 s 🟡

Open [metric-trace-link.md](../observability/metric-trace-link.md).

**Narration:** "A synthetic `GET /api/v1/runs` produced a Prometheus exemplar, a
Tempo span and a Loki request log sharing trace
`802cccdd7ebb4fc79cdd9750c0f8063d`. Grafana maps the exemplar to Tempo, so a
viewer can follow a metric to a trace. This is local Docker Compose evidence,
not hosted observability."

**Fallback:** show the committed document; do not rebuild the stack during the
walkthrough unless time allows.

---

## 12. Firing alert and supervised repair — 75 s 🟡/⚪

1. Open [phase3c-recovery-demo.md](../incidents/phase3c-recovery-demo.md).
2. Show the fault: `/health` and `/ready` 200 while `/metrics` 404, Prometheus
   `up=0`, Grafana alert fires after its `for` period.
3. Show the authenticated receiver persisting an incident and repair job.
4. Show the GPT-6 Luna investigation, allowlisted patch, isolated tests and
   draft PRs [#63](https://github.com/ShaneGore/BenchScope/pull/63) and
   [#64](https://github.com/ShaneGore/BenchScope/pull/64).

**Narration:** "The agent wakes on a real alert and produces a validated,
CI-checked draft repair. It does not merge or release. A human approves."

---

## 13. Independently verified recovery — 45 s ⚪

Still in [phase3c-recovery-demo.md](../incidents/phase3c-recovery-demo.md): show
that the recorded patch was replayed for a fresh disposable incident, applied
with owner approval only to the affected disposable checkout, and recovery was
independently confirmed — `/metrics` restored, `up=1`, alert cleared, incident
`resolved` with an audit event.

**Narration:** "This was a labelled replay in a disposable environment, not a
new autonomous hosted fix. That distinction is deliberate and documented."

---

## 14. Security and limitations — 30 s 🟢

Open [README — Security and privacy](../../README.md#security-and-privacy) and
[known limitations](./known-limitations.md).

**Narration:** "Private benchmark material never enters the repository or
telemetry. Ownership is server-side. Hosted mode never mounts benchmark routes.
Known limits: the private adapter is not connected, observability is local,
hosted AI repair is disabled, and free tiers have no SLA."

---

## Checklist

| Requirement | Where |
|---|---|
| Public app opens | <https://shanegore.github.io/BenchScope/> |
| Problem and expected behaviour | [README](../../README.md) |
| Demo explored | `#/demo`, `#/demo/compare`, `#/demo/runs/demo-run-01` |
| Specification and tracker | [#issues](https://github.com/ShaneGore/BenchScope/issues), [plan](../plan.md) |
| Agent team and process | [`AGENTS.md`](../../AGENTS.md), [process](../process.md) |
| Startup and tests reproduced | [submission checklist](./submission-checklist.md#dated-verification-log) |
| CI/CD and rollback evidence | [rubric matrix §9](./rubric-evidence.md#9-cicd) |
| Observability | [metric-trace-link.md](../observability/metric-trace-link.md) |
| Alerting and repair | [phase3c-recovery-demo.md](../incidents/phase3c-recovery-demo.md) |
| Security and limits | [security review](./security-review.md) |
| All 12 criteria | [rubric evidence](./rubric-evidence.md) |

## Screenshots to capture

1. Landing page / dashboard.
2. Demo list with 15 configurations.
3. A run detail showing an unavailable metric as unavailable.
4. Comparison of 2–3 configurations.
5. CI run with five green jobs.
6. Promote Production run with the environment approval.
7. Grafana alert firing and the resolved incident.
8. Draft repair PR with five green checks.

Do not fabricate screenshots or edit logs. If a live service is cold, show the
linked workflow run instead.
