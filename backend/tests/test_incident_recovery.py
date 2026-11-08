import json
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


def _container(service, digit, running=True):
    expected = recovery.EXPECTED_BINDINGS[service]
    return {
        "Id": digit * 64,
        "Config": {
            "Labels": {
                "com.docker.compose.project": recovery.RECOVERY_PROJECT,
                "com.docker.compose.service": service,
            }
        },
        "State": {"Running": running},
        "HostConfig": {
            "PortBindings": (
                {expected[0]: [{"HostIp": "127.0.0.1", "HostPort": str(expected[1])}]}
                if expected
                else None
            )
        },
    }


def _mock_inspection(monkeypatch, containers, occupied=()):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        output = (
            "\n".join(c["Id"] for c in containers)
            if command[1] == "ps"
            else json.dumps(containers)
        )
        return subprocess.CompletedProcess(command, 0, stdout=output)

    monkeypatch.setattr(recovery.subprocess, "run", run)
    monkeypatch.setattr(recovery, "check_host_ports", lambda: list(occupied))
    return calls


def test_observation_distinguishes_survivor_from_conflict(monkeypatch):
    containers = [_container("api", "a", False), _container("db", "b")]
    calls = _mock_inspection(monkeypatch, containers, [15432, 18000])
    observed = recovery.inspect_disposable_project()
    assert observed == {
        "api_container_id": "a" * 64,
        "surviving_service_ports": [15432],
        "unproven_listener_ports": [15432],
        "conflicting_ports": [18000],
    }
    assert [call[0][1] for call in calls] == ["ps", "inspect"]
    assert all(
        call[1]["timeout"] == recovery.INSPECTION_TIMEOUT_SECONDS for call in calls
    )
    assert recovery.RECOVERY_PROJECT in calls[0][0][-1]


@pytest.mark.parametrize(
    "case",
    [
        "absent",
        "no-api",
        "duplicate",
        "wrong-project",
        "bad-service",
        "bad-binding",
        "bad-state",
        "bad-id",
    ],
)
def test_inspection_rejects_bad_identity_and_mappings(monkeypatch, case):
    api = _container("api", "a", False)
    containers = [api]
    if case == "absent":
        containers = []
    elif case == "no-api":
        containers = [_container("db", "b")]
    elif case == "duplicate":
        containers.append(_container("api", "b"))
    elif case == "wrong-project":
        api["Config"]["Labels"]["com.docker.compose.project"] = "other"
    elif case == "bad-service":
        api["Config"]["Labels"]["com.docker.compose.service"] = "other"
    elif case == "bad-binding":
        api["HostConfig"]["PortBindings"]["8000/tcp"][0]["HostIp"] = "0.0.0.0"
    elif case == "bad-state":
        api["State"]["Running"] = 1
    else:
        api["Id"] = "not-an-id"
    _mock_inspection(monkeypatch, containers)
    with pytest.raises(recovery.RecoveryBlocked):
        recovery.inspect_disposable_project()


@pytest.mark.parametrize("failure", ["timeout", "error", "malformed"])
def test_inspection_errors_fail_closed(monkeypatch, failure):
    def run(command, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 5)
        if failure == "error":
            return subprocess.CompletedProcess(command, 1, stdout="")
        return subprocess.CompletedProcess(
            command, 0, stdout=("a" * 64 if command[1] == "ps" else "{")
        )

    monkeypatch.setattr(recovery.subprocess, "run", run)
    with pytest.raises(recovery.RecoveryBlocked):
        recovery.inspect_disposable_project()


def test_listener_inspection_is_read_only_and_fails_closed(monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="Proto Local Address Foreign Address State PID\n"
            "TCP 0.0.0.0:15432 0.0.0.0:0 LISTENING 42\n"
            "TCP [::1]:18000 [::]:0 LISTENING 43\n",
        )

    monkeypatch.setattr(recovery.subprocess, "run", run)
    assert recovery.check_host_ports() == [15432, 18000]
    assert calls[0][0] == ["netstat", "-ano"]
    assert calls[0][1]["timeout"] == recovery.INSPECTION_TIMEOUT_SECONDS
    monkeypatch.setattr(
        recovery.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout=""),
    )
    with pytest.raises(recovery.RecoveryBlocked):
        recovery.check_host_ports()


@pytest.mark.parametrize(
    "body",
    [
        "Proto garbage\n",
        "Proto Local Address Foreign Address State PID\ninvalid line\n",
        "Proto Local Address Foreign Address State PID\nTCp invalid [::]:0 LISTENING 3\n",
        "Proto Local Address Foreign Address State PID\nTCP 0.0.0.0:18000 bad LISTENING 3\n",
        "Proto Local Address Foreign Address State PID\nTCP 0.0.0.0:18000 [::]:0 LISTENING nope\n",
        "Proto Local Address Foreign Address State PID\nUDP nonsense\n",
        "unexpected output\nProto Local Address Foreign Address State PID\n",
    ],
)
def test_listener_inspection_rejects_malformed_output(monkeypatch, body):
    monkeypatch.setattr(
        recovery.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, stdout=body),
    )
    with pytest.raises(recovery.RecoveryBlocked):
        recovery.check_host_ports()


def test_listener_inspection_accepts_case_and_valid_udp(monkeypatch):
    body = (
        "Active Connections\n\n"
        "proto Local Address Foreign Address State PID\n"
        "tcp 127.0.0.1:18000 0.0.0.0:0 listening 12\n"
        "UDP [::]:53 *:* 13\n"
    )
    monkeypatch.setattr(
        recovery.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, stdout=body),
    )
    assert recovery.check_host_ports() == [18000]


def test_observed_listener_does_not_prove_ownership(monkeypatch):
    containers = [_container("api", "a", False), _container("db", "b")]

    def run(command, **kwargs):
        if command[0] == "netstat":
            output = (
                "Proto Local Address Foreign Address State PID\n"
                "tcp 127.0.0.1:15432 0.0.0.0:0 listening 12\n"
            )
        elif command[1] == "ps":
            output = "\n".join(item["Id"] for item in containers)
        else:
            output = json.dumps(containers)
        return subprocess.CompletedProcess(command, 0, stdout=output)

    monkeypatch.setattr(recovery.subprocess, "run", run)
    approval = _approval()
    with pytest.raises(recovery.RecoveryBlocked, match="ownership is unproven"):
        recovery.execute_fixed_recovery(approval=approval, env_config=DISPOSABLE_ENV)
    assert not approval.used and not approval.attempted


@pytest.mark.parametrize("occupied", [(), (15432,), (18000,)])
def test_observation_never_executes_or_consumes_approval(monkeypatch, occupied):
    calls = _mock_inspection(
        monkeypatch, [_container("api", "a", False), _container("db", "b")], occupied
    )
    approval = _approval()
    executed = []
    with pytest.raises(recovery.RecoveryBlocked):
        recovery.execute_fixed_recovery(
            approval=approval,
            env_config=dict(DISPOSABLE_ENV),
            project_identity=recovery.RECOVERY_PROJECT,
            ports=[],
            executor=lambda *args, **kwargs: executed.append(args),
        )
    assert not executed
    assert not approval.used and not approval.attempted
    assert approval.decision == "approved"
    assert [call[0][1] for call in calls] == ["ps", "inspect"]


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


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (
            {
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [{"metric": {"job": "api"}, "value": [1, "1"]}],
                },
            },
            True,
        ),
        (
            {
                "status": "error",
                "data": {
                    "resultType": "vector",
                    "result": [{"metric": {"job": "api"}, "value": [1, "1"]}],
                },
            },
            False,
        ),
        ({"status": "success", "data": None}, False),
        ({}, False),
        ([], False),
        ({"status": "success", "data": {"resultType": "matrix", "result": []}}, False),
        (
            {"status": "success", "data": {"resultType": "vector", "result": None}},
            False,
        ),
        (
            {"status": "success", "data": {"resultType": "vector", "result": [{}]}},
            False,
        ),
        (
            {
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [{"metric": {"job": "api"}, "value": [1, "0"]}],
                },
            },
            False,
        ),
        (
            {
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [{"metric": {}, "value": [1, "1"]}],
                },
            },
            False,
        ),
        (
            {
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [{"metric": {"job": "api"}, "value": [1, "1"]}, None],
                },
            },
            False,
        ),
    ],
)
def test_prometheus_target_response(monkeypatch, payload, expected):
    class Resp:
        status = 200

        def read(self):
            return json.dumps(payload).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(recovery.urllib.request, "urlopen", lambda *a, **k: Resp())
    assert recovery.verify_prometheus_target() is expected


@pytest.mark.parametrize("status,body", [(500, b"{}"), (200, b"{"), (200, b"\xff")])
def test_prometheus_target_invalid_http_response(monkeypatch, status, body):
    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return body

    response = Resp()
    response.status = status
    monkeypatch.setattr(recovery.urllib.request, "urlopen", lambda *a, **k: response)
    assert recovery.verify_prometheus_target() is False


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"status": "success", "data": {"resultType": "vector", "result": []}}, True),
        ({"status": "error", "data": {"resultType": "vector", "result": []}}, False),
        ({"status": "success", "data": None}, False),
        (
            {
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [
                        {
                            "metric": {
                                "alertname": "BenchScopeApiUnavailable",
                                "alertstate": "firing",
                            },
                            "value": [1, "1"],
                        }
                    ],
                },
            },
            False,
        ),
    ],
)
@pytest.mark.parametrize("alert_resolved", [None, True])
def test_verification_queries_alert_even_with_caller_assertion(
    monkeypatch, payload, expected, alert_resolved
):
    class Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(payload).encode()

    calls = []

    def fake_urlopen(url, **kwargs):
        calls.append(url)
        return Resp()

    monkeypatch.setattr(recovery.urllib.request, "urlopen", fake_urlopen)
    result = recovery.verify_recovery(
        api_readiness=True,
        prometheus_target=True,
        alert_resolved=alert_resolved,
        persistence=True,
        smoke_test=True,
    )
    assert result.success is expected
    assert calls == [recovery.ALERTS_QUERY_URL]


def test_caller_assertion_cannot_override_alert_request_error(monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("down")

    monkeypatch.setattr(recovery.urllib.request, "urlopen", fail)
    result = recovery.verify_recovery(
        api_readiness=True,
        prometheus_target=True,
        alert_resolved=True,
        persistence=True,
        smoke_test=True,
    )
    assert not result.success


@pytest.mark.parametrize("alert_resolved", [False, 1, "true"])
def test_invalid_alert_assertion_fails_closed(alert_resolved):
    result = recovery.verify_recovery(
        api_readiness=True,
        prometheus_target=True,
        alert_resolved=alert_resolved,
        persistence=True,
        smoke_test=True,
    )
    assert not result.success


@pytest.fixture
def resolved_alert(monkeypatch):
    class Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"status":"success","data":{"resultType":"vector","result":[]}}'

    monkeypatch.setattr(recovery.urllib.request, "urlopen", lambda *a, **k: Resp())


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"status": "success", "data": {"resultType": "vector", "result": []}}, True),
        (
            {
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [
                        {
                            "metric": {
                                "alertname": "BenchScopeApiUnavailable",
                                "alertstate": "firing",
                            },
                            "value": [1, "1"],
                        }
                    ],
                },
            },
            False,
        ),
        (
            {
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [
                        {
                            "metric": {
                                "alertname": "BenchScopeApiUnavailable",
                                "alertstate": "pending",
                            },
                            "value": [1, "1"],
                        }
                    ],
                },
            },
            False,
        ),
        (
            {
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [
                        {
                            "metric": {
                                "alertname": "BenchScopeApiUnavailable",
                                "alertstate": "firing",
                            },
                            "value": [1, "0"],
                        }
                    ],
                },
            },
            True,
        ),
        ({}, False),
        ({"status": "error", "data": {"resultType": "vector", "result": []}}, False),
        ({"status": "success", "data": {}}, False),
        ({"status": "success", "data": {"resultType": "matrix", "result": []}}, False),
        (
            {"status": "success", "data": {"resultType": "vector", "result": None}},
            False,
        ),
        (
            {"status": "success", "data": {"resultType": "vector", "result": [{}]}},
            False,
        ),
        (
            {
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [
                        {
                            "metric": {
                                "alertname": "BenchScopeApiUnavailable",
                                "alertstate": "firing",
                            },
                            "value": [1, None],
                        }
                    ],
                },
            },
            False,
        ),
        ([], False),
    ],
)
def test_alert_resolution_response(monkeypatch, payload, expected):
    class Resp:
        status = 200

        def read(self):
            return json.dumps(payload).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(recovery.urllib.request, "urlopen", lambda *a, **k: Resp())
    assert recovery.verify_alert_resolution(timeout=0, poll_interval=0) is expected


@pytest.mark.parametrize("failure", [OSError("down"), TimeoutError("timeout")])
def test_alert_resolution_request_failure(monkeypatch, failure):
    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(recovery.urllib.request, "urlopen", fail)
    assert recovery.verify_alert_resolution(timeout=0, poll_interval=0) is False


@pytest.mark.parametrize("status,body", [(500, b"{}"), (200, b"{"), (200, b"\xff")])
def test_alert_resolution_invalid_http_response(monkeypatch, status, body):
    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return body

    response = Resp()
    response.status = status
    monkeypatch.setattr(recovery.urllib.request, "urlopen", lambda *a, **k: response)
    assert recovery.verify_alert_resolution(timeout=0, poll_interval=0) is False


def test_persistence_failure():
    assert recovery.verify_synthetic_run_persisted(None, None) is False
    assert recovery.verify_synthetic_run_persisted("abc", "def") is False
    assert recovery.verify_synthetic_run_persisted("abc", "abc") is True


def test_smoke_test_failure():
    def fake_executor(command, **kwargs):
        return subprocess.CompletedProcess(command, 1)

    result = recovery.run_recovery_smoke_test(executor=fake_executor)
    assert result.returncode == 1


def test_successful_verification(resolved_alert):
    result = recovery.verify_recovery(
        api_readiness=True,
        prometheus_target=True,
        alert_resolved=True,
        persistence=True,
        smoke_test=True,
    )
    assert result.success is True


@pytest.mark.parametrize("field", ["persistence", "smoke_test"])
@pytest.mark.parametrize("value", [None, False, 1, "true"])
def test_verification_requires_explicit_evidence(field, value, resolved_alert):
    checks = {
        "api_readiness": True,
        "prometheus_target": True,
        "alert_resolved": True,
        "persistence": True,
        "smoke_test": True,
    }
    checks[field] = value
    result = recovery.verify_recovery(**checks)
    assert result.success is False


def test_verification_result_rejects_missing_or_truthy_checks(resolved_alert):
    assert not recovery.RecoveryVerificationResult({"api_readiness": True}).success
    result = recovery.verify_recovery(
        api_readiness=1,
        prometheus_target=True,
        alert_resolved=True,
        persistence=True,
        smoke_test=True,
    )
    assert not result.success


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
