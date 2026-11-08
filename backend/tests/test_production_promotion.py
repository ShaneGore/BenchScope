"""Exercise the actual production workflow guards without deploying anything."""

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (ROOT / ".github" / "workflows" / "promote-production.yml").read_text()
REQUIRED = (
    "PRODUCTION_DATABASE_URL",
    "PRODUCTION_RENDER_DEPLOY_HOOK_URL",
    "PRODUCTION_SMOKE_API_URL",
    "PRODUCTION_SMOKE_TEST_TOKEN",
    "PRODUCTION_SMOKE_FRONTEND_URL",
)


def script(name):
    section = re.search(
        rf"      - name: {re.escape(name)}\n([\s\S]*?)(?=\n      - |\Z)",
        WORKFLOW,
    )
    assert section
    match = re.search(
        r"        run: \|\n((?:          [^\n]*\n|\n)+)", section.group(1)
    )
    if match:
        return "\n".join(line[10:] for line in match.group(1).splitlines())
    match = re.search(r"        run: ([^\n]+)", section.group(1))
    assert match
    return match.group(1)


def git(directory, *args):
    return subprocess.run(
        ["git", *args], cwd=directory, check=True, capture_output=True, text=True
    ).stdout.strip()


def bash(directory, command, **env):
    executable = shutil.which("bash")
    if os.name == "nt":
        git_executable = Path(shutil.which("git")).resolve()
        executable = str(git_executable.parent.parent / "bin" / "bash.exe")
    return subprocess.run(
        [executable, "-e", "-o", "pipefail", "-c", command],
        cwd=directory,
        env={**os.environ, **env},
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def repository():
    with tempfile.TemporaryDirectory(dir=ROOT) as folder:
        repo = Path(folder)
        git(repo, "init", "-q")
        git(repo, "config", "user.email", "test@example.invalid")
        git(repo, "config", "user.name", "Test")
        (repo / "scripts").mkdir()
        shutil.copytree(
            ROOT / "backend" / "app",
            repo / "backend" / "app",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        for path in ("pyproject.toml", "uv.lock"):
            shutil.copyfile(ROOT / "backend" / path, repo / "backend" / path)
        for path in ("scripts/wait_for_deployment.py", "backend/app/main.py"):
            (repo / path).write_bytes(
                subprocess.run(
                    ["git", "show", f"HEAD:{path}"],
                    cwd=ROOT,
                    check=True,
                    capture_output=True,
                ).stdout
            )
        git(repo, "add", ".")
        git(repo, "commit", "-qm", "compatible")
        sha = git(repo, "rev-parse", "HEAD")
        git(repo, "branch", "-M", "main")
        git(repo, "update-ref", "refs/remotes/origin/main", sha)
        git(repo, "tag", "v1.2.3")
        yield repo, sha


def ci_check(repo, sha, response, exit_code=0):
    mock = """
    gh() {
      printf '%s\\n' "$*" > "$CI_CALL_LOG"
      if [ "$MOCK_CI_EXIT" != 0 ]; then
        echo "$GH_TOKEN" >&2
        return "$MOCK_CI_EXIT"
      fi
      printf '%s' "$MOCK_CI_RESPONSE"
    }
    """
    return bash(
        repo,
        mock + script("Require successful main CI"),
        SELECTED_SHA=sha,
        GITHUB_REPOSITORY="owner/repo",
        GH_TOKEN="test-secret-token",
        CI_CALL_LOG=str(repo / "ci-call"),
        MOCK_CI_RESPONSE=response,
        MOCK_CI_EXIT=str(exit_code),
    )


def ci_response(sha, **overrides):
    run = {
        "id": 123,
        "head_sha": sha,
        "head_branch": "main",
        "event": "push",
        "path": ".github/workflows/ci.yml",
        "repository": {"full_name": "owner/repo"},
        "head_repository": {"full_name": "owner/repo"},
        "status": "completed",
        "conclusion": "success",
    }
    run.update(overrides)
    return json.dumps({"total_count": 1, "workflow_runs": [run]})


def promotion(repo, ref, config, ci=None, ci_exit=0):
    output = repo / "output"
    output.write_text("")
    env = {"GITHUB_OUTPUT": str(output), "INPUT_REF": ref, **config}
    for step in ("Determine promotion ref", "Check production configuration"):
        result = bash(repo, script(step), **env)
        if result.returncode:
            return result, []
    selected = output.read_text().split("selected_ref=")[1].splitlines()[0]
    checkout = subprocess.run(
        ["git", "checkout", "--detach", selected],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    if checkout.returncode:
        return checkout, []
    result = bash(repo, script("Resolve exact deployment revision"), **env)
    if result.returncode:
        return result, []
    sha = output.read_text().split("sha=")[1].splitlines()[0]
    result = ci_check(repo, sha, ci if ci is not None else ci_response(sha), ci_exit)
    if result.returncode:
        return result, []
    result = bash(
        repo / "backend",
        script("Check deployment identity compatibility"),
        **{**env, "UV_PROJECT_ENVIRONMENT": str(ROOT / "backend" / ".venv")},
    )
    if result.returncode:
        return result, []
    log = repo / "calls"
    mock_commands = """
    uv() { printf 'uv|%s\\n' "$*" >> "$ACTION_LOG"; }
    python() { printf 'python|%s|%s|%s\\n' "$*" "$SELECTED_REF" "$EXPECTED_REVISION" >> "$ACTION_LOG"; }
    """
    for step, revision_name, directory in (
        ("Run production database migrations", None, repo / "backend"),
        ("Trigger production backend deployment", "SELECTED_REF", repo),
        ("Wait for the intended backend revision", "EXPECTED_REVISION", repo),
    ):
        step_env = {
            **env,
            "ACTION_LOG": str(log),
            "SELECTED_REF": "",
            "EXPECTED_REVISION": "",
        }
        if revision_name:
            section = WORKFLOW.split(f"      - name: {step}\n", 1)[1].split(
                "\n      - ", 1
            )[0]
            assert f"{revision_name}: ${{{{ steps.revision.outputs.sha }}}}" in section
            step_env[revision_name] = sha
        result = bash(directory, mock_commands + script(step), **step_env)
        assert result.returncode == 0, result.stdout + result.stderr
        assert f"head_sha={sha}" in (repo / "ci-call").read_text()
    return result, log.read_text().splitlines()


CONFIG = {name: "fixture-secret-value" for name in REQUIRED}


@pytest.mark.parametrize("missing", REQUIRED)
def test_missing_configuration_fails_without_exposing_values(repository, missing):
    repo, _ = repository
    result, effects = promotion(repo, "main", {**CONFIG, missing: ""})
    assert result.returncode != 0
    assert missing in result.stdout
    assert "fixture-secret-value" not in result.stdout + result.stderr
    assert not effects


@pytest.mark.parametrize(
    "ref", ["main", "refs/heads/main", "v1.2.3", "refs/tags/v1.2.3", "sha"]
)
def test_valid_refs_use_one_sha(repository, ref):
    repo, sha = repository
    result, effects = promotion(repo, sha if ref == "sha" else ref, CONFIG)
    assert result.returncode == 0, result.stdout + result.stderr
    assert effects == [
        "uv|run alembic upgrade head",
        f"python|scripts/render_deploy_hook.py|{sha}|",
        f"python|scripts/wait_for_deployment.py||{sha}",
    ]


@pytest.mark.parametrize("ref", ["feature", "main\nbad", "v1;echo bad", "v9", "0" * 40])
def test_invalid_or_nonexistent_refs_fail_before_side_effects(repository, ref):
    repo, _ = repository
    result, effects = promotion(repo, ref, CONFIG)
    assert result.returncode != 0
    assert not effects


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "pending",
        "failure",
        "cancelled",
        "wrong_sha",
        "wrong_branch",
        "pull_request",
        "wrong_workflow",
        "fork",
        "api_error",
        "invalid_json",
        "incomplete_page",
        "newer_failure",
    ],
)
def test_untrusted_or_unsuccessful_ci_fails_before_side_effects(repository, case):
    repo, sha = repository
    overrides = {
        "pending": {"status": "in_progress", "conclusion": None},
        "failure": {"conclusion": "failure"},
        "cancelled": {"conclusion": "cancelled"},
        "wrong_sha": {"head_sha": "f" * 40},
        "wrong_branch": {"head_branch": "feature"},
        "pull_request": {"event": "pull_request"},
        "wrong_workflow": {"path": ".github/workflows/other.yml"},
        "fork": {"head_repository": {"full_name": "other/repo"}},
    }
    response = ci_response(sha, **overrides.get(case, {}))
    if case == "missing":
        response = json.dumps({"total_count": 0, "workflow_runs": []})
    elif case == "invalid_json":
        response = "not json"
    elif case == "incomplete_page":
        response = json.dumps({**json.loads(response), "total_count": 101})
    elif case == "newer_failure":
        good = json.loads(response)["workflow_runs"][0]
        response = json.dumps(
            {
                "total_count": 2,
                "workflow_runs": [good, {**good, "id": 124, "conclusion": "failure"}],
            }
        )
    result, effects = promotion(repo, sha, CONFIG, response, int(case == "api_error"))
    assert result.returncode != 0
    assert not effects
    assert "test-secret-token" not in result.stdout + result.stderr
    assert f"head_sha={sha}" in (repo / "ci-call").read_text()


def test_outside_main_and_incompatible_revisions_fail(repository):
    repo, sha = repository
    git(repo, "checkout", "-qb", "outside")
    verifier = repo / "scripts" / "wait_for_deployment.py"
    verifier.write_text('from pathlib import Path\nPath("executed").touch()\n')
    (repo / "extra").write_text("outside")
    git(repo, "add", "extra", "scripts/wait_for_deployment.py")
    git(repo, "commit", "-qm", "outside")
    outside = git(repo, "rev-parse", "HEAD")
    result, effects = promotion(repo, outside, CONFIG)
    assert result.returncode != 0
    assert not effects
    assert not (repo / "executed").exists()

    git(repo, "checkout", "-q", "main")
    (repo / "scripts" / "wait_for_deployment.py").unlink()
    git(repo, "add", "-u")
    git(repo, "commit", "-qm", "incompatible")
    incompatible = git(repo, "rev-parse", "HEAD")
    git(repo, "update-ref", "refs/remotes/origin/main", incompatible)
    result, effects = promotion(repo, incompatible, CONFIG)
    assert result.returncode != 0
    assert not effects
    assert sha != incompatible


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        ("scripts/wait_for_deployment.py", "# placeholder\n"),
        ("backend/app/main.py", '@app.get("/version")\n'),
        ("backend/app/main.py", "# no version endpoint\n"),
        (
            "scripts/wait_for_deployment.py",
            (
                "class DeploymentVerificationError(Exception): pass\n"
                "def wait_for_revision(*args, **kwargs): pass\n"
            ),
        ),
        (
            "scripts/wait_for_deployment.py",
            (
                "class DeploymentVerificationError(Exception): pass\n"
                "def wait_for_revision(url, expected, *, fetch, **kwargs):\n"
                "    fetch(url + '/version')\n"
                "    fetch(url + '/ready')\n"
            ),
        ),
    ],
)
def test_incomplete_identity_implementation_fails(repository, path, replacement):
    repo, _ = repository
    (repo / path).write_text(replacement)
    git(repo, "add", path)
    git(repo, "commit", "-qm", "incomplete identity")
    sha = git(repo, "rev-parse", "HEAD")
    git(repo, "update-ref", "refs/remotes/origin/main", sha)
    result, effects = promotion(repo, sha, CONFIG)
    assert result.returncode != 0
    assert not effects


def test_compatible_revisions_remain_promotable_after_identity_file_edits(repository):
    repo, original = repository
    for path in ("backend/app/main.py", "scripts/wait_for_deployment.py"):
        with (repo / path).open("a") as source:
            source.write("\n# harmless change\n")
        git(repo, "add", path)
        git(repo, "commit", "-qm", "compatible change")
    latest = git(repo, "rev-parse", "HEAD")
    git(repo, "update-ref", "refs/remotes/origin/main", latest)
    git(repo, "tag", "v2.0")
    for ref, expected in (("main", latest), ("v2.0", latest), (original, original)):
        result, calls = promotion(repo, ref, CONFIG)
        assert result.returncode == 0, result.stderr
        assert calls[-2:] == [
            f"python|scripts/render_deploy_hook.py|{expected}|",
            f"python|scripts/wait_for_deployment.py||{expected}",
        ]


def test_version_route_with_incorrect_runtime_behavior_fails(repository):
    repo, _ = repository
    main = repo / "backend" / "app" / "main.py"
    original = main.read_text()
    broken = original.replace(
        'return {"revision": revision}', 'return {"revision": "unknown"}'
    )
    assert broken != original
    main.write_text(broken)
    git(repo, "add", "backend/app/main.py")
    git(repo, "commit", "-qm", "broken version")
    sha = git(repo, "rev-parse", "HEAD")
    git(repo, "update-ref", "refs/remotes/origin/main", sha)
    result, effects = promotion(repo, sha, CONFIG)
    assert result.returncode != 0
    assert not effects


def test_removed_registered_version_route_fails_before_side_effects(repository):
    repo, _ = repository
    main = repo / "backend" / "app" / "main.py"
    source = main.read_text()
    broken = source.replace(
        "    return app\n",
        '    app.router.routes = [route for route in app.router.routes if getattr(route, "path", "") != "/version"]\n'
        "    return app\n",
    )
    assert broken != source
    main.write_text(broken)
    git(repo, "add", "backend/app/main.py")
    git(repo, "commit", "-qm", "remove version registration")
    sha = git(repo, "rev-parse", "HEAD")
    git(repo, "update-ref", "refs/remotes/origin/main", sha)
    result, effects = promotion(repo, sha, CONFIG)
    assert result.returncode != 0
    assert not effects


def test_workflow_gates_side_effects_and_wires_the_same_revision():
    names = [
        "Check production configuration",
        "actions/checkout@v4",
        "Resolve exact deployment revision",
        "Require successful main CI",
        "Install preflight dependencies",
        "Check deployment identity compatibility",
        "Run production database migrations",
        "Trigger production backend deployment",
        "Wait for the intended backend revision",
    ]
    assert [WORKFLOW.index(name) for name in names] == sorted(
        WORKFLOW.index(name) for name in names
    )
    assert "SELECTED_REF: ${{ steps.revision.outputs.sha }}" in WORKFLOW
    assert "EXPECTED_REVISION: ${{ steps.revision.outputs.sha }}" in WORKFLOW
    assert "SELECTED_SHA: ${{ steps.revision.outputs.sha }}" in WORKFLOW
    assert "actions: read" in WORKFLOW
    assert (
        "PRODUCTION_SMOKE_OTHER_TEST_TOKEN: ${{ secrets.PRODUCTION_SMOKE_OTHER_TEST_TOKEN }}"
        not in WORKFLOW
    )
    assert (
        "SMOKE_OTHER_TEST_TOKEN: ${{ secrets.PRODUCTION_SMOKE_OTHER_TEST_TOKEN }}"
        in WORKFLOW
    )
