# Local AI Benchmark Observatory — Product Plan

## 1. Product objective

Build a local-first web application that helps developers record, compare, and understand the performance of local language models on an existing independent coding benchmark.

The application should turn benchmark runs into a useful, persistent history rather than isolated results. A user should be able to import an existing result or launch a benchmark against a configured, already-running local model endpoint, then review the outcome and compare it with earlier runs.

The product must make failures visible and recoverable. Failed or interrupted attempts remain in the history, but they must never be presented as successful benchmark results or distort successful-run comparisons.

The existing benchmark is a private dependency. Its implementation and confidential evaluation material must not be included in the public application repository or exposed through the dashboard.

## 2. Target user

The target users are developers and data scientists who run different local language models and want to compare their coding performance, speed, and hardware requirements.

A user may run models with different versions, quantisations, inference settings, or hardware configurations. They want to understand which model/configuration works best for their needs and how performance changes over time.

The application has two operating contexts:

- **Local/private use:** one developer can run the full workflow, including launching the private benchmark against a model endpoint available on that machine.
- **Hosted use:** multiple individual users can sign in, import supported benchmark results, maintain their own result history, and compare their own runs without seeing another user's private data. The hosted service cannot launch benchmarks against endpoints running on each user's own computer; hosted benchmark execution is outside the MVP.

The MVP does not include teams, shared private workspaces, public submissions, or a public leaderboard.

## 3. Problem being solved

Benchmark results can be scattered across exported files, terminal output, and informal notes. This makes it difficult to:

- Compare models and configurations consistently.
- Keep a reliable historical record of results and failures.
- Understand differences in quality, latency, throughput, and resource requirements.
- Identify why a run failed and confirm whether a later attempt recovered.

The Observatory provides one place to import or launch runs, retain their results, compare completed runs, and investigate failed attempts.

## 4. Core user workflows

### Workflow A — Import an existing result

1. The user selects a benchmark result file in the supported JSON format.
2. The application validates the file and explains any validation errors clearly.
3. Valid data is normalised and saved as a benchmark run.
4. The application confirms the import and displays the metrics that are available.
5. The user can find the run in history and compare it with other completed runs.

An invalid import must not create a partial run or change existing records. Re-importing the same result should not silently create a duplicate when a stable source identifier or file fingerprint is available.

### Workflow B — Launch a benchmark

1. The user selects a configured model profile and benchmark configuration.
2. The user starts a benchmark run.
3. The application creates a unique run record and shows that it is running.
4. The benchmark runs through a controlled integration with the existing private benchmark and the selected, already-running local model endpoint.
5. The application records the outcome and available metrics, and marks the attempt completed or failed.
6. The user can see the result or a useful, sanitised diagnostic message in the run history.

Starting a run must not make the web interface unusable while the benchmark is running. The MVP only needs to execute one benchmark at a time. The application does not download models or start and stop model servers.

### Workflow C — Investigate and recover from a failure

1. A run fails, for example because the configured model endpoint is unavailable or the benchmark process exits unsuccessfully.
2. The application records the failed attempt, its timestamps, available diagnostics, and relevant execution metadata.
3. Previously completed results remain available and unchanged.
4. The user corrects the underlying problem and starts a new attempt or imports a corrected result.
5. The new attempt is recorded separately and the user can compare its outcome with the failed attempt.

The application must distinguish running, completed, failed, and interrupted attempts. A failed attempt must not be presented as a successful result.

### Workflow D — Compare results

1. The user opens historical results.
2. The user filters runs by model, status, or date.
3. The user compares completed runs using the metrics available for those runs.
4. The application clearly distinguishes missing metrics from values of zero and does not imply statistical significance unsupported by the benchmark.

### Workflow E — Use a personal hosted workspace

1. A user signs in through the supported authentication mechanism. An unauthenticated visitor can still explore a read-only demo populated with synthetic results.
2. A signed-in user can import supported benchmark result JSON and maintain a private history of their own imports.
3. The user can view, filter, compare, and delete their own records.
4. The backend verifies ownership for every personal record operation; changing a record identifier must never expose another user's data.
5. The hosted workspace does not launch a benchmark against the user's local model endpoint. The user can run benchmarks in the local/private mode and import the resulting metrics into the hosted workspace.

## 5. MVP functionality

### 5.1 Dashboard and run history

The dashboard should show:

- Counts of completed and failed runs.
- The most recent run and its status.
- The model and configuration used for each run.
- Available benchmark quality scores.
- Time to first token (TTFT), when available.
- Prompt and output token counts, when available.
- Prompt-processing and generation throughput, when available.
- Total run duration.

The history should be filterable by model, status, and date. At least one chart should allow a useful comparison between completed runs. Missing data must be shown as unavailable rather than zero.

### 5.2 Model profiles

The user can maintain a small set of named profiles within their own workspace. In hosted mode, profiles are metadata for organising imported results; local endpoint addresses and credentials are not needed and must not be used to connect the hosted service to a user's computer. In local/private mode, profiles may reference a configured local endpoint. A profile may describe:

- Model name and version.
- Quantisation, if known.
- Local inference endpoint.
- Hardware and inference-configuration notes.
- Optional settings supported by the benchmark integration.

Profiles refer to existing endpoints. The application does not download models or manage inference-server lifecycles.

### 5.3 Benchmark execution

The application can launch the existing benchmark using a selected, configured profile and a controlled integration. The integration must not accept arbitrary commands from a browser request.

For each attempt, record the run identifier, selected profile/configuration, start and end times, final status, process outcome where applicable, available metrics, and a sanitised diagnostic when it fails. A run left active by an application restart must be marked interrupted or otherwise clearly identified as incomplete.

The benchmark itself is not to be recreated or substantially refactored as part of the MVP. The exact integration mechanism remains a technical decision to be made after checking the private benchmark's available interface.

### 5.4 Result import and normalisation

Support one documented JSON result format for the MVP. Validate required fields and types, normalise supported metrics, report actionable errors, and avoid duplicates when a stable run identifier or file fingerprint is available.

Use a versioned canonical result format, initially version 1. Only metrics actually provided or measured should be stored; unsupported metrics remain unavailable.

### 5.5 Historical comparison

Provide a history table and at least one meaningful chart for comparing successful runs across models, configurations, or time. Failed attempts remain inspectable but are excluded from successful-performance summaries unless the view explicitly concerns failure rates or reliability.

## 6. Information the application records

Each benchmark attempt should retain, where available:

- Owner/user ID for records in the hosted multi-user workspace; local/private mode may use a single local workspace.
- Unique run ID and optional source run ID.
- Status and source (imported or launched by the application).
- Model name, version, quantisation, and selected configuration.
- Benchmark version or a non-confidential identifier.
- Start and completion timestamps and total elapsed time.
- Quality score or aggregate pass rate as defined by the benchmark.
- TTFT, prompt token count, generated token count, prompt-processing throughput, and generation throughput.
- Hardware and operating-system snapshot, including CPU, GPU, RAM, and VRAM where available.
- A sanitised error category and diagnostic message for a failed attempt.
- Import fingerprint/source identifier and optional relationship to an earlier attempt.
- Optional reference to a private local artefact, which must never be served publicly by the dashboard.

Store enough of the selected model, hardware, and configuration information with each run to preserve its historical meaning if a profile later changes. TTFT must be measured by the runner or streaming client when possible; it must not be inferred from prompt-processing duration.

## 7. Privacy, safety, and operating modes

### Local/private mode

The complete workflow is available locally. The service binds to the loopback interface by default. Local model endpoints, private benchmark paths, and private artifacts remain local and are not exposed to external users.

### Hosted multi-user mode

A hosted deployment supports individual user accounts and private workspaces. An unauthenticated visitor can explore a read-only demo populated with synthetic results. Signed-in users can import supported JSON results and manage their own profiles and result history. Personal records must remain isolated by owner, enforced on the backend for every read and write. Users must not be able to view, edit, or delete another user's records by guessing or changing identifiers.

The hosted service must not connect to model endpoints on a user's local computer or run the private benchmark. Benchmark execution against a developer's locally running model remains available in local/private mode; results can then be imported into the hosted workspace. Hosted import processing must extract only allowlisted, non-confidential metrics and metadata, discard the uploaded raw payload after processing, and never store prompts, reference answers, generated code, secrets, or private raw artifacts.

Use one maintained authentication approach appropriate for the chosen stack; do not invent a custom password/authentication scheme. Include sign-in, sign-out, session protection, and a documented way to configure the authentication provider. The exact provider and implementation will be chosen during stack selection. Full role-based access control, team workspaces, cross-user sharing, and multiple authentication providers are not required.

### Requirements for both modes

- Keep the proprietary benchmark implementation, prompts, reference answers, hidden test identifiers, generated code, confidential evaluation logic, and private raw artifacts out of the public repository and public dashboard.
- Keep local benchmark paths and private configuration outside version control.
- Commit only synthetic or sanitised example results.
- Do not log prompts, generated code, secrets, credentials, or complete private benchmark output.
- Accept only validated profile identifiers and supported input formats.
- Never execute uploaded files or arbitrary commands supplied by a browser request.
- Limit upload size and validate all data before persisting it.
- Enforce ownership checks server-side on every personal profile and run operation; client-side hiding is not an access-control mechanism.
- Keep authentication/session secrets out of source control and logs. Test that one user cannot read, modify, or delete another user's records.
- Do not add team workspaces, cross-user sharing, public result submissions, or hosted execution of private benchmarks to the MVP.

## 8. Additional requirements

The project must be maintainable, verifiable, safely deployable, and operable after release. These requirements describe outcomes, not a prescribed technology stack.

- The application can be started locally using documented, repeatable instructions.
- The application and its dependencies can be run in containers.
- Automated tests cover important application behaviour and can run in CI without a GPU, model weights, or access to the private benchmark.
- A publicly reachable hosted demonstration is available without exposing confidential data. Anonymous visitors can explore a read-only synthetic dataset; signed-in users can privately import and compare their own supported benchmark results.
- CI/CD runs tests and relevant quality checks, deploys a successful build to a development environment, supports a deliberate promotion to production, and documents how to roll back.
- A key user journey emits correlated metrics, structured logs, and traces that can be explored in a dashboard.
- At least one actionable alert detects a meaningful application or user-facing failure.
- An incident responder can receive an alert, gather relevant evidence, investigate a genuine development-environment failure, propose or apply a bounded fix, run relevant tests, and record the outcome.
- The project includes a written specification, a public task tracker with tasks and acceptance criteria, durable project instructions, and documentation of the agent roles and development process.

The specific frameworks, database, deployment provider, observability tools, runner implementation, and agent framework will be selected after reviewing options against this plan.

## 9. Success criteria

The MVP is successful when the following outcomes can be demonstrated:

1. The application starts using documented instructions.
2. Valid historical result files can be imported and remain available after an application restart.
3. Malformed or invalid imports produce clear errors and do not create partial records.
4. Duplicate imports are identified when a stable source ID or fingerprint is available.
5. A user can select a configured model profile and launch the existing benchmark without blocking the interface.
6. A completed run displays the available metrics and appears in history.
7. Missing metrics remain visibly unavailable rather than being treated as zero.
8. A failed or interrupted run is recorded with useful, sanitised diagnostics.
9. A new attempt can follow a failed attempt without overwriting the earlier record.
10. The history can be filtered and completed runs can be compared using a meaningful chart.
11. Automated tests cover import validation, persistence, metric normalisation, run success/failure, timeout/interruption, retries, and the principal user workflows.
12. CI runs the relevant tests and quality checks without access to the private benchmark or local GPU.
13. The project is containerised and has a repeatable development and deployment workflow, including rollback documentation.
14. A reviewer can access a hosted demonstration using only synthetic or sanitised data.
15. The repository documents the specification, architecture, setup, tests, task tracker, agent workflow, and incident-response demonstration.
16. An observable development incident triggers an alert, is investigated by the incident responder, and is resolved through a verified, bounded fix.
17. Users can sign in and out, and hosted users can manage their own profiles and imported results.
18. Authorization tests prove that a user cannot read, alter, or delete another user's records, even by changing record IDs in requests.
19. An anonymous visitor can use the read-only synthetic demo without creating an account.
20. No proprietary benchmark code, confidential evaluation material, credentials, or private artifacts are committed or publicly served.

## 10. Non-goals for the MVP

Do not implement:

- Team workspaces, organisation accounts, shared private results, roles/permissions beyond individual ownership, or a public leaderboard.
- Public benchmark-result submissions or hosted execution of the private benchmark.
- Public remote benchmark execution.
- A mechanism that claims to prevent users of a client-side benchmark from accessing its tests.
- Model downloads or model-server lifecycle management.
- Multiple inference-framework integrations or cloud-provider integrations.
- Subscription usage tracking or guarantees of cloud-cost savings.
- A new benchmark algorithm.
- Distributed job queues, Kubernetes, or complex orchestration without a demonstrated need.
- Advanced analytics or claims of statistical significance not supported by the benchmark.

## 11. Assumptions and questions to resolve before implementation

These are product or feasibility questions, not decisions to make by guessing during implementation:

1. **Benchmark interface:** What supported command, API, or adapter interface can launch the private benchmark and produce machine-readable results without copying confidential materials into the public repository?
2. **Result format:** What does a real exported result look like, and which fields are stable and safe to import? Create a sanitised sample fixture after confirming this.
3. **Model endpoint:** What endpoint protocol does the benchmark expect, and what information is needed to configure a profile?
4. **Metric definitions:** How does the benchmark define its quality score, pass rate, TTFT, and throughput? Which metrics can it reliably supply or measure?
5. **Authentication approach:** Which maintained authentication option best fits the selected stack while keeping signup/sign-in simple and secure? Prefer one provider or a well-supported built-in mechanism over custom authentication logic.
6. **Hosted/local boundary:** The hosted service supports account-scoped imports and comparisons, but cannot access a user's localhost model endpoint. Benchmark execution therefore remains local/private for the MVP. A local runner connected securely to a hosted account is a possible future extension, not a current requirement.
7. **Deployment constraints:** Which hosting option can run the application safely and affordably, retain user records appropriately, and support deployment, release promotion, and rollback?

The private benchmark integration is the principal feasibility risk. Validate its interface before committing to a detailed technical architecture.

## 12. Future extensions

Future work may add an open, non-confidential benchmark suite, shared results with explicit consent, team workspaces, verified versus self-reported results, a securely connected local runner for hosted users, more inference backends, repeated-run aggregation, and variability analysis. These features are explicitly not required for the MVP and must not delay its completion.
