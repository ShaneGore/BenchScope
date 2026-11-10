# Rollback and recovery

The demonstrated production rollback is an **application revision** rollback:
re-run the protected promotion workflow with a previously verified,
schema-compatible commit SHA. It is not a Render-dashboard rollback, a database
downgrade or a point-in-time restore.

## Frontend rollback (GitHub Pages)

GitHub Pages keeps previous deployments available through the Pages environment
history. To roll back, redeploy a known-good frontend commit using the
`Deploy GitHub Pages` / `deploy-frontend.yml` workflow:

1. Identify the last known-good full commit SHA from `main` history and the
   successful Pages deployment record.
2. Run the workflow manually with `ref` set to that full 40-character SHA. The
   workflow validates that the SHA is `main` or an ancestor of `main`; arbitrary
   or unmerged refs are rejected.
3. Confirm the workflow checks out, builds, and deploys that exact SHA.
4. Verify `https://shanegore.github.io/BenchScope/` returns HTTP 200 and the
   expected build.

To restore the current frontend after a rollback rehearsal, rerun the workflow
with `ref=main` or merge and deploy the intended commit. Frontend rollback does
not affect backend data or database state. Automatic `workflow_run` deployments
continue to use the exact SHA of the successful CI run and are not overridden by
a manual `ref`.

The public Pages frontend is staging-backed and was **not** promoted to
production. There is no production frontend rollback in this demonstration.

## Backend rollback (production demonstration API)

Backend releases use `.github/workflows/promote-production.yml`, never the
Render dashboard:

1. Record the current production `/version` and the deployment record.
2. Choose a previously verified revision whose Alembic head is compatible with
   the live schema. Forward-only migrations mean the current schema must still
   satisfy the older application.
3. Run the workflow with the rollback SHA and approve the protected
   `production` environment:

   ```powershell
   gh workflow run promote-production.yml --ref main -f confirm=promote -f ref=<40-char-sha>
   ```

4. Verify `/version` returns the rollback SHA, `/ready` succeeds, the full
   `scripts/smoke_test.py --mode full` passes (13/13 checks), and previously
   imported synthetic runs still exist.
5. Restore the approved revision through the same workflow and verify again.

Render Free retains only a small number of recent deploys, so a SHA-pinned
deploy hook is the reliable mechanism. Do not rely on the provider dashboard as
the primary rollback path.

### Executed rehearsal (2026-11-10)

| Step | Revision | Workflow run | Result |
|---|---|---|---|
| Rollback | `ab6ea5dc10d18059071f06696478edc0b1c46284` | [`42727553382`](https://github.com/ShaneGore/BenchScope/actions/runs/42727553382) | Success, 13/13 smoke |
| Restore | `dd8064ac6e3ebf505acb23fa01f5da051e07747f` | [`42728234322`](https://github.com/ShaneGore/BenchScope/actions/runs/42728234322) | Success, 13/13 smoke |

Both runs required environment approval, kept the schema at
`0008_incident_repair_jobs`, retained the same four synthetic run UUIDs, and
left staging unchanged. Evidence record:
<https://github.com/ShaneGore/BenchScope/issues/70#issuecomment-6755310213>.

`c47adc16aa3f4135a2cc1da81ff4cab16b6753b6` was the **originally proposed**
rollback candidate and is historical only; the revision actually demonstrated
was `ab6ea5d`.

### What the rehearsal does not prove

- No database rollback, restore or downgrade was performed.
- Neon Free's six-hour history and single manual snapshot are not backups.
- Only schema-compatible revisions are safe rollback targets.
- The production environment reviewer is the repository owner, so approval is a
  self-approval gate rather than independent review.

## Database migration compatibility

- Migrations must be backward compatible during deployment and rollback.
- Prefer additive migrations: add nullable columns/tables/indexes before
  removing old structures.
- Do not drop columns or tables in the same release that stops using them.
- A rollback to an older application version must still work with the newer
  schema.
- If a migration fails, the workflow stops before triggering backend deployment.
  Investigate and fix forward; do not manually mark the database as migrated.

## Failed deploy recovery

1. Check CI and workflow logs for the failing job.
2. If migration failed, do not trigger backend deployment. Fix the migration and
   rerun.
3. If backend deployment failed after the deploy hook, redeploy the previous
   verified SHA through the promotion workflow.
4. If smoke tests failed, roll back frontend/backend as needed and preserve the
   database.
5. Record the incident, root cause and recovery steps in `_docs/incidents/`.

## GitHub environment protection

The workflows reference `staging`, `github-pages` and `production` GitHub
Environments. The `production` environment is configured with a custom branch
policy limited to `main`, the repository owner as required reviewer,
`prevent_self_review=false` and `can_admins_bypass=false`. The `staging` and
`github-pages` environments are branch-restricted but have no required
reviewers, which is why staging deploys automatically after successful `main`
CI. The workflow files alone cannot enforce reviewer approval; the environment
settings do.
