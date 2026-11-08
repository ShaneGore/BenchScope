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

## Privacy and hosting

- Hosted mode does not run benchmarks.
- The deployment uses free-tier services; two historical demo configurations were run through the paid OpenRouter API.
- Only selected approved benchmark summary values are publicly served; private prompts, responses, test content and paths are not.
