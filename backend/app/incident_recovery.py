"""
Local-only, supervised Stage 3 incident recovery.
"""

from __future__ import annotations

import ipaddress
import json
import math
import re
import subprocess
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

RECOVERY_COMMAND = (
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
RECOVERY_ENV_FILE = ".env.incident-response-disposable"
RECOVERY_COMPOSE_FILE = "compose.yaml"
RECOVERY_PROJECT = "benchscope-incident-response-disposable"
RECOVERY_SERVICE = "api"
RECOVERY_TIMEOUT_SECONDS = 300
RECOVERY_WORKING_DIRECTORY = Path(__file__).resolve().parents[2]
RECOVERY_ATTEMPT_LIMIT = 1

APPROVAL_TTL_SECONDS = 300
ALERT_RESOLUTION_TIMEOUT_SECONDS = 180
ALERT_RESOLUTION_POLL_SECONDS = 1.0
READY_TIMEOUT_SECONDS = 5.0
PROMETHEUS_TIMEOUT_SECONDS = 5.0

RECOVERY_SMOKE_TEST_COMMAND = (
    "uv",
    "run",
    "pytest",
    "-q",
    "tests/test_incident_recovery.py",
)
RECOVERY_SMOKE_TEST_WORKING_DIRECTORY = Path(__file__).resolve().parents[1]
RECOVERY_SMOKE_TEST_TIMEOUT_SECONDS = 300

READY_URL = "http://127.0.0.1:18000/ready"
PROMETHEUS_QUERY_URL = (
    "http://127.0.0.1:19090/api/v1/query?query=up%7Bjob%3D%22api%22%7D"
)
ALERTS_QUERY_URL = "http://127.0.0.1:19090/api/v1/query?query=ALERTS%7Balertname%3D%22BenchScopeApiUnavailable%22%7D"

DISPOSABLE_REQUIRED_ENV_KEYS = frozenset(
    {"POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"}
)
DISPOSABLE_REQUIRED_HOST_PORTS = (18000, 15432, 19090, 13000, 13100, 13200, 14318)
DISPOSABLE_REQUIRED_PORT_ASSIGNMENTS = {
    "POSTGRES_PORT": 15432,
    "API_PORT": 18000,
    "PROMETHEUS_PORT": 19090,
    "GRAFANA_PORT": 13000,
    "LOKI_PORT": 13100,
    "TEMPO_PORT": 13200,
    "OTLP_PORT": 14318,
}
INSPECTION_TIMEOUT_SECONDS = 5
EXPECTED_BINDINGS = {
    "api": ("8000/tcp", 18000),
    "db": ("5432/tcp", 15432),
    "prometheus": ("9090/tcp", 19090),
    "grafana": ("3000/tcp", 13000),
    "loki": ("3100/tcp", 13100),
    "tempo": ("3200/tcp", 13200),
    "otel-collector": ("4318/tcp", 14318),
    "alert-receiver": None,
}

FORBIDDEN_AUDIT_KEYS = {
    "secret",
    "token",
    "password",
    "api_key",
    "credential",
    "prompt",
    "output",
    "raw",
    "bearer",
}


class RecoveryError(Exception):
    pass


class RecoveryBlocked(RecoveryError):
    pass


class RecoveryRejected(RecoveryError):
    pass


class ApprovalInvalid(RecoveryError):
    pass


@dataclass
class RecoveryApproval:
    approval_id: str = field(default_factory=lambda: str(uuid4()))
    incident_id: Any = None
    action: tuple[str, ...] = RECOVERY_COMMAND
    project: str = RECOVERY_PROJECT
    service: str = RECOVERY_SERVICE
    working_directory: Path = RECOVERY_WORKING_DIRECTORY
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    approved: bool = False
    used: bool = False
    attempted: bool = False
    decision: str = "pending"
    operator: str | None = None
    approved_at: datetime | None = None

    def __post_init__(self) -> None:
        if isinstance(self.working_directory, str):
            self.working_directory = Path(self.working_directory)
        if isinstance(self.action, list):
            self.action = tuple(self.action)
        if self.expires_at == self.created_at:
            self.expires_at = self.created_at + timedelta(seconds=APPROVAL_TTL_SECONDS)
        if self.approved and self.decision == "pending":
            self.decision = "approved"
            if self.approved_at is None:
                self.approved_at = self.created_at


@dataclass
class RecoveryVerificationResult:
    checks: dict[str, bool] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        required = {
            "api_readiness",
            "prometheus_target",
            "alert_resolution",
            "persistence",
            "recovery_smoke_test",
        }
        return required <= self.checks.keys() and all(
            value is True for value in self.checks.values()
        )

    def __bool__(self) -> bool:
        return self.success


@dataclass
class RecoveryAuditRecord:
    incident_id: str
    alert_reference: Any = None
    investigation_reference: Any = None
    approval: dict[str, Any] = field(default_factory=dict)
    action: list[str] = field(default_factory=lambda: list(RECOVERY_COMMAND))
    project: str = RECOVERY_PROJECT
    service: str = RECOVERY_SERVICE
    working_directory: str = str(RECOVERY_WORKING_DIRECTORY)
    started_at: str | None = None
    ended_at: str | None = None
    outcome: str = "unknown"
    verification: dict[str, bool] = field(default_factory=dict)
    final_state: str = "escalated"

    def to_dict(self) -> dict[str, Any]:
        return _redact(
            {
                "incident_id": self.incident_id,
                "alert_reference": self.alert_reference,
                "investigation_reference": self.investigation_reference,
                "approval": self.approval,
                "action": self.action,
                "project": self.project,
                "service": self.service,
                "working_directory": self.working_directory,
                "started_at": self.started_at,
                "ended_at": self.ended_at,
                "outcome": self.outcome,
                "verification": self.verification,
                "final_state": self.final_state,
            }
        )


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat()


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in FORBIDDEN_AUDIT_KEYS or any(
                part in lowered for part in FORBIDDEN_AUDIT_KEYS
            ):
                result[key] = "[redacted]"
            else:
                result[key] = _redact(item)
        return result
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        if "SENTINEL" in value.upper() or "SECRET" in value.upper():
            return "[redacted]"
        return value
    return value


def redact(value: Any) -> Any:
    return _redact(value)


def _as_uuid(value: Any) -> UUID | None:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def approval_is_expired(
    approval: RecoveryApproval, now: datetime | None = None
) -> bool:
    current = now or _now()
    return current >= approval.expires_at


def validate_approval(
    approval: Any,
    incident_id: Any = None,
    *,
    action: Any = None,
    project: str | None = None,
    service: str | None = None,
    working_directory: Any = None,
    now: datetime | None = None,
) -> None:
    if not isinstance(approval, RecoveryApproval):
        raise ApprovalInvalid("approval is missing")
    current = now or _now()
    if incident_id is not None and str(approval.incident_id) != str(incident_id):
        raise ApprovalInvalid("approval is bound to the wrong incident")
    if approval.used:
        raise ApprovalInvalid("approval has already been used")
    if not approval.approved or approval.decision != "approved":
        if approval.decision == "rejected":
            raise ApprovalInvalid("approval was rejected")
        if current >= approval.expires_at:
            approval.decision = "expired"
            raise ApprovalInvalid("approval has expired")
        raise ApprovalInvalid("approval is missing")
    if current >= approval.expires_at:
        approval.decision = "expired"
        raise ApprovalInvalid("approval has expired")
    expected_action = tuple(action) if action is not None else RECOVERY_COMMAND
    if tuple(approval.action) != tuple(expected_action):
        raise ApprovalInvalid("approval is bound to the wrong action")
    if project is not None and approval.project != project:
        raise ApprovalInvalid("approval is bound to the wrong project")
    if service is not None and approval.service != service:
        raise ApprovalInvalid("approval is bound to the wrong service")
    if working_directory is not None and Path(working_directory) != Path(
        approval.working_directory
    ):
        raise ApprovalInvalid("approval is bound to the wrong working directory")
    if approval.project != RECOVERY_PROJECT or approval.service != RECOVERY_SERVICE:
        raise ApprovalInvalid("approval target is invalid")
    if tuple(approval.action) != RECOVERY_COMMAND:
        raise ApprovalInvalid("approval cannot modify the fixed action")
    if Path(approval.working_directory) != RECOVERY_WORKING_DIRECTORY:
        raise ApprovalInvalid("approval is bound to the wrong working directory")


def request_recovery_approval(
    incident_id: Any,
    *,
    summary: str | None = None,
    alert_reference: Any = None,
    investigation_reference: Any = None,
    now: datetime | None = None,
    operator: str | None = None,
) -> RecoveryApproval:
    current = now or _now()
    approval = RecoveryApproval(
        incident_id=incident_id,
        action=RECOVERY_COMMAND,
        project=RECOVERY_PROJECT,
        service=RECOVERY_SERVICE,
        working_directory=RECOVERY_WORKING_DIRECTORY,
        created_at=current,
        expires_at=current + timedelta(seconds=APPROVAL_TTL_SECONDS),
        approved=False,
        decision="pending",
        operator=operator,
    )
    return approval


def approve_recovery_approval(
    approval: RecoveryApproval,
    *,
    approved: bool,
    now: datetime | None = None,
    operator: str | None = None,
) -> RecoveryApproval:
    current = now or _now()
    if not isinstance(approval, RecoveryApproval):
        raise ApprovalInvalid("approval is missing")
    if current >= approval.expires_at:
        approval.decision = "expired"
        approval.approved = False
        return approval
    if approved is True:
        approval.approved = True
        approval.decision = "approved"
        approval.approved_at = current
        if operator is not None:
            approval.operator = operator
    else:
        approval.approved = False
        approval.decision = "rejected"
    return approval


def consume_approval(approval: RecoveryApproval, now: datetime | None = None) -> None:
    validate_approval(approval, approval.incident_id, now=now)
    approval.used = True
    approval.decision = "consumed"


def validate_disposable_env(env_values: Any = None, path: Any = None) -> dict[str, Any]:
    if env_values is None:
        target = Path(path) if path is not None else Path(RECOVERY_ENV_FILE)
        if not target.exists():
            raise RecoveryBlocked("disposable environment configuration is missing")
        values: dict[str, str] = {}
        try:
            for line in target.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
        except OSError as exc:
            raise RecoveryBlocked(
                "disposable environment configuration is invalid"
            ) from exc
        env_values = values
    if not isinstance(env_values, dict):
        raise RecoveryBlocked("disposable environment configuration is invalid")
    missing = DISPOSABLE_REQUIRED_ENV_KEYS - set(env_values)
    if missing:
        raise RecoveryBlocked("disposable environment configuration is invalid")
    for key in DISPOSABLE_REQUIRED_ENV_KEYS:
        if not str(env_values.get(key, "")).strip():
            raise RecoveryBlocked("disposable environment configuration is invalid")
    for key, expected_port in DISPOSABLE_REQUIRED_PORT_ASSIGNMENTS.items():
        try:
            actual_port = int(str(env_values.get(key, "")).strip())
        except (TypeError, ValueError):
            raise RecoveryBlocked("disposable environment configuration is invalid")
        if actual_port != expected_port:
            raise RecoveryBlocked("disposable environment configuration is invalid")
    return dict(env_values)


def check_host_ports(ports: Any = None, host: str = "127.0.0.1") -> list[int]:
    if ports is None:
        ports = DISPOSABLE_REQUIRED_HOST_PORTS
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            timeout=INSPECTION_TIMEOUT_SECONDS,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not isinstance(result.stdout, str):
            raise ValueError
        occupied = set()
        header_seen = False
        for line in result.stdout.splitlines():
            fields = line.split()
            if not fields:
                continue
            if not header_seen and line.strip().casefold() == "active connections":
                continue
            if not header_seen and [field.casefold() for field in fields] == [
                "proto",
                "local",
                "address",
                "foreign",
                "address",
                "state",
                "pid",
            ]:
                header_seen = True
                continue
            if not header_seen:
                raise ValueError
            protocol = fields[0].upper()
            if (
                protocol not in {"TCP", "UDP"}
                or len(fields) != (5 if protocol == "TCP" else 4)
                or not fields[-1].isascii()
                or not fields[-1].isdigit()
            ):
                raise ValueError
            for index, endpoint in enumerate(fields[1:3]):
                match = re.fullmatch(r"(\[[^\]]+\]|[^:]+):([0-9]+|\*)", endpoint)
                if match is None:
                    raise ValueError
                address, port = match.groups()
                if address == "*":
                    if index == 0:
                        raise ValueError
                else:
                    ip = ipaddress.ip_address(address.strip("[]"))
                    if (ip.version == 6) != address.startswith("["):
                        raise ValueError
                if port != "*" and int(port) > 65535:
                    raise ValueError
            local_match = re.fullmatch(r"(\[[^\]]+\]|[^:]+):([0-9]+)", fields[1])
            if local_match is None:
                raise ValueError
            if protocol == "UDP":
                continue
            state = fields[3].upper()
            if state not in {
                "LISTENING",
                "ESTABLISHED",
                "TIME_WAIT",
                "CLOSE_WAIT",
                "SYN_SENT",
                "SYN_RECEIVED",
                "FIN_WAIT_1",
                "FIN_WAIT_2",
                "CLOSING",
                "LAST_ACK",
                "CLOSED",
                "DELETE_TCB",
            }:
                raise ValueError
            if state == "LISTENING":
                occupied.add(int(local_match.group(2)))
        if not header_seen:
            raise ValueError
        return sorted(set(ports) & occupied)
    except (OSError, subprocess.SubprocessError, ValueError, TypeError) as exc:
        raise RecoveryBlocked("host listener inspection failed") from exc


def host_ports_are_free(ports: Any = None, host: str = "127.0.0.1") -> bool:
    return not check_host_ports(ports, host)


def verify_compose_project_identity(
    actual: Any, expected: str = RECOVERY_PROJECT
) -> bool:
    if actual != expected:
        raise RecoveryBlocked("wrong Compose project identity")
    return True


def inspect_disposable_project() -> dict[str, Any]:
    """Observe the fixed project; this is not authorization to restart it."""

    def run(command: list[str]) -> str:
        try:
            result = subprocess.run(
                command,
                cwd=RECOVERY_WORKING_DIRECTORY,
                timeout=INSPECTION_TIMEOUT_SECONDS,
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0 or not isinstance(result.stdout, str):
                raise RecoveryBlocked("Docker inspection failed")
            return result.stdout
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            raise RecoveryBlocked("Docker inspection failed") from exc

    ids = run(
        [
            "docker",
            "ps",
            "-aq",
            "--no-trunc",
            "--filter",
            f"label=com.docker.compose.project={RECOVERY_PROJECT}",
        ]
    ).splitlines()
    if (
        not ids
        or len(ids) != len(set(ids))
        or any(re.fullmatch(r"[0-9a-f]{64}", item) is None for item in ids)
    ):
        raise RecoveryBlocked("invalid or absent project containers")
    try:
        containers = json.loads(run(["docker", "inspect", *ids]))
        if not isinstance(containers, list) or len(containers) != len(ids):
            raise ValueError
        seen_ids = set()
        seen_services = set()
        running_ports = set()
        for container in containers:
            container_id = container["Id"]
            labels = container["Config"]["Labels"]
            service = labels["com.docker.compose.service"]
            if (
                container_id not in ids
                or container_id in seen_ids
                or labels["com.docker.compose.project"] != RECOVERY_PROJECT
                or service not in EXPECTED_BINDINGS
                or service in seen_services
            ):
                raise ValueError
            seen_ids.add(container_id)
            seen_services.add(service)
            running = container["State"]["Running"]
            if not isinstance(running, bool):
                raise TypeError
            bindings = container["HostConfig"]["PortBindings"]
            expected = EXPECTED_BINDINGS[service]
            expected_bindings = (
                {expected[0]: [{"HostIp": "127.0.0.1", "HostPort": str(expected[1])}]}
                if expected
                else {}
            )
            if bindings is None:
                bindings = {}
            if not isinstance(bindings, dict) or bindings != expected_bindings:
                raise ValueError
            if running and expected:
                running_ports.add(expected[1])
        if "api" not in seen_services:
            raise ValueError
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise RecoveryBlocked("invalid project inspection or port mappings") from exc

    occupied = set(check_host_ports())
    return {
        "api_container_id": next(
            container["Id"]
            for container in containers
            if container["Config"]["Labels"]["com.docker.compose.service"] == "api"
        ),
        "surviving_service_ports": sorted(running_ports),
        "unproven_listener_ports": sorted(occupied & running_ports),
        "conflicting_ports": sorted(occupied - running_ports),
    }


def verify_api_readiness(
    url: str = READY_URL, timeout: float = READY_TIMEOUT_SECONDS
) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return int(getattr(response, "status", 200)) == 200
    except (OSError, TimeoutError, ValueError):
        return False


def verify_prometheus_target(
    url: str = PROMETHEUS_QUERY_URL, timeout: float = PROMETHEUS_TIMEOUT_SECONDS
) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            if response.status != 200:
                return False
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict) or payload.get("status") != "success":
            return False
        data = payload.get("data")
        if not isinstance(data, dict) or data.get("resultType") != "vector":
            return False
        results = data.get("result")
        if not isinstance(results, list):
            return False
        target_up = False
        for item in results:
            if not isinstance(item, dict):
                return False
            labels, value = item.get("metric"), item.get("value")
            if (
                not isinstance(labels, dict)
                or not isinstance(labels.get("job"), str)
                or not isinstance(value, list)
                or len(value) != 2
                or isinstance(value[0], bool)
                or not isinstance(value[0], (int, float))
                or not math.isfinite(value[0])
                or value[1] not in ("0", "1")
            ):
                return False
            if labels["job"] == "api" and value[1] == "1":
                target_up = True
        return target_up
    except (
        OSError,
        TimeoutError,
        ValueError,
        AttributeError,
        TypeError,
        OverflowError,
    ):
        return False


def verify_alert_resolution(
    timeout: float = ALERT_RESOLUTION_TIMEOUT_SECONDS,
    poll_interval: float = ALERT_RESOLUTION_POLL_SECONDS,
    url: str = ALERTS_QUERY_URL,
) -> bool:
    deadline = time.monotonic() + float(timeout)
    while True:
        try:
            with urllib.request.urlopen(url, timeout=5.0) as response:
                if response.status != 200:
                    raise ValueError("unsuccessful Prometheus response")
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict) or payload.get("status") != "success":
                raise ValueError("invalid Prometheus status")
            data = payload.get("data")
            if not isinstance(data, dict) or data.get("resultType") != "vector":
                raise ValueError("invalid Prometheus data")
            results = data.get("result")
            if not isinstance(results, list):
                raise TypeError("invalid Prometheus result")
            active = False
            for item in results:
                if not isinstance(item, dict):
                    raise TypeError("invalid alert sample")
                metric, value = item.get("metric"), item.get("value")
                if (
                    not isinstance(metric, dict)
                    or not isinstance(metric.get("alertname"), str)
                    or metric.get("alertstate") not in ("pending", "firing")
                    or not isinstance(value, list)
                    or len(value) != 2
                    or isinstance(value[0], bool)
                    or not isinstance(value[0], (int, float))
                    or not math.isfinite(value[0])
                    or value[1] not in ("0", "1")
                ):
                    raise ValueError("invalid alert sample")
                if (
                    metric["alertname"] == "BenchScopeApiUnavailable"
                    and value[1] == "1"
                ):
                    active = True
            if not active:
                return True
        except (
            OSError,
            TimeoutError,
            ValueError,
            AttributeError,
            TypeError,
            OverflowError,
        ):
            pass
        if time.monotonic() >= deadline:
            return False
        time.sleep(max(0.0, float(poll_interval)))


def verify_synthetic_run_persisted(expected: Any, actual: Any) -> bool:
    return expected is not None and actual is not None and expected == actual


def run_recovery_smoke_test(
    executor: Any = subprocess.run,
    command: tuple[str, ...] = RECOVERY_SMOKE_TEST_COMMAND,
    cwd: Path = RECOVERY_SMOKE_TEST_WORKING_DIRECTORY,
    timeout: int = RECOVERY_SMOKE_TEST_TIMEOUT_SECONDS,
) -> Any:
    try:
        result = executor(
            list(command),
            cwd=cwd,
            timeout=timeout,
            check=False,
            capture_output=True,
            text=True,
        )
        return result
    except (OSError, subprocess.SubprocessError, ValueError):
        return subprocess.CompletedProcess(list(command), 1)


def verify_recovery(
    *,
    api_readiness: bool | None = None,
    prometheus_target: bool | None = None,
    alert_resolved: bool | None = None,
    persistence: bool | None = None,
    smoke_test: bool | None = None,
) -> RecoveryVerificationResult:
    checks = {
        "api_readiness": (
            verify_api_readiness() is True
            if api_readiness is None
            else api_readiness is True
        ),
        "prometheus_target": (
            verify_prometheus_target() is True
            if prometheus_target is None
            else prometheus_target is True
        ),
        "alert_resolution": (
            (alert_resolved is None or alert_resolved is True)
            and verify_alert_resolution(timeout=0, poll_interval=0) is True
        ),
        "persistence": persistence is True,
        "recovery_smoke_test": smoke_test is True,
    }
    return RecoveryVerificationResult(checks=checks)


def create_audit_record(
    *,
    incident_id: Any,
    alert_reference: Any = None,
    investigation_reference: Any = None,
    approval: RecoveryApproval | None = None,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
    outcome: str = "unknown",
    verification: dict[str, Any] | None = None,
    final_state: str = "escalated",
) -> dict[str, Any]:
    approval_payload = {}
    if approval is not None:
        approval_payload = {
            "approval_id": approval.approval_id,
            "incident_id": approval.incident_id,
            "approved": approval.approved,
            "decision": approval.decision,
            "approved_at": _iso(approval.approved_at),
            "expires_at": _iso(approval.expires_at),
            "used": approval.used,
        }
    record = RecoveryAuditRecord(
        incident_id=str(incident_id),
        alert_reference=alert_reference,
        investigation_reference=investigation_reference,
        approval=_redact(approval_payload),
        action=list(RECOVERY_COMMAND),
        project=RECOVERY_PROJECT,
        service=RECOVERY_SERVICE,
        working_directory=str(RECOVERY_WORKING_DIRECTORY),
        started_at=_iso(started_at),
        ended_at=_iso(ended_at),
        outcome=outcome,
        verification=_redact(verification or {}),
        final_state=final_state,
    )
    return record.to_dict()


def execute_fixed_recovery(
    *,
    approval: Any,
    incident_id: Any = None,
    executor: Any = subprocess.run,
    env_config: Any = None,
    env_path: Any = None,
    project_identity: Any = None,
    ports: Any = None,
    now: datetime | None = None,
    session: Session | None = None,
) -> dict[str, Any]:
    current = now or _now()
    target_incident = (
        incident_id
        if incident_id is not None
        else getattr(approval, "incident_id", None)
    )
    if getattr(approval, "attempted", False):
        raise RecoveryBlocked("recovery has already been attempted")

    validate_approval(
        approval,
        target_incident,
        action=RECOVERY_COMMAND,
        project=RECOVERY_PROJECT,
        service=RECOVERY_SERVICE,
        working_directory=RECOVERY_WORKING_DIRECTORY,
        now=current,
    )
    validate_disposable_env(env_config, env_path)
    observation = inspect_disposable_project()
    if observation["conflicting_ports"]:
        raise RecoveryBlocked("required host ports have conflicts")
    if observation["unproven_listener_ports"]:
        raise RecoveryBlocked("surviving service listener ownership is unproven")
    raise RecoveryBlocked("recovery execution disabled: race-safe ownership unproven")


def recover_incident(
    session: Session,
    record_id: Any,
    approval: Any,
    *,
    executor: Any = subprocess.run,
    env_config: Any = None,
    env_path: Any = None,
    project_identity: Any = None,
    ports: Any = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    return execute_fixed_recovery(
        approval=approval,
        incident_id=record_id,
        executor=executor,
        env_config=env_config,
        env_path=env_path,
        project_identity=project_identity,
        ports=ports,
        now=now,
        session=session,
    )


def recover_and_store(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return recover_incident(*args, **kwargs)


def execute_recovery(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return execute_fixed_recovery(*args, **kwargs)


Approval = RecoveryApproval
ApprovalInvalidError = ApprovalInvalid
RecoverySupervisor = execute_fixed_recovery
request_approval = request_recovery_approval
approve_approval = approve_recovery_approval
approve = approve_recovery_approval
consume = consume_approval
check_ports = check_host_ports
ports_are_free = host_ports_are_free
verify_project = verify_compose_project_identity
verify_readiness = verify_api_readiness
verify_prometheus = verify_prometheus_target
verify_alert = verify_alert_resolution
create_audit = create_audit_record
redact_audit = redact
FIXED_RECOVERY_COMMAND = RECOVERY_COMMAND
RECOVERY_ARGV = RECOVERY_COMMAND
RECOVERY_ARGS = RECOVERY_COMMAND
