- Tasks are tracked in `_docs/tasks.md`, one at a time
- Once tasks are ported to GitHub issues, GitHub issues becomes the single source of truth for the backlog
- Read the acceptance criteria before starting and before closing
- Commit regularly

Orchestrator

The main session is the orchestrator. It launches the PM, the engineer
and QA as subagents. It does not groom, implement or test itself.

Lifecycle

1. Pick the next ready, unassigned issue (or a batch of independent ones) from the backlog
2. PM grooms it
3. Engineer implements it
4. QA verifies it
5. On FAIL, back to step 3 with the QA comment as input
6. On PASS, close the issue
7. Repeat until the backlog is empty

Rules

- Do not skip step 2
- The engineer does not close the issue
- QA does not fix the code, only outputs PASS or FAIL
- The orchestrator closes the issue only after QA outputs PASS
- Claim an issue before starting (assignee + in-progress); one owner per issue
- Serial mode: pick one ready issue. Parallel mode: pick multiple independent ready issues and work each in its own branch/worktree
