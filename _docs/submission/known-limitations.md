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
- The receiver does not automatically invoke the investigator or the recovery action. The live Copilot provider remains blocked until tool restrictions and account entitlement are independently verified; accepting CLI flags is not proof. Recovery requires explicit approval and a successful restart now reports `verification_required` rather than resolving the incident without post-checks. An autonomous alert-to-fix run has not been demonstrated.

## Privacy and hosting

- Hosted mode does not run benchmarks.
- The deployment uses free-tier services; two historical demo configurations were run through the paid OpenRouter API.
- Only selected approved benchmark summary values are publicly served; private prompts, responses, test content and paths are not.
