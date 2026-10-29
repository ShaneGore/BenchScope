import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from app import incident_recovery as recovery

DISPOSABLE_ENV = {
    "POSTGRES_DB": "x",
    "POSTGRES_USER": "y",
    "POSTGRES_PASSWORD": "z",
    "POSTGRES_PORT": "15432",
    "API_PORT": "18000",
    "PROMETHEUS_PORT": "19090",
    "GRAFANA_PORT": "13000",
    "LOKI_PORT": "13100",
    "TEMPO_PORT": "13200",
    "OTLP_PORT": "14318",
}


def _approval(now=None, **overrides):
    now = now or datetime.now(UTC)
    approval = recovery.request_recovery_approval(uuid4(), now=now)
    recovery.approve_recovery_approval(approval, approved=True, now=now)
    for key, value in overrides.items():
        setattr(approval, key, value)
    return approval


def test_fixed_command_vector():
    assert recovery.RECOVERY_COMMAND == (
        "docker",
        "compose",
        "--env-file",
        ".env.incident-response-disposable",
        "-f",
        "compose.yaml",
        "-p",
        "benchscope-incident-response-disposable",
        "restart",
        "api",
    )
    assert recovery.RECOVERY_WORKING_DIRECTORY == Path(__file__).resolve().parents[2]
    assert recovery.RECOVERY_SMOKE_TEST_COMMAND == (
        "uv",
        "run",
        "pytest",
        "-q",
        "tests/test_incident_recovery.py",
    )
    assert (
        recovery.RECOVERY_SMOKE_TEST_WORKING_DIRECTORY
        == Path(__file__).resolve().parents[1]
    )


def test_approval_missing():
    with pytest.raises(recovery.ApprovalInvalid):
        recovery.validate_approval(None, uuid4())


def test_approval_rejected():
    approval = recovery.request_recovery_approval(uuid4())
    recovery.approve_recovery_approval(approval, approved=False)
    with pytest.raises(recovery.ApprovalInvalid, match="rejected"):
        recovery.validate_approval(approval, approval.incident_id)


def test_approval_expired():
    now = datetime.now(UTC)
    approval = recovery.request_recovery_approval(uuid4(), now=now)
    recovery.approve_recovery_approval(approval, approved=True, now=now)
    later = now + timedelta(seconds=301)
    with pytest.raises(recovery.ApprovalInvalid, match="expired"):
        recovery.validate_approval(approval, approval.incident_id, now=later)


def test_approval_replayed():
    now = datetime.now(UTC)
    approval = _approval(now=now)
    recovery.consume_approval(approval, now=now)
    with pytest.raises(recovery.ApprovalInvalid, match="used"):
        recovery.validate_approval(approval, approval.incident_id, now=now)


def test_approval_mismatched_incident():
    now = datetime.now(UTC)
    approval = _approval(now=now)
    with pytest.raises(recovery.ApprovalInvalid, match="wrong incident"):
        recovery.validate_approval(approval, uuid4(), now=now)


def test_approval_cannot_modify_action():
    now = datetime.now(UTC)
    approval = _approval(now=now)
    approval.action = ("docker", "compose", "restart", "db")
    with pytest.raises(recovery.ApprovalInvalid):
        recovery.validate_approval(approval, approval.incident_id, now=now)


def test_no_command_on_invalid_approval(monkeypatch):
    calls = []

    def fake_executor(*args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args[0], 0)

    now = datetime.now(UTC)
    approval = recovery.request_recovery_approval(uuid4())  # not approved
    with pytest.raises(recovery.ApprovalInvalid):
        recovery.execute_fixed_recovery(
            approval=approval,
            now=now,
            executor=fake_executor,
            env_config=dict(DISPOSABLE_ENV),
        )
    assert calls == []


def test_wrong_project_identity():
    with pytest.raises(recovery.RecoveryBlocked, match="wrong Compose project"):
        recovery.verify_compose_project_identity(
            "benchscope", recovery.RECOVERY_PROJECT
        )


def test_missing_env_config():
    with pytest.raises(recovery.RecoveryBlocked):
        recovery.validate_disposable_env({})


def test_occupied_ports(monkeypatch):
    def fake_check(ports=None, host="127.0.0.1"):
        return [8000]

    monkeypatch.setattr(recovery, "check_host_ports", fake_check)
    with pytest.raises(recovery.RecoveryBlocked, match="occupied"):
        recovery.execute_fixed_recovery(
            approval=_approval(),
            env_config=dict(DISPOSABLE_ENV),
            ports=[8000],
        )


def test_exact_execution(monkeypatch):
    captured = {}

    def fake_executor(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0)

    now = datetime.now(UTC)
    approval = _approval(now=now)
    recovery.execute_fixed_recovery(
        approval=approval,
        env_config=dict(DISPOSABLE_ENV),
        ports=[],
        executor=fake_executor,
        now=now,
    )
    assert captured["command"] == list(recovery.RECOVERY_COMMAND)
    assert captured["kwargs"]["cwd"] == recovery.RECOVERY_WORKING_DIRECTORY
    assert captured["kwargs"]["env"] is None


def test_execution_failure():
    def fake_executor(command, **kwargs):
        return subprocess.CompletedProcess(command, 1)

    now = datetime.now(UTC)
    approval = _approval(now=now)
    with pytest.raises(recovery.RecoveryBlocked, match="failed"):
        recovery.execute_fixed_recovery(
            approval=approval,
            env_config=dict(DISPOSABLE_ENV),
            ports=[],
            executor=fake_executor,
            now=now,
        )


def test_execution_timeout():
    def fake_executor(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 1)

    now = datetime.now(UTC)
    approval = _approval(now=now)
    with pytest.raises(subprocess.TimeoutExpired):
        recovery.execute_fixed_recovery(
            approval=approval,
            env_config=dict(DISPOSABLE_ENV),
            ports=[],
            executor=fake_executor,
            now=now,
        )


def test_one_attempt_limit():
    def fake_executor(command, **kwargs):
        return subprocess.CompletedProcess(command, 0)

    now = datetime.now(UTC)
    approval = _approval(now=now)
    recovery.execute_fixed_recovery(
        approval=approval,
        env_config=dict(DISPOSABLE_ENV),
        ports=[],
        executor=fake_executor,
        now=now,
    )
    with pytest.raises(recovery.RecoveryBlocked, match="attempted"):
        recovery.execute_fixed_recovery(
            approval=approval,
            env_config=dict(DISPOSABLE_ENV),
            ports=[],
            executor=fake_executor,
            now=now,
        )


def test_no_success_after_failed_action():
    def fake_executor(command, **kwargs):
        return subprocess.CompletedProcess(command, 1)

    now = datetime.now(UTC)
    approval = _approval(now=now)
    try:
        recovery.execute_fixed_recovery(
            approval=approval,
            env_config=dict(DISPOSABLE_ENV),
            ports=[],
            executor=fake_executor,
            now=now,
        )
    except recovery.RecoveryBlocked:
        pass
    assert approval.decision == "consumed"
    assert not hasattr(approval, "success")


def test_api_readiness_failure(monkeypatch):
    monkeypatch.setattr(
        recovery.urllib.request,
        "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(OSError("down")),
    )
    assert recovery.verify_api_readiness() is False


def test_prometheus_failure(monkeypatch):
    monkeypatch.setattr(
        recovery.urllib.request,
        "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(OSError("down")),
    )
    assert recovery.verify_prometheus_target() is False


def test_alert_not_resolved(monkeypatch):
    class Resp:
        def read(self):
            return b'{"data":{"result":[{"value":[1,"1"]}]}}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(recovery.urllib.request, "urlopen", lambda *a, **k: Resp())
    assert recovery.verify_alert_resolution(timeout=0, poll_interval=0) is False


def test_persistence_failure():
    assert recovery.verify_synthetic_run_persisted("abc", "def") is False
    assert recovery.verify_synthetic_run_persisted("abc", "abc") is True


def test_smoke_test_failure():
    def fake_executor(command, **kwargs):
        return subprocess.CompletedProcess(command, 1)

    result = recovery.run_recovery_smoke_test(executor=fake_executor)
    assert result.returncode == 1


def test_successful_verification():
    result = recovery.verify_recovery(
        api_readiness=True,
        prometheus_target=True,
        alert_resolved=True,
        persistence=True,
        smoke_test=True,
    )
    assert result.success is True


def test_audit_redaction():
    record = recovery.create_audit_record(
        incident_id=uuid4(),
        approval=_approval(),
        verification={"token": "secret-value", "count": 1},
        outcome="resolved",
        final_state="resolved",
    )
    assert record["verification"]["token"] == "[redacted]"
    assert "secret-value" not in str(record)
    assert record["final_state"] == "resolved"


def test_audit_no_sensitive_payload():
    record = recovery.create_audit_record(
        incident_id=uuid4(),
        verification={"raw_payload": "x", "secret": "y"},
    )
    assert record["verification"]["raw_payload"] == "[redacted]"
    assert record["verification"]["secret"] == "[redacted]"


def test_disposable_env_accepts_fixed_alternate_ports():
    assert recovery.validate_disposable_env(dict(DISPOSABLE_ENV)) == DISPOSABLE_ENV


def test_disposable_env_rejects_unexpected_port():
    bad = dict(DISPOSABLE_ENV, API_PORT="8000")
    with pytest.raises(recovery.RecoveryBlocked):
        recovery.validate_disposable_env(bad)


def test_disposable_env_rejects_missing_port():
    bad = dict(DISPOSABLE_ENV)
    del bad["PROMETHEUS_PORT"]
    with pytest.raises(recovery.RecoveryBlocked):
        recovery.validate_disposable_env(bad)
