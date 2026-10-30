# Known Limitations

## Implemented and verified

- Frontend and backend tests pass in CI.
- Docker backend image builds.
- Hosted frontend and backend are deployed.
- Observability and supervised recovery are implemented and tested locally.
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

## Privacy and hosting

- Hosted mode does not run benchmarks.
- No paid services are used.
- No private benchmark content is committed or publicly served.
PY