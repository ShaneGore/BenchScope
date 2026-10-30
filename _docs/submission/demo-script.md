# Demo Script

Target length: 5 to 7 minutes. Use only features available in the deployed demo.

## 1. Problem (30 seconds)

- Explain that local LLM benchmark results are often one-off and hard to compare.
- BenchScope persists and compares those results without exposing the private benchmark.

## 2. Product overview (30 seconds)

- Open the hosted frontend.
- Explain local/private mode versus hosted multi-user mode.
- Mention privacy: no prompts, answers, hidden tests, or generated code are stored.

## 3. Dashboard and history (60 seconds)

- Show the dashboard.
- Open Runs.
- Filter and inspect a run.
- Show missing metrics as null rather than zero.

## 4. Run detail and comparison (90 seconds)

- Open a run detail page.
- Show benchmark identity, release, manifest hash, expected task IDs, and task results.
- Compare two compatible runs.
- Explain that incompatible manifests/releases are not compared.

## 5. Import flow (60 seconds)

- Show the Import page.
- Explain v1 and v2 contract validation.
- Show duplicate detection and validation errors.
- Explain that raw uploaded payload is discarded.

## 6. Authentication and isolation (60 seconds)

- Sign in with Clerk.
- Show that profiles and runs are owner-scoped.
- Explain backend-enforced ownership.

## 7. Observability (60 seconds)

- Show Grafana dashboard.
- Show metrics, traces, and structured logs sharing a trace ID.
- Show alert rules and alert lifecycle.

## 8. Supervised recovery (60 seconds)

- Explain authenticated alert intake.
- Explain read-only AI investigation.
- Explain explicit operator approval and allowlisted recovery.
- Show audit records.

## 9. CI/CD and deployment (45 seconds)

- Show GitHub Actions workflows.
- Show required checks and branch protection.
- Explain rollback documentation.

## 10. Local/private benchmark architecture (45 seconds)

- Explain that hosted mode never runs benchmarks.
- Show the local Windows subprocess safety design:
  - suspended process launch
  - Job Object assignment
  - bounded output capture
  - bounded result-file reads
  - cancellation and timeout
- State clearly that real-runner integration remains tracked by Issue #25.

## 11. Limitations and future work (30 seconds)

- Real benchmark adapter not yet connected to the private runner.
- Observability demonstrated locally in Docker Compose.
- Quality score remains null until authoritative.
- No paid services are used.

## Recording note

No demo video has been recorded yet. This script is the shot list for the owner to record.
PY