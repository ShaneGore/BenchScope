# Known Limitations

Dated 2026-11-10, `main` at `dd8064ac6e3ebf505acb23fa01f5da051e07747f`. This
list is deliberately blunt: it separates what is verified, what is
code-and-test-supported, and what remains incomplete.

## Verified in Phase 4

- Backend, frontend, contract and browser-journey tests pass through one
  command on current `main` (531 backend, 102 frontend, 10 journeys).
- The containerised core stack (frontend, API, PostgreSQL) starts and persists
  data across an API restart.
- Pages, staging API and the production demo API are reachable; staging and
  production `/version`, `/health` and `/ready` were checked.
- Production promotion, rollback and restoration each passed 13/13 smoke checks
  and retained the same four synthetic run UUIDs at the same schema head.

## Application

- The private benchmark runner adapter is **not integrated**. Issue
  [#25](https://github.com/ShaneGore/BenchScope/issues/25) remains open, and
  there is no authoritative private runner wrapper contract. The runner seam is
  exercised with synthetic adapters only.
- Real private benchmark execution has not been performed against the public
  application, and its inputs, expected outputs and raw results are not
  published.
- The real runner's process-tree cleanup is not proven by source inspection
  alone; Windows safety is tested with synthetic runners.
- `quality_score` remains `null` until an authoritative scoring definition
  exists.
- Global rate-limiting specifics are undefined.

## Deployment

- The public Pages frontend is **staging-backed**. Production is an API-only
  demonstration, so production frontend-to-API connectivity is not exercised.
- Production uses free tiers (Render Free, Neon Free) with no SLA, cold starts,
  limited deploy history and no backup guarantee.
- Production authentication uses a separate Clerk **Development** application
  for synthetic smoke identities; there is no Clerk Production instance and no
  public production frontend auth.
- Production approval is a **self-approval** gate: the repository owner is the
  only required reviewer (`prevent_self_review=false`).
- The main ruleset requires **zero approving reviews**, so independent code
  review is procedural, not enforced.
- Production rollback is an **application revision** rehearsal. Migrations are
  forward-only; no database downgrade, restore or point-in-time recovery was
  performed. A rollback is only safe between schema-compatible revisions.
- Neon Free history and its single manual snapshot are not a production backup.
- The live static frontend content is not SHA-stamped; the Pages deployment
  record identifies its source SHA.

## Observability and alerting

- Observability dashboards, the correlated trace and alerting are verified in
  **local Docker Compose**, not as a hosted monitoring stack. Hosted staging and
  production do not run Prometheus, Tempo, Loki or Grafana.
- The observability correlation evidence was produced at revision `12c3206` and
  was not re-executed during Phase 4.
- Alerting is local; the production demo API does not deliver alerts to the
  receiver.

## Supervised AI repair — what is and is not proven

- The repair worker is started explicitly and is **operator-supervised**. Its
  host process is not OS-isolated, and it can use the operator's existing GitHub
  CLI login, which is not least-privilege credential isolation.
- It does not merge, release or recover hosted production. The automatic
  recovery executor is disabled.
- Repair scope is limited to the metrics enable condition, the literal health
  response and health-contract tests. Automated checks cannot prove that a new
  regression test is meaningful, so each draft needs human review.
- A lost worker lock connection during an active job has not been proven safe;
  do not run multiple workers or leave the worker unattended. A timed-out CI
  watch leaves its draft PR for manual follow-up.
- The repair job receiver persists eligible jobs but does not itself execute a
  model or recovery action. Recovery requires explicit approval; a successful
  restart reports `verification_required` rather than resolving the incident
  without post-checks.

### Repair development history (historical, kept for honesty)

- A local synthetic probe using Copilot CLI 1.0.105 produced a schema-validated
  `gpt-6-luna` patch for two synthetic files that passed `git apply --check`.
  The probe did not use a persisted incident or execute generated code, and the
  CLI tool controls are not proof of OS isolation.
- The bundled CLI 1.0.81 lacks `--sync-session`; use a compatible installation
  through `BENCHSCOPE_COPILOT_CLI`.
- Several earlier disposable incidents escalated before tests or PR creation:
  one as `patch_rejected`, another at `8ba618d` after initial checks, another at
  `ee125cd` as `patch_apply_failed`. The worker now persists a sanitized,
  stage-specific failure code and asks for exact context with `git apply
  --recount`. These failures do not establish the precise cause of each
  rejection, and later runs should not be read as proof the retry path was
  exercised for those exact cases.
- On 2026-11-09, two supervised runs on `demo/incident-repair-outage-20261109`
  completed the genuine alert-to-draft-PR path. Run 1 (`5838236`) persisted
  incident `e94c84b0`, passed isolated tests and opened draft PR #63; it recorded
  `ci_failed` only because the check watch raced workflow registration, and all
  five checks later passed. After the watch fix (`79ce43c`), run 2 persisted
  incident `3839ac43`, re-enabled the metrics mount with a regression test,
  opened draft PR #64 and recorded `ci_passed` with 5/5 green. Neither PR was
  merged or released.
- Phase 3C replayed the recorded PR #64 patch for a fresh disposable incident
  (`33173824…`, job `4783dc6e…`) at faulty revision `79ce43c`. With owner
  approval the patch was applied only to the affected disposable checkout, and
  only the API image/container were rebuilt. Independent checks confirmed
  `/metrics`, Prometheus `up=1`, Grafana resolution and incident `resolved`. This
  is a labelled replay, not a new model invocation, and nothing was merged,
  released or deployed outside the disposable project. See
  [phase3c-recovery-demo.md](../incidents/phase3c-recovery-demo.md).
- The evidence-only demo branch still carries the pre-PR-#65 verifier and fails
  one revision-isolation test when `APP_REVISION` is inherited. The authoritative
  one-command result is the current `main` run in the
  [dated log](./submission-checklist.md#dated-verification-log).

## Agent team

- The QA custom agent definition previously named an unavailable model; the PM
  and Software Engineer definitions used another unavailable display name. All
  three now specify the CLI model ID `gpt-6-luna`, but the QA agent still failed
  to launch in a 2026-11-09 Copilot SDK session because its configured model
  display name was unavailable. A CLI model probe does not establish that the
  custom agent can launch.

## Privacy and hosting

- Hosted mode never runs benchmarks; `/api/v1/benchmark/capabilities` returns
  `{"enabled":false}`.
- Only selected approved benchmark aggregate summaries are publicly served;
  private prompts, responses, test content and paths are not.
- Two historical demo configurations were run through the paid OpenRouter API.
- The deployment uses free-tier services and is a course demonstration, not an
  enterprise production system.

## Deferred work

- Resolve the private runner adapter contract and integrate it (issue #25).
- Define `quality_score` and rate limiting.
- Decide whether a hosted observability stack or a production frontend is in
  scope.
- Add a second maintainer so independent review can be required.
