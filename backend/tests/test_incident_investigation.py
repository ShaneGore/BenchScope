import json
import os
import sys
import time
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app import incident_investigation as investigation
from app.models import Base, IncidentRecord
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def _evidence(status="complete"):
    return {
        "status": status,
        "collected_at": "2026-10-28T00:00:00Z",
        "lookback_seconds": 300,
        "prometheus": {
            "status": "ok",
            "api_status": "ok",
            "http_responses_status": "ok",
            "api": "down",
            "http_responses": [{"status_code": "503", "count": 2.0}],
        },
        "logs": {"status": "ok", "entries": [{"timestamp": "2026-10-28T00:00:00Z"}]},
        "traces": {
            "status": "ok",
            "traces": [
                {
                    "started_at": "2026-10-28T00:00:00Z",
                    "duration_ms": 12.5,
                    "span_count": 1,
                    "spans": [
                        {
                            "started_at": "2026-10-28T00:00:00Z",
                            "duration_ms": 1.5,
                        }
                    ],
                }
            ],
        },
        "truncated": {"logs": False, "traces": False, "spans": False},
    }


def _partial_evidence():
    evidence = _evidence("partial")
    evidence["prometheus"] = {
        "status": "partial",
        "api_status": "ok",
        "http_responses_status": "failed",
        "api": "down",
    }
    evidence["logs"] = {"status": "timeout"}
    return evidence


def _record(evidence=None, status="complete"):
    return SimpleNamespace(
        evidence=evidence if evidence is not None else _evidence(status),
        evidence_status=status,
        investigation_summary=None,
        alert_name="SYNTHETIC_PRIVATE_PROMPT_SENTINEL",
        fingerprint="SYNTHETIC_OWNER_ID_SENTINEL",
        owner_id="SYNTHETIC_OWNER_ID_SENTINEL",
        secret="SYNTHETIC_SECRET_SENTINEL",
        raw_telemetry="SYNTHETIC_PRIVATE_OUTPUT_SENTINEL",
    )


class FakeProvider:
    def __init__(self, response=None, capabilities=None):
        self.response = response or investigation.ProviderResponse(
            "gpt-6-luna", "gpt-6-luna", "API returned 503 responses."
        )
        self.capabilities = capabilities or investigation.CapabilityVerification(
            True, True, True, True
        )
        self.prompt = None
        self.invocations = 0

    def verify_capabilities(self):
        return self.capabilities

    def invoke(self, prompt):
        self.invocations += 1
        self.prompt = prompt
        return self.response


def test_complete_and_partial_stage1_records_send_only_sanitized_evidence():
    for record in (_record(), _record(_partial_evidence(), "partial")):
        provider = FakeProvider()
        assert investigation.investigate_record(record, provider) == (
            "API returned 503 responses."
        )
        request = json.loads(provider.prompt.splitlines()[-1])
        assert set(request) == {"evidence", "completion_status", "truncated"}
        assert request["completion_status"] == record.evidence_status
        assert request["truncated"] == record.evidence["truncated"]
        assert all(
            sentinel not in provider.prompt
            for sentinel in (
                "SYNTHETIC_PRIVATE_PROMPT_SENTINEL",
                "SYNTHETIC_OWNER_ID_SENTINEL",
                "SYNTHETIC_SECRET_SENTINEL",
                "SYNTHETIC_PRIVATE_OUTPUT_SENTINEL",
            )
        )


@pytest.mark.parametrize(
    ("record", "error"),
    [
        (_record(_evidence("failed"), "failed"), investigation.InvestigationRejected),
        (_record(_evidence(), "partial"), investigation.InvestigationRejected),
        (
            _record({"status": "complete"}, "complete"),
            investigation.InvestigationRejected,
        ),
    ],
)
def test_rejects_failed_malformed_or_non_stage1_evidence(record, error):
    provider = FakeProvider()
    with pytest.raises(error):
        investigation.investigate_record(record, provider)
    assert provider.invocations == 0


def test_rejects_oversized_evidence_before_provider_use():
    evidence = _evidence()
    evidence["prometheus"]["http_responses"] = [
        {"status_code": "503", "count": 1} for _ in range(5000)
    ]
    provider = FakeProvider()
    with pytest.raises(investigation.InvestigationRejected, match="64 KiB"):
        investigation.investigate_record(_record(evidence), provider)
    assert provider.invocations == 0


@pytest.mark.parametrize(
    "capabilities",
    [
        investigation.CapabilityVerification(False, True, True, True),
        investigation.CapabilityVerification(True, False, True, True),
        investigation.CapabilityVerification(True, True, False, True),
        investigation.CapabilityVerification(True, True, True, False),
    ],
)
def test_capability_failure_blocks_without_invoking(capabilities):
    provider = FakeProvider(capabilities=capabilities)
    with pytest.raises(investigation.InvestigationBlocked):
        investigation.investigate_record(_record(), provider)
    assert provider.invocations == 0


@pytest.mark.parametrize(
    "response",
    [
        investigation.ProviderResponse("other", "gpt-6-luna", "summary"),
        investigation.ProviderResponse("gpt-6-luna", "other", "summary"),
        investigation.ProviderResponse("gpt-6-luna", None, "summary"),
    ],
)
def test_model_mismatch_or_unavailable_identity_fails_closed(response):
    provider = FakeProvider(response=response)
    with pytest.raises(investigation.InvestigationRejected, match="model"):
        investigation.investigate_record(_record(), provider)


@pytest.mark.parametrize(
    "summary",
    [
        None,
        "",
        " \n ",
        "x" * (investigation.SUMMARY_LIMIT_BYTES + 1),
        "🙂" * 1025,
        "contains SYNTHETIC_OWNER_ID_SENTINEL",
        "contains SYNTHETIC_PRIVATE_OUTPUT_SENTINEL",
        "bad\x00control",
        "\ud800",
    ],
)
def test_rejects_empty_malformed_oversized_or_sentinel_output(summary):
    provider = FakeProvider(
        investigation.ProviderResponse("gpt-6-luna", "gpt-6-luna", summary)
    )
    with pytest.raises(investigation.InvestigationRejected):
        investigation.investigate_record(_record(), provider)


def test_summary_utf8_limit_accepts_exact_boundary():
    summary = "é" * (investigation.SUMMARY_LIMIT_BYTES // 2)
    assert investigation._validate_summary(summary) == summary


def test_input_with_sentinel_is_rejected_not_forwarded():
    evidence = _evidence()
    evidence["unexpected"] = "SYNTHETIC_PRIVATE_PROMPT_SENTINEL"
    provider = FakeProvider()
    with pytest.raises(investigation.InvestigationRejected):
        investigation.investigate_record(_record(evidence), provider)
    assert provider.invocations == 0


@pytest.mark.parametrize(
    "raw",
    [
        b"not-json",
        b'{"type":"assistant.message","data":{"content":"ok","model":"other"}}',
        b'{"type":"assistant.message","data":{"content":"unsafe","model":"gpt-6-luna","toolRequests":[{"name":"shell"}]}}',
        b'{"type":"tool.execution_start"}',
    ],
)
def test_cli_event_parser_rejects_malformed_tool_or_model_events(raw):
    with pytest.raises(investigation.InvestigationRejected):
        investigation._parse_cli_events(raw)


def test_cli_event_parser_reads_selected_and_effective_model_metadata():
    events = [
        {"type": "session.start", "data": {"model": "gpt-6-luna"}},
        {
            "type": "assistant.message",
            "data": {"content": "Summary.", "model": "gpt-6-luna"},
        },
    ]
    result = investigation._parse_cli_events(
        "\n".join(json.dumps(event) for event in events).encode()
    )
    assert result.selected_model == "gpt-6-luna"
    assert result.effective_model == "gpt-6-luna"
    assert result.summary == "Summary."


@pytest.mark.parametrize(
    "events",
    [
        [
            {
                "type": "assistant.message",
                "data": {"content": "Summary.", "model": "gpt-6-luna"},
            }
        ],
        [
            {"type": "session.start", "data": {"model": "unknown"}},
            {
                "type": "assistant.message",
                "data": {"content": "Summary.", "model": "gpt-6-luna"},
            },
        ],
        [
            {"type": "session.start", "data": {"model": "gpt-6-luna"}},
            {
                "type": "assistant.message",
                "data": {"content": "Summary.", "model": "unknown"},
            },
        ],
        [
            {"type": "session.start", "data": {"model": "gpt-6-luna"}},
            {
                "type": "assistant.message",
                "data": {"content": "Summary.", "model": "gpt-6-luna"},
            },
            {"type": "session.start", "data": {"model": "gpt-6-luna"}},
        ],
    ],
)
def test_cli_event_parser_requires_explicit_matching_model_metadata(events):
    raw = "\n".join(json.dumps(event) for event in events).encode()
    with pytest.raises(investigation.InvestigationRejected, match="model"):
        investigation._parse_cli_events(raw)


def test_copilot_cli_flags_are_not_proof_of_effective_policy(monkeypatch):
    calls = []

    def fake_run(args, cwd, timeout):
        calls.append(args)
        return (
            (
                b"--model --available-tools=none --deny-tool=* --deny-url=* "
                b"--disable-builtin-mcps"
            ),
            b"",
        )

    monkeypatch.setattr(investigation, "_run_cli_process", fake_run)
    provider = investigation.CopilotCLIProvider("copilot")
    result = provider.verify_capabilities()
    assert not result.permits_invocation
    assert not result.model_flag_accepted
    assert not result.tool_restrictions_verified
    assert not result.existing_entitlement_verified
    assert not result.usage_cost_limit_verified
    assert result.blocker == investigation.CLI_INVOCATION_BLOCKER
    assert calls == []
    with pytest.raises(investigation.InvestigationBlocked, match="disabled"):
        provider.invoke(investigation._make_prompt(_evidence(), "complete"))
    assert calls == []


def test_direct_cli_call_requires_verified_capabilities_and_sanitized_prompt(
    monkeypatch,
):
    calls = []

    def fake_run(args, cwd, timeout):
        calls.append(args)
        return b"", b""

    monkeypatch.setattr(investigation, "_run_cli_process", fake_run)
    provider = investigation.CopilotCLIProvider("copilot")
    with pytest.raises(investigation.InvestigationBlocked):
        provider.invoke("SYNTHETIC_SECRET_SENTINEL")
    assert not provider.verify_capabilities().permits_invocation
    with pytest.raises(investigation.InvestigationBlocked):
        provider.invoke("SYNTHETIC_SECRET_SENTINEL")
    assert calls == []


def test_process_tree_cleanup_removes_descendant_on_normal_completion(tmp_path):
    marker = tmp_path / "child-still-running"
    child_script = (
        "import pathlib,time; time.sleep(.25); "
        f"pathlib.Path({str(marker)!r}).write_text('alive')"
    )
    parent_script = (
        "import subprocess,sys; "
        f"child=subprocess.Popen([sys.executable,'-c',{child_script!r}]); "
        "print(child.pid,flush=True)"
    )
    stdout, _ = investigation._run_cli_process(
        [sys.executable, "-c", parent_script], tmp_path, timeout=5
    )
    assert stdout.decode().strip().isdigit()
    time.sleep(0.3)
    assert not marker.exists()


def test_timeout_cleans_up_controlled_child_process_tree(tmp_path):
    marker = tmp_path / "timeout-child-still-running"
    child_script = (
        "import pathlib,time; time.sleep(.25); "
        f"pathlib.Path({str(marker)!r}).write_text('alive')"
    )
    parent_script = (
        "import subprocess,sys,time; "
        f"subprocess.Popen([sys.executable,'-c',{child_script!r}]); "
        "time.sleep(30)"
    )
    with pytest.raises(TimeoutError):
        investigation._run_cli_process(
            [sys.executable, "-c", parent_script], tmp_path, timeout=0.1
        )
    time.sleep(0.3)
    assert not marker.exists()


def test_force_kills_descendant_that_ignores_graceful_shutdown(tmp_path, monkeypatch):
    marker = tmp_path / "forced-child-still-running"
    if os.name == "nt":
        child_script = (
            "import pathlib,signal,time; signal.signal(signal.SIGBREAK,signal.SIG_IGN); "
            "time.sleep(.25); "
            f"pathlib.Path({str(marker)!r}).write_text('alive')"
        )
    else:
        child_script = (
            "import pathlib,signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); "
            "time.sleep(.25); "
            f"pathlib.Path({str(marker)!r}).write_text('alive')"
        )
    parent_script = (
        "import subprocess,sys,time; "
        f"subprocess.Popen([sys.executable,'-c',{child_script!r}]); "
        "time.sleep(30)"
    )
    monkeypatch.setattr(investigation, "GRACEFUL_SHUTDOWN_SECONDS", 0.1)
    with pytest.raises(TimeoutError):
        investigation._run_cli_process(
            [sys.executable, "-c", parent_script], tmp_path, timeout=0.1
        )
    time.sleep(0.3)
    assert not marker.exists()


def _database_record(session):
    record = IncidentRecord(
        id=uuid4(),
        alert_name="BenchScopeApiUnavailable",
        fingerprint="0123456789abcdef",
        starts_at=datetime(2026, 10, 28, tzinfo=UTC),
        ends_at=datetime(2026, 10, 28, tzinfo=UTC),
        alert_status="firing",
        evidence_status="complete",
        evidence=_evidence(),
        received_at=datetime(2026, 10, 28, tzinfo=UTC),
    )
    session.add(record)
    session.commit()
    return record


def test_successful_investigation_stores_only_bounded_summary(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'incidents-success.sqlite'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        record = _database_record(session)
        provider = FakeProvider()
        assert investigation.investigate_and_store(session, record.id, provider) == (
            "API returned 503 responses."
        )
        session.refresh(record)
        assert record.investigation_summary == "API returned 503 responses."
        assert "SYNTHETIC_" not in record.investigation_summary
    engine.dispose()


def test_failed_investigation_does_not_store_summary_or_log_sentinels(tmp_path, caplog):
    engine = create_engine(f"sqlite:///{tmp_path / 'incidents.sqlite'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        record = _database_record(session)
        provider = FakeProvider(
            investigation.ProviderResponse(
                "gpt-6-luna", "gpt-6-luna", "SYNTHETIC_SECRET_SENTINEL"
            )
        )
        with pytest.raises(investigation.InvestigationRejected):
            investigation.investigate_and_store(session, record.id, provider)
        session.refresh(record)
        assert record.investigation_summary is None
        assert "SYNTHETIC_SECRET_SENTINEL" not in caplog.text
    engine.dispose()
