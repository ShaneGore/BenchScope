# Exploring BenchScope

The [public demo](https://shanegore.github.io/BenchScope/) provides a read-only catalogue and comparison view without an account. The API may take about a minute to wake; use **Retry** if needed.

Open a configuration to inspect its available measurements and settings, or choose **Compare configurations** and select two or more runs. The comparison link preserves the selection when shared or refreshed. Values that were not measured are shown as unavailable. Reasoning, MTP, context and hosting differ across configurations, so the results should be interpreted with those settings in mind.

The public catalogue is an immutable fixture based on the owner's aggregate benchmark summaries. It does not expose the underlying private benchmark or raw trials. The separate [synthetic import example](../../frontend/public/examples/synthetic-run.json) is intended for local testing.

To try importing, filtering, and persistence, follow the [local setup](../../README.md#run-locally). Hosted personal records require sign-in. The public demo does not provide import or profile editing.

For technical details and recorded verification:

- [Architecture and boundaries](../architecture/boundaries.md) and the [API contract](../../openapi.yaml).
- [Local test and verification commands](../../README.md#verify) and [dated verification results](./submission-checklist.md#dated-verification-log).
- [Development workflow](../process.md), [agent roles](../team/), and [public issues](https://github.com/ShaneGore/BenchScope/issues).
- [CI and deployment](../../README.md#cicd-and-environments), including [production promotion and rollback evidence](../architecture/production-release.md#rollback-and-restoration-evidence-executed).
- [Local telemetry correlation](../observability/metric-trace-link.md) and [incident recovery exercise](../incidents/phase3c-recovery-demo.md). Model-generated draft PRs [#63](https://github.com/ShaneGore/BenchScope/pull/63) and [#64](https://github.com/ShaneGore/BenchScope/pull/64) were supervised; the independently verified recovery replayed a previously generated patch in a separate disposable incident.
- [Security review](./security-review.md) and [operational boundaries](./known-limitations.md).

The production demo is API-focused; the public Pages frontend uses staging. Observability and incident exercises are local. Historical records describe their tested revision and environment.
