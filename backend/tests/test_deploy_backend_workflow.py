from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-backend.yml"


def test_deploy_backend_workflow_uses_generated_smoke_credentials():
    content = WORKFLOW.read_text(encoding="utf-8")

    assert "SMOKE_TEST_TOKEN: ${{ secrets.SMOKE_TEST_TOKEN }}" not in content
    assert (
        "SMOKE_OTHER_TEST_TOKEN: ${{ secrets.SMOKE_OTHER_TEST_TOKEN }}" not in content
    )
    assert "CLERK_SECRET_KEY: ${{ secrets.CLERK_SECRET_KEY }}" in content
    assert "SMOKE_TEST_USER_A_ID: ${{ vars.SMOKE_TEST_USER_A_ID }}" in content
    assert "SMOKE_TEST_USER_B_ID: ${{ vars.SMOKE_TEST_USER_B_ID }}" in content
    assert "generate_smoke_tokens.py --write-github-env" in content
    assert "CLERK_SECRET_KEY" in content
    assert "SMOKE_TEST_USER_A_ID" in content
    assert "SMOKE_TEST_USER_B_ID" in content
