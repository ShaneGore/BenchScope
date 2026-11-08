import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app import incident_repair as repair
from app.incident_investigation import (
    CopilotUsage,
    InvestigationBlocked,
    InvestigationRejected,
)
from app.models import Base, IncidentAuditEvent, IncidentRecord, IncidentRepairJob


def _record(*, fingerprint="0123456789abcdef", revision="abcdef0", status="complete"):
    return IncidentRecord(
        id=uuid4(),
        alert_name="BenchScopeApiUnavailable",
        fingerprint=fingerprint,
        starts_at=datetime(2026, 11, 1, tzinfo=UTC),
        ends_at=datetime(2026, 11, 1, tzinfo=UTC),
        alert_status="firing",
        evidence_status=status,
        evidence={},
        application_revision=revision,
        received_at=datetime(2026, 11, 1, tzinfo=UTC),
    )


def _engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'repair.sqlite'}")
    Base.metadata.create_all(engine)
    return engine


@pytest.mark.parametrize(
    "modified",
    [
        "def test_added(): assert True\n",
        "def test_original(): assert False\ndef test_added(): assert True\n",
        "def test_original(): assert True\ndef test_added(): pass\n",
        "def test_original(): assert True\ndef test_original(): assert True\n",
        "def test_original(:\n",
    ],
)
def test_regression_validation_rejects_weakened_or_missing_tests(modified):
    with pytest.raises(InvestigationRejected):
        repair._validate_regression_tests(
            "def test_original(): assert True\n", modified
        )


def test_regression_validation_accepts_new_asserting_test():
    repair._validate_regression_tests(
        "def test_original(): assert True\n",
        "def test_original(): assert True\ndef test_new_regression(): assert 1 == 1\n",
    )


def test_application_change_boundary_rejects_auth_and_side_effects():
    original = (
        "def create_app():\n"
        "    if request_telemetry.enabled and False:\n"
        '        app.mount("/metrics", request_telemetry.metrics_app)\n'
        '    @app.get("/health")\n'
        "    def health():\n"
        '        return {"status": "ok"}\n'
        "    configure_auth()\n"
    )
    fixed = original.replace(
        "request_telemetry.enabled and False", "request_telemetry.enabled"
    )
    repair._validate_application_change(original, fixed)
    for modified in (
        fixed.replace("configure_auth()", "pass"),
        fixed.replace('{"status": "ok"}', '__import__("os").environ'),
        fixed.replace("request_telemetry.enabled:", "dangerous_call():"),
        "import os\n" + fixed,
    ):
        with pytest.raises(InvestigationRejected):
            repair._validate_application_change(original, modified)


def test_repair_queue_requires_complete_revision_bound_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(
        repair, "_check_evidence_schema", lambda evidence, status: evidence
    )
    engine = _engine(tmp_path)
    with Session(engine) as session:
        complete = _record()
        incomplete = _record(fingerprint="1111111111111111", status="partial")
        no_revision = _record(fingerprint="2222222222222222", revision="unknown")
        session.add_all((complete, incomplete, no_revision))
        session.flush()

        assert repair.queue_repair_job(session, complete) == "queued"
        assert repair.queue_repair_job(session, incomplete) == "escalated"
        assert repair.queue_repair_job(session, no_revision) == "escalated"
        session.commit()

        jobs = list(session.scalars(select(IncidentRepairJob)))
        assert {job.status for job in jobs} == {"queued", "escalated"}
        assert {job.failure_code for job in jobs if job.status == "escalated"} == {
            "evidence_incomplete",
            "application_revision_unavailable",
        }
        events = list(session.scalars(select(IncidentAuditEvent)))
        assert len(events) == 6
    engine.dispose()


def test_only_one_active_repair_job_per_fingerprint(tmp_path, monkeypatch):
    monkeypatch.setattr(
        repair, "_check_evidence_schema", lambda evidence, status: evidence
    )
    engine = _engine(tmp_path)
    with Session(engine) as session:
        first = _record()
        second = _record()
        second.starts_at = datetime(2026, 11, 2, tzinfo=UTC)
        session.add_all((first, second))
        session.flush()
        assert repair.queue_repair_job(session, first) == "queued"
        assert repair.queue_repair_job(session, second) == "escalated"
        session.commit()

        jobs = list(
            session.scalars(
                select(IncidentRepairJob).where(
                    IncidentRepairJob.fingerprint == first.fingerprint
                )
            )
        )
        assert [job.status for job in jobs].count("queued") == 1
        assert [job.failure_code for job in jobs if job.status == "escalated"] == [
            "fingerprint_already_active"
        ]
    engine.dispose()


def test_open_pull_request_does_not_block_another_fingerprint(tmp_path, monkeypatch):
    monkeypatch.setattr(repair, "_check_evidence_schema", lambda evidence, status: {})
    engine = _engine(tmp_path)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        first = _record()
        second = _record(fingerprint="1111111111111111")
        session.add_all((first, second))
        session.flush()
        repair.queue_repair_job(session, first)
        repair.queue_repair_job(session, second)
        session.commit()
    first_job = repair._claim_next_job(factory)
    with factory() as session:
        session.get(IncidentRepairJob, first_job).status = "pr_open"
        session.commit()
    assert repair._claim_next_job(factory) is not None
    engine.dispose()


@pytest.mark.parametrize(
    "failure", ["model", "patch", "github", "tests", "base_mismatch", "pull_request"]
)
def test_worker_escalates_failures_after_model(tmp_path, monkeypatch, caplog, failure):
    monkeypatch.delenv("BENCHSCOPE_REPAIR_GH_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(
        repair, "_check_evidence_schema", lambda evidence, status: evidence
    )
    repo = tmp_path / "repo"
    (repo / "backend" / "app").mkdir(parents=True)
    (repo / "backend" / "tests").mkdir(parents=True)
    app_path = repo / "backend" / "app" / "main.py"
    test_path = repo / "backend" / "tests" / "test_health_contract.py"
    app_path.write_text('def health(): return "bad"\n', encoding="utf-8")
    test_path.write_text("def test_health(): assert True\n", encoding="utf-8")

    def git(*args):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    git("init")
    git("config", "user.name", "BenchScope Test")
    git("config", "user.email", "test@example.invalid")
    git("remote", "add", "origin", "https://github.com/shanegore/benchscope.git")
    git("add", "backend")
    git("commit", "-m", "synthetic source")
    revision = (
        subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True
        )
        .stdout.decode("ascii")
        .strip()
    )

    engine = create_engine(f"sqlite:///{tmp_path / 'repair.sqlite'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        record = _record(revision=revision)
        session.add(record)
        session.flush()
        assert repair.queue_repair_job(session, record) == "queued"
        session.commit()
        incident_id = record.id

    patch = (
        "diff --git a/backend/app/main.py b/backend/app/main.py\n"
        "--- a/backend/app/main.py\n+++ b/backend/app/main.py\n"
        '@@ -1 +1 @@\n-def health(): return "bad"\n'
        '+def health(): return "good"\n'
        "diff --git a/backend/tests/test_health_contract.py "
        "b/backend/tests/test_health_contract.py\n"
        "--- a/backend/tests/test_health_contract.py\n"
        "+++ b/backend/tests/test_health_contract.py\n"
        "@@ -1 +1,3 @@\n def test_health(): assert True\n"
        '+from app.main import health\n+def test_health_contract(): assert health() == "good"\n'
    )
    usage = CopilotUsage(repair.MODEL, 1, 1, 1, 100, 10)

    class Provider:
        def __init__(self):
            self.prompts = []

        def invoke(self, prompt):
            self.prompts.append(prompt)
            if failure == "model":
                raise InvestigationBlocked("private-log-sentinel")
            return repair.RepairRecommendation(
                "Health returns an invalid status.",
                0.9,
                (("backend/app/main.py", 1),),
                patch,
                usage,
                repair.MODEL,
                repair.MODEL,
            )

    provider = Provider()
    test_runs = []

    def run_tests(root, worktree):
        test_runs.append(worktree)
        if failure == "tests":
            raise InvestigationBlocked("synthetic test failure")

    monkeypatch.setattr(repair, "run_repair_tests", run_tests)
    monkeypatch.setattr(repair, "_validate_application_change", lambda *args: None)
    if failure == "patch":

        def invalid_patch(*args):
            raise repair.RepairCommandError("failed")

        monkeypatch.setattr(repair, "apply_repair_patch", invalid_patch)

    def missing_github():
        raise InvestigationBlocked("GitHub CLI authentication is unavailable")

    if failure == "github":
        monkeypatch.setattr(repair, "_github_environment", missing_github)
    else:
        monkeypatch.setattr(repair, "_github_environment", dict)
    if failure in {"base_mismatch", "pull_request"}:
        original_run = repair._run_host_command

        def fake_run(args, **kwargs):
            if args[0] == "git" and "ls-remote" in args:
                remote_revision = "0" * 40 if failure == "base_mismatch" else revision
                return f"{remote_revision}\trefs/heads/main\n".encode()
            if args[0] == "git" and "push" in args:
                return b""
            return original_run(args, **kwargs)

        def failed_pull_request(*args):
            raise InvestigationBlocked("synthetic GitHub failure")

        monkeypatch.setattr(repair, "_run_host_command", fake_run)
        if failure == "pull_request":
            monkeypatch.setattr(repair, "_create_pull_request", failed_pull_request)
    assert repair.run_next_repair_job(factory, repo, provider=provider) == "escalated"
    assert len(provider.prompts) == 1
    assert len(test_runs) == (0 if failure in {"model", "patch"} else 1)
    assert "private-log-sentinel" not in caplog.text
    with factory() as session:
        job = session.scalar(select(IncidentRepairJob))
        record = session.get(IncidentRecord, incident_id)
        assert job.status == "escalated"
        assert (
            job.failure_code
            == {
                "github": "github_permissions_unverified",
                "model": "model_invocation_blocked",
                "patch": "patch_rejected",
                "tests": "tests_failed",
                "base_mismatch": "source_revision_mismatch",
                "pull_request": "pull_request_failed",
            }[failure]
        )
        assert job.attempts == 1
        assert record.investigation_status == "failed"
        events = [
            event.reason_code
            for event in session.scalars(
                select(IncidentAuditEvent).where(
                    IncidentAuditEvent.incident_id == incident_id
                )
            )
        ]
        assert events[:3] == [
            "repair_job_queued",
            "sanitized_evidence_ready",
            "repair_started",
        ]
        if failure != "model":
            assert events[3] == "copilot_patch_validated"
        if failure not in {"model", "patch", "tests"}:
            assert events[4] == "tests_passed"
        assert (
            events[-1]
            == {
                "github": "github_permissions_unverified",
                "model": "investigation_failed",
                "patch": "patch_rejected",
                "tests": "tests_failed",
                "base_mismatch": "investigation_failed",
                "pull_request": "pull_request_failed",
            }[failure]
        )
    engine.dispose()


def test_repair_response_requires_strict_schema_and_allowlisted_paths():
    patch = (
        "diff --git a/backend/app/main.py b/backend/app/main.py\n"
        "diff --git a/backend/tests/test_app.py b/backend/tests/test_app.py\n"
    )
    content = json.dumps(
        {
            "root_cause": "Health route reports the wrong status.",
            "confidence": 0.9,
            "evidence": [{"path": "backend/app/main.py", "line": 1}],
            "patch": patch,
        }
    )
    result = repair.parse_repair_recommendation(
        content,
        allowed_files={"backend/app/main.py", "backend/tests/test_app.py"},
        source_files={"backend/app/main.py": "x\n", "backend/tests/test_app.py": "y\n"},
    )
    assert result.root_cause == "Health route reports the wrong status."
    assert result.confidence == 0.9

    bad_values = [
        "```json\n" + content + "\n```",
        content.replace("backend/app/main.py", "../../secrets.env"),
        content.replace('"confidence": 0.9', '"confidence": true'),
        content.replace('"line": 1', '"line": 3'),
        content.replace("Health route", "token=ghp_abcdefghijklmnopqrstuvwxyz012345"),
        json.dumps({**json.loads(content), "patch": patch + "+token=example-secret\n"}),
    ]
    for bad in bad_values:
        with pytest.raises(InvestigationRejected):
            repair.parse_repair_recommendation(
                bad,
                allowed_files={"backend/app/main.py", "backend/tests/test_app.py"},
                source_files={
                    "backend/app/main.py": "x\n",
                    "backend/tests/test_app.py": "y\n",
                },
            )


def test_repair_provider_refuses_unauthorized_invocation(monkeypatch):
    calls = []

    def should_not_run(*args, **kwargs):
        calls.append(args)
        raise AssertionError("Copilot must not be invoked")

    monkeypatch.setattr(repair, "_verify_cli_restrictions", should_not_run)
    provider = repair.CopilotRepairProvider("copilot")
    with pytest.raises(InvestigationBlocked, match="not authorized"):
        provider.invoke("synthetic prompt")
    assert not calls


def test_repair_provider_uses_explicit_cli_without_falling_back(monkeypatch):
    monkeypatch.setenv("BENCHSCOPE_COPILOT_CLI", "missing-configured-cli")
    provider = repair.CopilotRepairProvider()
    assert provider.executable == "missing-configured-cli"
    assert repair.CopilotRepairProvider("explicit-cli").executable == "explicit-cli"


def test_repair_preflight_rejects_runtime_missing_session_sync_control(
    tmp_path, monkeypatch
):
    calls = []

    def fake_run(args, cwd, timeout, output_limit, env):
        calls.append(args)
        return (
            (
                b"--model --prompt --output-format --available-tools --deny-tool "
                b"--disable-builtin-mcps --disallow-temp-dir --no-custom-instructions "
                b"--no-ask-user --no-auto-update --max-ai-credits --secret-env-vars "
                b"--usage-output-file"
            ),
            b"",
        )

    monkeypatch.setattr(repair, "_run_cli_process", fake_run)
    with pytest.raises(InvestigationBlocked, match="safety flags"):
        repair._verify_cli_restrictions("copilot", tmp_path, {})
    assert len(calls) == 1
    assert "--prompt" not in calls[0]


def test_repair_prompt_requests_the_validated_patch_format(monkeypatch):
    monkeypatch.setattr(repair, "_check_evidence_schema", lambda evidence, status: {})
    prompt = repair.make_repair_prompt(
        _record(),
        {
            "backend/app/main.py": "def health(): return 'bad'\n",
            "backend/tests/test_health_contract.py": "def test_health(): assert True\n",
        },
    )
    assert "diff --git a/PATH b/PATH" in prompt
    assert "regression test" in prompt


def test_repair_provider_uses_cli_login_without_exporting_tokens(monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", "isolated-home-sentinel")
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", "copilot-secret-sentinel")
    monkeypatch.setenv("GH_TOKEN", "github-secret-sentinel")
    if os.name == "nt":
        monkeypatch.setenv("HOME", "wrong-home-sentinel")
        monkeypatch.setenv("USERPROFILE", "profile-home-sentinel")
    environment = repair._cli_environment()
    assert "COPILOT_HOME" not in environment
    assert "COPILOT_GITHUB_TOKEN" not in environment
    assert "GH_TOKEN" not in environment
    if os.name == "nt":
        assert environment["HOME"] == "profile-home-sentinel"


def test_patch_application_rejects_paths_outside_allowlist(tmp_path):
    patch = (
        "diff --git a/backend/.env b/backend/.env\n"
        "--- a/backend/.env\n+++ b/backend/.env\n"
    )
    with pytest.raises(InvestigationRejected, match="prohibited"):
        repair.apply_repair_patch(tmp_path, patch)


def test_patch_application_recounts_hunks_without_relaxing_context(tmp_path):
    source = tmp_path / "backend" / "app" / "main.py"
    source.parent.mkdir(parents=True)
    source.write_text("before\nold\nafter\n", encoding="utf-8")
    patch = (
        "diff --git a/backend/app/main.py b/backend/app/main.py\n"
        "--- a/backend/app/main.py\n"
        "+++ b/backend/app/main.py\n"
        "@@ -1,4 +1,4 @@\n"
        " before\n"
        "-old\n"
        "+new\n"
        " after\n"
    )
    assert repair.apply_repair_patch(tmp_path, patch) == {"backend/app/main.py"}
    assert source.read_text(encoding="utf-8") == "before\nnew\nafter\n"

    source.write_text("before\ndifferent\nafter\n", encoding="utf-8")
    with pytest.raises(InvestigationBlocked):
        repair.apply_repair_patch(tmp_path, patch)
    assert source.read_text(encoding="utf-8") == "before\ndifferent\nafter\n"

    source.write_text("before\nold\nafter\n", encoding="utf-8")
    with pytest.raises(InvestigationBlocked):
        repair.apply_repair_patch(tmp_path, patch.replace("+new\n", "+new \n"))
    assert source.read_text(encoding="utf-8") == "before\nold\nafter\n"


def test_binary_patch_is_rejected():
    patch = (
        "diff --git a/backend/app/main.py b/backend/app/main.py\n"
        "GIT binary patch\nliteral 1\n"
    )
    with pytest.raises(InvestigationRejected, match="binary"):
        repair._patch_paths(patch, set(repair.REPAIR_SOURCE_FILES))


def test_repair_model_stream_limit_is_bounded_above_patch_limit(monkeypatch):
    observed = []
    monkeypatch.setattr(repair, "_verify_cli_restrictions", lambda *args: None)

    def run(*args, **kwargs):
        observed.append(kwargs["output_limit"])
        raise InvestigationBlocked("test")

    monkeypatch.setattr(repair, "_run_cli_process", run)
    with pytest.raises(InvestigationBlocked):
        repair.CopilotRepairProvider("copilot", authorized=True).invoke("test prompt")
    assert observed == [2 * 1024 * 1024]
    assert repair._PATCH_LIMIT_BYTES == 64 * 1024


def test_timed_out_container_is_explicitly_removed(tmp_path, monkeypatch):
    dockerfile = tmp_path / "backend" / "Dockerfile.repair-test"
    dockerfile.parent.mkdir()
    dockerfile.touch()
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        if args[1] == "run":
            raise repair.RepairCommandError("timed_out")
        return b""

    monkeypatch.setattr(repair.shutil, "which", lambda command: "docker")
    monkeypatch.setattr(repair, "_run_host_command", run)
    with pytest.raises(
        repair.RepairCommandError, match="trusted repair command failed"
    ):
        repair.run_repair_tests(tmp_path, tmp_path)
    name = calls[1][calls[1].index("--name") + 1]
    assert calls[2] == ["docker", "rm", "--force", name]


def test_worker_rejects_hosted_mode_before_connecting(monkeypatch):
    monkeypatch.setenv("APP_MODE", "hosted")
    monkeypatch.setenv("BENCHSCOPE_COPILOT_REPAIR_ENABLED", "true")
    with pytest.raises(SystemExit, match="APP_MODE=local"):
        repair.main()


def test_worker_rejects_remote_database_before_connecting(monkeypatch):
    monkeypatch.setenv("APP_MODE", "local")
    monkeypatch.setenv("BENCHSCOPE_COPILOT_REPAIR_ENABLED", "true")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@example.invalid/db")
    with pytest.raises(SystemExit, match="loopback PostgreSQL"):
        repair.main()


def test_restart_escalates_interrupted_job_without_retry(tmp_path, monkeypatch):
    monkeypatch.setattr(repair, "_check_evidence_schema", lambda evidence, status: {})
    engine = _engine(tmp_path)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        record = _record()
        session.add(record)
        session.flush()
        repair.queue_repair_job(session, record)
        session.commit()
        incident_id = record.id
    job_id = repair._claim_next_job(factory)
    assert job_id is not None
    repair._recover_interrupted_jobs(factory)
    assert repair._claim_next_job(factory) is None
    with factory() as session:
        job = session.get(IncidentRepairJob, job_id)
        record = session.get(IncidentRecord, incident_id)
        assert job.status == "escalated"
        assert job.failure_code == "worker_interrupted"
        assert job.attempts == 1
        assert record.investigation_status == "failed"
    engine.dispose()


def test_existing_github_login_is_used_without_exporting_a_token(monkeypatch):
    monkeypatch.delenv("BENCHSCOPE_REPAIR_GH_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs["env"]))
        return b""

    monkeypatch.setattr(repair, "_run_host_command", fake_run)
    environment = repair._github_environment()
    assert "GH_TOKEN" not in environment
    assert calls[0][0] == ["gh", "auth", "status", "--hostname", "github.com"]
    assert environment["GH_PROMPT_DISABLED"] == "1"


def test_pull_request_is_draft_and_contains_incident_evidence(tmp_path, monkeypatch):
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["body"] = Path(args[args.index("--body-file") + 1]).read_text()
        return b"https://github.com/ShaneGore/BenchScope/pull/999"

    monkeypatch.setattr(repair, "_run_host_command", fake_run)
    record = _record()
    record.id = uuid4()
    job = SimpleNamespace(fingerprint=record.fingerprint)
    recommendation = repair.RepairRecommendation(
        "Health check fails.", 0.9, (("backend/app/main.py", 1),), "patch"
    )
    url = repair._create_pull_request(
        tmp_path, "repair/test", "main", record, job, recommendation, {}
    )
    assert url.endswith("/999")
    assert "--draft" in captured["args"]
    assert str(record.id) in captured["body"]
    assert "health-contract tests and Ruff passed" in captured["body"]


@pytest.mark.parametrize(
    "case", ["passed", "missing", "wrong_sha", "failed", "timeout"]
)
def test_ci_requires_all_five_passing_checks_and_matching_sha(
    tmp_path, monkeypatch, case
):
    engine = _engine(tmp_path)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    sha = "a" * 40
    with factory() as session:
        record = _record()
        session.add(record)
        session.flush()
        job = IncidentRepairJob(
            incident_id=record.id,
            fingerprint=record.fingerprint,
            source_revision=sha,
            status="pr_open",
            attempts=1,
            pull_request_sha=sha,
        )
        session.add(job)
        session.commit()
        job_id, incident_id = job.id, record.id

    names = ["backend", "frontend", "journey", "container-images", "backend-windows"]
    if case == "missing":
        names.pop()
    checks = [{"name": name, "workflow": "CI", "bucket": "pass"} for name in names]

    def fake_run(args, **kwargs):
        if "--watch" in args:
            if case in {"failed", "timeout"}:
                raise repair.RepairCommandError(
                    "timed_out" if case == "timeout" else "failed"
                )
            return b""
        if "view" in args:
            return json.dumps(
                {"headRefOid": "b" * 40 if case == "wrong_sha" else sha}
            ).encode()
        return json.dumps(checks).encode()

    monkeypatch.setattr(repair, "_run_host_command", fake_run)
    result = repair._wait_for_ci(
        factory, job_id, incident_id, "https://example.invalid", tmp_path, {}
    )
    assert result == {"passed": "ci_passed", "timeout": "pr_open"}.get(
        case, "ci_failed"
    )
    with factory() as session:
        job = session.get(IncidentRepairJob, job_id)
        assert job.ci_status == {"passed": "passed", "timeout": "timed_out"}.get(
            case, "failed"
        )
    engine.dispose()
