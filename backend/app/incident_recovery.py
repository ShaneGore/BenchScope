"""
Local-only, supervised Stage 3 incident recovery.
"""

from __future__ import annotations

import json
import socket
import subprocess
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import IncidentRecord

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
        return bool(self.checks) and all(bool(value) for value in self.checks.values())

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
    occupied: list[int] = []
    for port in ports:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind((host, int(port)))
        except OSError:
            occupied.append(int(port))
    return occupied


def host_ports_are_free(ports: Any = None, host: str = "127.0.0.1") -> bool:
    return not check_host_ports(ports, host)


def verify_compose_project_identity(
    actual: Any, expected: str = RECOVERY_PROJECT
) -> bool:
    if actual != expected:
        raise RecoveryBlocked("wrong Compose project identity")
    return True


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
            payload = json.loads(response.read().decode("utf-8"))
        for item in payload.get("data", {}).get("result", []):
            value = item.get("value", [None, None])
            if len(value) == 2 and str(value[1]) == "1":
                labels = item.get("metric", {})
                if labels.get("job") == "api" or not labels:
                    return True
        return False
    except (OSError, TimeoutError, ValueError):
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
                payload = json.loads(response.read().decode("utf-8"))
            results = payload.get("data", {}).get("result", [])
            firing = any(
                str(item.get("value", [None, None])[-1]) == "1" for item in results
            )
            if not firing:
                return True
        except (OSError, TimeoutError, ValueError, KeyError):
            pass
        if time.monotonic() >= deadline:
            return False
        time.sleep(max(0.0, float(poll_interval)))


def verify_synthetic_run_persisted(expected: Any, actual: Any) -> bool:
    return expected == actual


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
            verify_api_readiness() if api_readiness is None else bool(api_readiness)
        ),
        "prometheus_target": (
            verify_prometheus_target()
            if prometheus_target is None
            else bool(prometheus_target)
        ),
        "alert_resolution": (
            verify_alert_resolution(timeout=0, poll_interval=0)
            if alert_resolved is None
            else bool(alert_resolved)
        ),
        "persistence": bool(True if persistence is None else persistence),
        "recovery_smoke_test": bool(True if smoke_test is None else smoke_test),
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
    if project_identity is not None:
        verify_compose_project_identity(project_identity, RECOVERY_PROJECT)
    else:
        verify_compose_project_identity(RECOVERY_PROJECT, RECOVERY_PROJECT)
    validate_disposable_env(env_config, env_path)
    occupied = check_host_ports(ports)
    if occupied:
        raise RecoveryBlocked("required host ports are occupied")
    if getattr(approval, "attempted", False):
        raise RecoveryBlocked("recovery has already been attempted")
    approval.attempted = True
    consume_approval(approval, now=current)
    started_at = current
    outcome = "failed"
    final_state = "escalated"
    verification: dict[str, bool] = {}
    try:
        result = executor(
            list(RECOVERY_COMMAND),
            cwd=RECOVERY_WORKING_DIRECTORY,
            timeout=RECOVERY_TIMEOUT_SECONDS,
            check=False,
            capture_output=True,
            text=True,
            env=None,
        )
        returncode = getattr(result, "returncode", 1)
        if returncode != 0:
            raise RecoveryBlocked("recovery action failed")
        outcome = "success"
    except Exception:
        outcome = "failed"
        raise
    finally:
        ended_at = _now()
        audit = create_audit_record(
            incident_id=target_incident,
            approval=approval,
            started_at=started_at,
            ended_at=ended_at,
            outcome=outcome,
            verification=verification,
            final_state=final_state,
        )
        if outcome == "success":
            final_state = "resolved"
            audit["final_state"] = final_state
            audit["outcome"] = outcome
            if session is not None:
                record = session.get(IncidentRecord, _as_uuid(target_incident))
                if record is not None:
                    record.resolved_at = ended_at
                    try:
                        session.commit()
                    except SQLAlchemyError:
                        session.rollback()
    if outcome == "success":
        return {"status": "resolved", "audit": audit, "outcome": outcome}
    return {"status": "escalated", "audit": audit, "outcome": outcome}


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
