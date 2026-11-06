# BenchScope showcase improvement plan

Date: 6 November 2026. PM status: READY for implementation. Implementation issue: [#56](https://github.com/ShaneGore/BenchScope/issues/56), claimed and in progress.

## Goal

Make BenchScope straightforward for employers and course reviewers to launch, test, and understand, and let anonymous visitors experience its central comparison workflow. Fix the independently reproduced setup defect and release-verification gaps while preserving existing local work and safely removing obsolete task checkouts.

## Baseline and delivery order

- Current published baseline: `f2902bf93a3ec1500330133eff56c184beb86135` (4 November 2026).
- Integration checkout: `C:/Users/Shane/.codex/worktrees/benchscope-showcase/BenchScope`; frontend work uses a separate worktree before integration.
- The original `BenchScope` checkout at `9b2163a` has pre-existing changes and remains intact. This work does not discard, commit, or silently copy those changes.
- Independent review reproduced empty `ALERT_RECEIVER_BEARER` blocking Compose parsing even for `db api`; the live demo showed 15 configurations and detail pages but no anonymous comparison.
- Current public CI/staging runs passed. Readiness alone cannot establish that a newly requested revision is serving rather than an older healthy release.
- Docker Engine was unavailable during review; source, historical evidence, fresh tests, and live observations must remain distinguishable.

| Order | Slice | Initial status |
| --- | --- | --- |
| A | Baseline and cleanup inventory | Baseline isolated; inventory pending |
| B | Reproducible startup and tests | READY |
| C | Public comparison | READY |
| D | README and synthetic example | READY after B/C interfaces settle |
| E | Deployment identity and refs | READY |
| F | Independent QA and cleanup completion | Pending implementation |

The earlier two-hour estimate prioritizes B/C/D, with A first and F throughout. E is the bounded release-reliability improvement identified in the same review. Estimates do not justify claiming unexecuted checks passed. GitHub issues remain the authoritative tracker; the orchestrator records the issue link and closes only after QA PASS.

## A. Preserve work and clean obsolete checkouts

### Goal

Use the current baseline without losing owner changes; remove only demonstrably redundant task-specific BenchScope folders under the directory named by the owner.

### Acceptance criteria

- [ ] A1. Implementation uses the isolated current-main checkout; original tracked/untracked changes remain intact.
- [ ] A2. Cleanup inventory records each candidate's absolute path, HEAD, branch, tracked/untracked status, ignored-data assessment, and whether commits are retained in the baseline or another preserved ref.
- [ ] A3. Before removal, the resolved target is verified to be a task-specific BenchScope sibling directly inside `C:/Users/Shane/Documents/Coding Projects/AI_devs_2026`; the main checkout and unrelated projects are excluded.
- [ ] A4. Dirty, locked, active, or uncertain checkouts are retained with a reason. Ignored configuration/private artifacts/user data are considered before removal; clean Git status alone is insufficient.
- [ ] A5. Safe obsolete worktrees are removed through their appropriate lifecycle, preserving branch refs and needed local data; the record names exactly what was removed or retained.
- [ ] A6. Remaining folders and Git worktree registrations are verified after cleanup.

### Out of scope

Unrelated projects, the original dirty checkout, branch-ref deletion, and cleanup outside the owner's named directory.

### Constraints

One shell end to end for filesystem operations; validate absolute paths before recursive deletion/moving. Do not force removal past unexplained changes.

## B. Predictable startup and a project verification command

### Goal

A reviewer can start frontend/API/PostgreSQL and run the relevant checks through documented root commands without local environment files changing test expectations.

### Acceptance criteria

- [ ] B1. From fresh documented local configuration, one supported root command starts frontend/API/PostgreSQL after prerequisite installation; API migrations precede readiness.
- [ ] B2. Optional monitoring/alerting secrets do not block core startup through global interpolation. Full-stack secret setup is explicit.
- [ ] B3. Setup never overwrites existing environment files, secrets, or user databases; generated local values remain ignored.
- [ ] B4. One documented root command runs backend unit/PostgreSQL integration tests, frontend tests/build, and relevant browser journeys using the existing toolchain.
- [ ] B5. Verification uses an explicitly disposable database, fails nonzero for failed checks/unavailable required prerequisites, cleans only resources it created, and never labels database-dependent skips full integration success.
- [ ] B6. Frontend tests are independent of a developer's local `VITE_API_URL`; ordinary local configuration does not cause URL assertion failures.
- [ ] B7. A fresh runtime check covers synthetic import, history/detail readback, and persistence after application restart. Any prerequisite preventing this remains recorded as unverified.

### Out of scope

Authentication-provider changes, dependencies, personal database migration, hosted benchmark execution, unrelated CI redesign.

### Constraints

Compose/environment examples, root scripts, relevant test configuration and existing coverage. Use `uv`/`pnpm`; keep published services local and leave existing listeners untouched.

## C. Anonymous read-only comparison

### Goal

A visitor can compare published demo configurations without signing in, using existing comparison components and immutable public summaries.

### Acceptance criteria

- [ ] C1. Public demo visibly offers comparison and lets anonymous visitors choose at least two completed demo runs.
- [ ] C2. Comparison displays available pass rate/throughput and configuration differences; absent values remain unavailable rather than zero.
- [ ] C3. Established benchmark identity/release/manifest compatibility rules apply where fields exist. Incompatible selections explain the problem; differing inference settings stay visible rather than implying a controlled ranking.
- [ ] C4. Only public demo records participate; anonymous import/profile modification/deletion/private access/benchmark execution remain unavailable.
- [ ] C5. Direct comparison links and refresh preserve demo routing and selection without authentication.
- [ ] C6. Focused service/routing tests and a browser journey verify anonymous comparison, visible values, missing metrics, and read-only boundaries.

### Out of scope

Public submissions, shared leaderboards, new benchmark results, scoring definitions, team workspaces, and private runner integration ([#25](https://github.com/ShaneGore/BenchScope/issues/25)).

### Constraints

Existing frontend stack, demo service/data, router, comparison page. Do not expose personal routes or add confidential benchmark fixtures.

## D. README and synthetic import example

### Goal

Explain the useful product, provide a working demonstration/setup path, and show engineering decisions without repeatedly foregrounding the same deferred feature.

### Acceptance criteria

- [ ] D1. README links live demo, architecture, public task evidence, exact startup/check commands, and a current screenshot or walkthrough.
- [ ] D2. One concise scope statement says independently produced results are imported/compared and private runner execution is not connected; detailed gaps are linked without repeated caveats.
- [ ] D3. At least three concrete source-supported decisions are explained, such as allowlisted imports, owner isolation, null/incomplete-result semantics, and request correlation. No invented human-review or verification claims.
- [ ] D4. A clearly synthetic JSON example is linked from README/import flow, validates and imports successfully, and contains no private prompts, output, credentials, paths, or artifacts.
- [ ] D5. Setup/test/demo/deployment claims match the implemented revision; long exercises remain linked runbooks.
- [ ] D6. Submission/operational evidence accurately retains the on-call gap; no autonomous recovery is claimed.

### Out of scope

Rewriting all historical documents or deleting earlier failure evidence. Private runner work remains [#25](https://github.com/ShaneGore/BenchScope/issues/25); autonomous responder completion is a separate follow-up owned by the orchestrator.

### Constraints

README, focused linked documentation, synthetic public sample and import-page link; distinguish synthetic examples from owner-supplied summaries.

## E. Release identity and manual refs

### Goal

Deployment checks establish the intended revision is serving, and manual release inputs select the requested revision.

### Acceptance criteria

- [ ] E1. Backend exposes non-secret build/revision metadata for comparing requested and running commits.
- [ ] E2. Deployment waits for the expected revision before smoke testing; an older healthy release cannot pass, and bounded timeout clearly reports failure/mismatch.
- [ ] E3. Relevant backend deployment/production-promotion workflows resolve/use manual `ref` consistently; invalid refs fail before deployment.
- [ ] E4. Focused tests/executable helper checks cover old-revision rejection, expected-revision success, timeout, and manual ref selection.
- [ ] E5. Existing automatic staging and manual production control remain; actual deployment verification is recorded separately from local checks.

### Out of scope

Production provisioning, automatic production releases, provider-plan changes, new cloud dependencies.

### Constraints

Existing helpers/workflows, public health/build metadata, Docker build metadata and focused tests. No credentials in public responses/logs.

## F. Independent QA and delivery record

### Goal

Assess the result against these criteria and report completed work alongside remaining verification gaps.

### Acceptance criteria

- [ ] F1. Engineer records files/checks/outcomes; independent QA checks every applicable criterion without fixing product code.
- [ ] F2. Failures return to engineering; only the orchestrator closes the issue after QA PASS.
- [ ] F3. Evidence distinguishes fresh runtime observations, tests, static inspection, historical evidence, and prerequisite-blocked checks.
- [ ] F4. Final handoff names implementation branch/revision, tests, publication status, original-checkout preservation, and removed/retained folders.

### Out of scope

Calling unavailable prerequisites, unchecked criteria, historical issue closure, or an old green deployment proof of current success.

### Constraints

No dependencies without owner approval. Preserve hosted restrictions, local-only benchmark execution, owner isolation, null metrics, and confidentiality.

## Progress record

- PM grooming: READY, 6 November 2026.
- Issue: [#56](https://github.com/ShaneGore/BenchScope/issues/56), claimed.
- Baseline: isolated at `f2902bf`; original dirty checkout preserved.
- Implementation/QA: pending.
- Cleanup: 23 merged task checkouts removed; three retained for local data/changes. See [cleanup inventory](worktree-cleanup-2026-11-06.md); independent QA pending.
- Publication: pending; local implementation alone is not live deployment evidence.

