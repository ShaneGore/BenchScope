from sqlalchemy.orm import Session

from app.models import IncidentAuditEvent

_ALLOWED_EVENTS = {
    ("alert_received", "accepted", "authenticated_firing_alert"),
    ("alert_resolved", "accepted", "resolved_notification"),
    ("evidence_collected", "complete", "sources_complete"),
    ("evidence_collected", "partial", "source_failure"),
    ("evidence_collected", "failed", "sources_unavailable"),
    ("investigation_dispatch", "blocked", "model_runtime_unverified"),
    ("recovery_attempt", "blocked", "recovery_safety_gate"),
    ("recovery_attempt", "rejected", "approval_invalid"),
}


def append_incident_audit_event(
    session: Session,
    incident_id,
    *,
    event_type: str,
    outcome: str,
    reason_code: str,
) -> None:
    if (event_type, outcome, reason_code) not in _ALLOWED_EVENTS:
        raise ValueError("invalid incident audit event")
    session.add(
        IncidentAuditEvent(
            incident_id=incident_id,
            event_type=event_type,
            outcome=outcome,
            reason_code=reason_code,
        )
    )
