# Rollback and recovery

## Frontend rollback
- GitHub Pages keeps previous deployments available through the Pages environment history.
- To roll back, redeploy a known-good frontend commit using the `Deploy GitHub Pages` / `deploy-frontend.yml` workflow:
  1. Identify the last known-good full commit SHA from `main` history and the successful Pages deployment record.
  2. Run the workflow manually with `ref` set to that full 40-character SHA. The workflow validates that the SHA is `main` or an ancestor of `main`; arbitrary or unmerged refs are rejected.
  3. Confirm the workflow checks out, builds, and deploys that exact SHA.
  4. Verify `https://shanegore.github.io/BenchScope/` returns HTTP 200 and the expected build.
- To restore the current frontend after a rollback rehearsal, rerun the workflow with `ref=main` or merge and deploy the intended commit.
- Frontend rollback does not affect backend data or database state.
- Automatic `workflow_run` deployments continue to use the exact SHA of the successful CI run and are not overridden by a manual `ref`.

## Backend rollback
- Backend deployment is triggered by a Render deploy hook after migrations succeed.
- Render keeps previous images/builds available for rollback in the provider dashboard.
- If a backend release fails readiness or smoke tests, roll back to the previous Render deployment.
- Do not run destructive database changes as part of rollback.

## Database migration compatibility
- Migrations must be backward compatible during deployment and rollback.
- Prefer additive migrations: add nullable columns/tables/indexes before removing old structures.
- Do not drop columns or tables in the same release that stops using them.
- A rollback to an older application version must still work with the newer schema.
- If a migration fails, the workflow stops before triggering backend deployment. Investigate and fix forward; do not manually mark the database as migrated.

## Failed deploy recovery
1. Check CI logs for the failing job.
2. If migration failed, do not trigger backend deployment. Fix the migration and rerun.
3. If backend deployment failed, roll back the backend to the previous image.
4. If smoke tests failed, roll back frontend/backend as needed and preserve the database.
5. Record the incident, root cause, and recovery steps in `_docs/incidents/`.

## GitHub environment protection

The workflows reference `staging` and `production` GitHub Environments. Required reviewers, wait timers, and branch restrictions must be configured in the repository settings before these gates are effective. The workflow files alone cannot enforce reviewer approval.
