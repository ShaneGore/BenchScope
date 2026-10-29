from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-frontend.yml"


def test_deploy_frontend_manual_main_uses_requested_ref():
    content = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in content
    assert 'requested_ref="${INPUT_REF:-main}"' in content
    assert 'selected_ref="main"' in content
    assert 'selected_ref="$requested_ref"' in content
    assert 'selected_ref="$GITHUB_SHA"' not in content


def test_deploy_frontend_valid_prior_main_commit_is_checked_against_main():
    content = WORKFLOW.read_text(encoding="utf-8")

    assert "^[0-9a-f]{40}$" in content
    assert (
        'gh api "repos/${GITHUB_REPOSITORY}/compare/${requested_ref}...main"' in content
    )
    assert "ahead|identical" in content
    assert "Requested commit is not an ancestor of main" in content


def test_deploy_frontend_rejects_invalid_or_unapproved_refs():
    content = WORKFLOW.read_text(encoding="utf-8")

    assert "Requested ref must be 'main' or a full 40-character commit SHA." in content
    assert "Requested commit is not available in ${GITHUB_REPOSITORY}." in content
    assert "Unsupported deployment event" in content


def test_deploy_frontend_automatic_uses_exact_ci_sha():
    content = WORKFLOW.read_text(encoding="utf-8")

    assert 'selected_ref="$WORKFLOW_SHA"' in content
    assert "github.event.workflow_run.head_sha" in content


def test_deploy_frontend_build_and_deployment_failures_are_reported():
    content = WORKFLOW.read_text(encoding="utf-8")

    assert "pnpm build" in content
    assert "node scripts/check-static-build.mjs dist" in content
    assert "actions/deploy-pages@v4" in content
    assert ">/dev/null" not in content
