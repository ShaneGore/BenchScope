# Task checkout cleanup — 6 November 2026

Scope: direct task-specific BenchScope siblings inside `C:/Users/Shane/Documents/Coding Projects/AI_devs_2026` only. Original `BenchScope` and unrelated projects were preserved.

## Result

Removed 23 redundant task checkouts. Retained three task checkouts with local configuration, secrets, or uncommitted work. Every removed HEAD was an ancestor of baseline `f2902bf`; branch refs and shared repository history were retained.

Before each removal, the resolved absolute path was checked to be a direct child of the named directory and not a reparse point. Git status included all non-ignored untracked files and was clean; ancestry was checked again. Ignored paths were inspected and restricted to disposable virtual environments, node_modules, Python/test/lint caches and frontend build artifacts. A process inventory found no candidate checkout in use; Docker mount sources referenced none of these task folders.

Git worktree removal updated registrations. Where Windows left read-only remnants, native PowerShell Remove-Item used the same revalidated literal path. No branch deletion, container/volume cleanup, or unrelated directory removal occurred.

## Removed inventory

All paths below are relative to the exact scope above. Each had clean tracked/untracked status and no ignored user configuration/data; only the disposable caches described above were removed.

| Folder | HEAD | Preserved branch |
| --- | --- | --- |
| BenchScope-issue25-docs | 6e1f25d | docs/issue-25-v2-runner-findings |
| BenchScope-issue25-cancellation | 274b971 | feat/issue-25-cancellation-lifecycle |
| BenchScope-issue33-readonly-ai | 9d1a59b | feat/issue-33-readonly-luna |
| BenchScope-issue35-metric-trace | 1bc6e5e | feat/issue-35-metric-trace-link |
| BenchScope-local-startup | 0eb5342 | docs/local-mvp-startup |
| BenchScope-pr36 | 0b00133 | pr-36-review |
| BenchScope-task1 | c081a23 | task-1-project-skeleton |
| BenchScope-task7 | f5cac09 | task-7-fastapi-config |
| BenchScope-task9 | 9022976 | task-9-postgres-storage |
| BenchScope-task10 | a82c9aa | task-10-profiles-api |
| BenchScope-task11 | 331c266 | task-11-result-import |
| BenchScope-task12 | f0b496b | task-12-run-history |
| BenchScope-task13 | b526d82 | task-13-real-api |
| BenchScope-task14 | 0e4a33b | task-14-auth |
| BenchScope-task15 | e489328 | task-15-controlled-runner |
| BenchScope-task16 | 0275b25 | task-16-hosted-demo |
| BenchScope-task17 | 0179c75 | task-17-mode-gating |
| BenchScope-task18 | 557c621 | task-18-observability |
| BenchScope-task19 | c668ade | task-19-ci |
| BenchScope-task20 | e6c8ae5 | task-20-images-deploy |
| BenchScope-task22 | d080e58 | task-22-e2e |
| BenchScope-task23 | 228081d | task-23-incident |
| BenchScope-task24 | 122d3fb | task-24-release-audit |

## Retained inventory

| Folder | HEAD / branch | Reason |
| --- | --- | --- |
| BenchScope | 9b2163a / feat/issue-21-pages-workflow | Original checkout has pre-existing tracked and untracked work; left intact. |
| BenchScope-issue32-alert-intake | 0b00133 / feat/issue-32-alert-intake | Ignored local incident environment and secrets directory. |
| BenchScope-issue34 | d010969 / fix/dockerfile-port | Modified .gitignore; untracked neon.ts/package.json/package-lock.json; ignored local environment and Neon configuration. |
| BenchScope-task8 | 62a409a / task-8-local-compose | Ignored local .env configuration. |

Local secret/configuration contents were not published or copied. Worktrees outside the named cleanup directory were excluded. The two managed showcase worktrees were created for this implementation; the frontend integration worktree can be archived once its commits are integrated and QA completes.

## Verification

After removal, directory enumeration showed only the four retained BenchScope folders above in the named directory. Git worktree registrations likewise retained only those four within that directory. All 23 removed branches remain in the shared repository. Independent QA will verify the report, registrations and original-checkout preservation before final handoff.
