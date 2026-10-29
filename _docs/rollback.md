# Rollback and recovery

## Frontend rollback
- GitHub Pages keeps previous deployments available through the Pages environment history.
- To roll back, rerun the previous successful `Deploy GitHub Pages`/`deploy-frontend.yml` workflow run or deploy the last known-good commit.
- Frontend rollback does not affect backend data or database state.

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
