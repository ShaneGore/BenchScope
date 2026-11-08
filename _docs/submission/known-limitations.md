# Known Limitations

## Implemented and verified

- Frontend and backend tests pass in CI.
- Docker backend image builds.
- Hosted frontend and backend are deployed.
- Observability and an injected alert with manual recovery were exercised locally; supervised recovery components also have isolated tests.
- Windows process-tree safety foundation is implemented and tested with synthetic runners.

## Implemented but not independently verified

- Full end-to-end synthetic runner integration through the API is represented by tests, but the exact real runner contract is not connected.
- Observability dashboards and alerts are verified in local Docker Compose, not as a hosted production observability stack.

## Blocked or incomplete

- Issue #25 remains open.
- No authoritative private runner wrapper contract is established.
- Real benchmark execution has not been performed.
- `quality_score` remains null.
- The real runner's process-tree cleanup is not proven by source inspection alone.
- The receiver persists eligible repair jobs; it does not itself execute a model or recovery action. Recovery requires explicit approval and a successful restart reports `verification_required` rather than resolving the incident without post-checks. An autonomous alert-to-fix run has not been demonstrated.
- The experimental repair worker is started explicitly in the foreground with `scripts/start.py --observability --repair-worker`; Compose alone does not start it. It requires a clean local checkout and loopback PostgreSQL, and must remain operator-supervised because its host process is not OS-isolated. It can use the operator's existing GitHub CLI login, which is not least-privilege credential isolation. A local synthetic probe using Copilot CLI 1.0.105 produced a schema-validated `gpt-6-luna` patch for two synthetic files that passed `git apply --check`; the CLI event parser and usage output confirmed the selected/effective model and one request, with a reported premium cost of 1. The probe did not use a persisted incident or execute generated code. The CLI tool controls are not proof of OS isolation or complete tool restriction enforcement. The bundled 1.0.81 CLI lacks `--sync-session`; use a compatible installation through `BENCHSCOPE_COPILOT_CLI`. No genuine alert-to-repair run, repair PR, CI check, or release verification has been demonstrated.
- Repair scope is currently limited to the metrics enable condition, literal health response, and health-contract tests. Existing test functions must remain unchanged, but automated checks cannot establish that a new regression test is meaningful. Review each draft and verify recovery independently. A lost worker lock connection during an active job has not been proven safe; do not run multiple workers or leave the worker unattended. A timed-out CI watch leaves its draft PR for manual follow-up.
- A disposable metrics outage produced a real Grafana alert, a persisted incident with complete evidence, and an automatically claimed job. A verified Luna response passed structured-output validation, but the job escalated as `patch_rejected` before tests or PR creation. A separate sanitized diagnostic generated a malformed Git patch whose context also failed with `git apply --recount`; this does not establish the precise reason the incident patch was rejected. The disposable database was removed after its sanitized audit events were captured; this is not evidence of an end-to-end repair or recovery.
- A later supervised synthetic probe reproduced incorrect hunk counts and mismatched context in Luna diffs. The worker now asks for exact context and uses Git's `--recount` while retaining strict context and whitespace checks. One subsequent synthetic Luna patch applied and passed the application and regression-test structure validators. This probe did not originate from an alert, execute generated tests, create a PR, or establish the cause of the earlier incident's rejection.
- A second disposable metrics outage produced a real firing Grafana alert, complete persisted evidence, and an automatically claimed job at revision `eecc744`. It escalated as `patch_rejected` before the `copilot_patch_validated` audit event; no tests or repair PR resulted. The old audit does not identify which pre-validation check failed. The worker now makes at most one additional model request when a proposal omits either required file, records verified usage for each response, and records that specific failure if both proposals omit a file. This change has not yet been demonstrated with another genuine incident.
- At revision `8ba618d`, another disposable alert led to an automatically claimed incident and a verified `gpt-6-luna` response (one request, reported premium cost 1). The response passed the initial patch checks but the job again escalated before tests or a PR. The generic historical audit does not identify which worktree validation failed; the worker now persists a sanitized, stage-specific failure code without storing patch contents.

## Privacy and hosting

- Hosted mode does not run benchmarks.
- The deployment uses free-tier services; two historical demo configurations were run through the paid OpenRouter API.
- Only selected approved benchmark summary values are publicly served; private prompts, responses, test content and paths are not.
