# Engineering decisions

BenchScope is a results observatory: React renders typed records from FastAPI; SQLAlchemy and Alembic provide PostgreSQL persistence. Public summaries and authenticated personal records have separate service paths.

## Data quality before rankings

The UI preserves missing values instead of displaying zero. v2 imports identify the benchmark, release, canonical manifest SHA-256 and expected task IDs; task coverage controls whether pass rate is meaningful. Comparison suppresses task outcomes and pass rates when identities differ. This avoids treating two different evaluations as the same benchmark.

The demo API publishes aggregate summaries rather than task-level materials or manifests. Demo charts compare records from that curated public catalogue only. They describe observed values and configuration differences, not a reproducible controlled ranking; they do not invent benchmark identity metadata. Throughput definitions, hosted runs and provider errors are disclosed in the expandable methodology.

## Public exploration without public writes

Anonymous demo comparison resolves requested IDs against GET `/api/v1/demo/runs`. Forged IDs cannot call personal comparison or detail routes. Import, editing and deletion remain unavailable. A shareable hash URL carries the selection, so comparisons survive page refresh and static GitHub Pages hosting.

Personal record owners are derived from verified authentication in the backend rather than browser-supplied owner IDs. Import validation retains only allowlisted metadata and metrics. Prompts, hidden tests, generated code and raw responses remain outside the public repository and telemetry.

## Small operational boundaries

Core startup includes the frontend, API and PostgreSQL. Optional observability and its receiver credentials have a separate Compose overlay. This keeps operational tooling from blocking the first useful application journey.

The root verification command creates disposable test resources and distinct local ports rather than borrowing a developer's database or stopping existing services. Backend persistence tests and browser flows run against the same supported database engine used by the application.

## Evidence and review

Specifications and the public tracker show PM grooming, implementation and QA outcomes. For example, [issue #13](https://github.com/ShaneGore/BenchScope/issues/13) records real API integration and browser checks; [issue #35](https://github.com/ShaneGore/BenchScope/issues/35) records unsuccessful telemetry checks followed by a narrower verified trace-link solution. Test reports and review comments are evidence within their stated revision and environment, not a blanket certification of every deployment.

[Showcase task #56](https://github.com/ShaneGore/BenchScope/issues/56) and the [implementation plan](../plans/showcase-improvements.md) track this pass. The [submission limitations](../submission/known-limitations.md) preserve unresolved runner and incident-response boundaries separately from product onboarding.
