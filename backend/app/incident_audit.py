from sqlalchemy.orm import Session

from app.models import IncidentAuditEvent

_ALLOWED_EVENTS = {
    ("alert_received", "accepted", "authenticated_firing_alert"),
    ("alert_resolved", "accepted", "resolved_notification"),
    ("evidence_collected", "complete", "sources_complete"),
    ("evidence_collected", "partial", "source_failure"),
    ("evidence_collected", "failed", "sources_unavailable"),
    ("investigation_dispatch", "blocked", "model_runtime_unverified"),
    ("investigation_dispatch", "accepted", "repair_job_queued"),
    ("investigation_dispatch", "blocked", "evidence_incomplete"),
    ("investigation_dispatch", "blocked", "application_revision_unavailable"),
    ("investigation_dispatch", "blocked", "fingerprint_already_active"),
    ("investigation_dispatch", "blocked", "alert_not_supported"),
    ("repair_dispatch", "accepted", "sanitized_evidence_ready"),
    ("repair_dispatch", "blocked", "evidence_incomplete"),
    ("repair_dispatch", "blocked", "application_revision_unavailable"),
    ("repair_dispatch", "blocked", "fingerprint_already_active"),
    ("repair_dispatch", "blocked", "alert_not_supported"),
    ("repair_attempt", "accepted", "repair_started"),
    ("repair_attempt", "complete", "patch_validated"),
    ("repair_attempt", "complete", "copilot_patch_validated"),
    ("repair_attempt", "complete", "tests_passed"),
    ("repair_attempt", "failed", "investigation_failed"),
    ("repair_attempt", "failed", "patch_rejected"),
    ("repair_attempt", "failed", "tests_failed"),
    ("repair_attempt", "failed", "pull_request_failed"),
    ("repair_attempt", "failed", "github_permissions_unverified"),
    ("repair_attempt", "blocked", "runtime_unverified"),
    ("repair_pull_request", "accepted", "human_review_required"),
    ("repair_pull_request", "failed", "pull_request_failed"),
    ("repair_ci", "complete", "checks_passed"),
    ("repair_ci", "failed", "checks_failed"),
    ("repair_ci", "partial", "checks_timed_out"),
    ("repair_release_check", "complete", "issue_resolved"),
    ("repair_release_check", "failed", "issue_persists"),
    ("repair_release_check", "blocked", "awaiting_human_merge"),
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
