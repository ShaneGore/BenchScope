import json
import os
import subprocess
from dataclasses import replace
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from alembic import command
from app import incident_investigation as investigation
from app.models import Base, IncidentRecord


def test_incident_migration_revisions_fit_postgres_version_column_offline(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)
    context = MigrationContext.configure(
        url="postgresql://", opts={"as_sql": True, "output_buffer": StringIO()}
    )
    version_table = context.impl.version_table_impl(
        version_table="alembic_version",
        version_table_schema=None,
        version_table_pk=True,
    )
    capacity = version_table.c.version_num.type.length
    assert capacity == 32
    assert all(
        len(revision.revision) <= capacity for revision in scripts.walk_revisions()
    )
    assert scripts.get_current_head() == "0005_incident_summary"

    upgrade = StringIO()
    config.output_buffer = upgrade
    command.upgrade(config, "head", sql=True)
    assert "VARCHAR(32)" in upgrade.getvalue()
    assert "ADD COLUMN investigation_summary TEXT" in upgrade.getvalue()
    assert "'0005_incident_summary'" in upgrade.getvalue()

    downgrade = StringIO()
    config.output_buffer = downgrade
    command.downgrade(config, "head:0004_incident_records", sql=True)
    assert "DROP COLUMN investigation_summary" in downgrade.getvalue()
    assert "'0004_incident_records'" in downgrade.getvalue()


def _usage():
    return investigation.CopilotUsage("gpt-6-luna", 1, 1, 87207000, 15005, 75)


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
            "gpt-6-luna", "gpt-6-luna", "API returned 503 responses.", _usage()
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
        b'{"type":"assistant.message","data":{"content":"unsafe","model":"gpt-6-luna","serverTools":[{"name":"shell"}]}}',
        b'{"type":"tool.execution_start"}',
        b'{"type":null}',
        b'{"data":{}}',
        b'{"type":"model.call_start","type":"assistant.message"}',
    ],
)
def test_cli_event_parser_rejects_malformed_tool_or_model_events(raw):
    with pytest.raises(investigation.InvestigationRejected):
        investigation._parse_cli_events(raw)


def test_cli_event_parser_reads_selected_and_effective_model_metadata():
    events = [
        {"type": "model.call_start", "data": {"model": "gpt-6-luna"}},
        {
            "type": "assistant.message",
            "data": {
                "content": "Summary.",
                "model": "gpt-6-luna",
                "serverTools": [],
                "toolRequests": [],
            },
        },
        {"type": "model.call_final_result", "data": {"model": "gpt-6-luna"}},
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
                "data": {
                    "content": "Summary.",
                    "model": "gpt-6-luna",
                    "serverTools": [],
                },
            }
        ],
        [
            {"type": "model.call_start", "data": {"model": "unknown"}},
            {
                "type": "assistant.message",
                "data": {
                    "content": "Summary.",
                    "model": "gpt-6-luna",
                    "serverTools": [],
                },
            },
            {"type": "model.call_final_result", "data": {"model": "gpt-6-luna"}},
        ],
        [
            {"type": "model.call_start", "data": {"model": "gpt-6-luna"}},
            {
                "type": "assistant.message",
                "data": {
                    "content": "Summary.",
                    "model": "unknown",
                    "serverTools": [],
                },
            },
            {"type": "model.call_final_result", "data": {"model": "gpt-6-luna"}},
        ],
        [
            {"type": "model.call_start", "data": {"model": "gpt-6-luna"}},
            {
                "type": "assistant.message",
                "data": {
                    "content": "Summary.",
                    "model": "gpt-6-luna",
                    "serverTools": [],
                },
            },
            {"type": "model.call_final_result", "data": {"model": "unknown"}},
        ],
        [
            {"type": "model.call_start", "data": {"model": "gpt-6-luna"}},
            {
                "type": "assistant.message",
                "data": {
                    "content": "Summary.",
                    "model": "gpt-6-luna",
                    "serverTools": [],
                },
            },
        ],
    ],
)
def test_cli_event_parser_requires_explicit_matching_model_metadata(events):
    raw = "\n".join(json.dumps(event) for event in events).encode()
    with pytest.raises(investigation.InvestigationRejected, match="model"):
        investigation._parse_cli_events(raw)


@pytest.mark.parametrize("tool_requests", [None, "", {}, False, [None]])
def test_cli_event_parser_rejects_malformed_or_nonempty_tool_requests(tool_requests):
    events = [
        {"type": "model.call_start", "data": {"model": "gpt-6-luna"}},
        {
            "type": "assistant.message",
            "data": {
                "model": "gpt-6-luna",
                "content": "Summary.",
                "serverTools": [],
                "toolRequests": tool_requests,
            },
        },
        {"type": "model.call_final_result", "data": {"model": "gpt-6-luna"}},
    ]
    with pytest.raises(investigation.InvestigationRejected, match="unsafe"):
        investigation._parse_cli_events(
            "\n".join(json.dumps(event) for event in events).encode()
        )


@pytest.mark.parametrize("server_tools", [None, "", {}, False, ["read_file"]])
def test_cli_event_parser_requires_empty_server_tool_list(server_tools):
    raw = json.dumps(
        {
            "type": "assistant.message",
            "data": {
                "model": "gpt-6-luna",
                "content": "Summary.",
                "serverTools": server_tools,
            },
        }
    ).encode()
    with pytest.raises(investigation.InvestigationRejected, match="exposed tools"):
        investigation._parse_cli_events(raw)


def test_cli_event_parser_distinguishes_selected_and_effective_model_errors():
    message = {
        "type": "assistant.message",
        "data": {"model": "gpt-6-luna", "content": "ok", "serverTools": []},
    }
    events = [
        {"type": "model.call_start", "data": {"model": "other"}},
        message,
        {"type": "model.call_final_result", "data": {"model": "gpt-6-luna"}},
    ]
    with pytest.raises(investigation.InvestigationRejected, match="selected model"):
        investigation._parse_cli_events(
            "\n".join(json.dumps(event) for event in events).encode()
        )
    events[0]["data"]["model"] = "gpt-6-luna"
    events[2]["data"]["model"] = "other"
    with pytest.raises(investigation.InvestigationRejected, match="effective model"):
        investigation._parse_cli_events(
            "\n".join(json.dumps(event) for event in events).encode()
        )


def test_copilot_cli_preflight_never_promotes_help_token_or_opt_in_to_proof(
    monkeypatch,
):
    calls = []
    output_limits = []
    help_output = (
        b"--model --available-tools --disable-builtin-mcps "
        b"--no-custom-instructions --no-ask-user --max-ai-credits "
        b"--output-format --prompt --secret-env-vars --sync-session "
        b"--usage-output-file"
    )

    def fake_run(args, cwd, timeout, output_limit):
        calls.append(args)
        output_limits.append(output_limit)
        if "--help" in args:
            return help_output, b""
        if "permissions" in args:
            return (
                b"--available-tools do not expose tools filtered\n  out by the list",
                b"",
            )
        return b"GitHub Copilot CLI 1.0.81", b""

    monkeypatch.setattr(investigation, "_run_cli_process", fake_run)
    monkeypatch.setenv("GH_TOKEN", "arbitrary-token-not-entitlement")
    provider = investigation.CopilotCLIProvider("copilot", costs_authorized=True)
    result = provider.verify_capabilities()

    assert result.model_flag_accepted
    assert result.empty_tool_allowlist_argument_accepted
    assert result.tool_controls_documented
    assert not result.tool_restrictions_verified
    assert not result.existing_auth_credential_available
    assert not result.usage_cost_authorized
    assert not result.permits_invocation
    assert result.blocker == investigation.CLI_INVOCATION_BLOCKER
    with pytest.raises(investigation.InvestigationBlocked, match="entitlement"):
        provider.invoke("anything")
    assert len(calls) == 3
    assert calls[0][1:] == [
        "--model=gpt-6-luna",
        "--help",
    ]
    assert calls[1][1:] == [
        "--model=gpt-6-luna",
        "help",
        "permissions",
    ]
    version_args = calls[2][1:]
    assert version_args[:6] == [
        "--model=gpt-6-luna",
        "--available-tools=",
        "--disable-builtin-mcps",
        "--no-custom-instructions",
        "--no-ask-user",
        "--max-ai-credits=30",
    ]
    assert version_args[6].startswith("--usage-output-file=")
    assert version_args[7:] == [
        "--secret-env-vars=GH_TOKEN,COPILOT_GITHUB_TOKEN,GITHUB_TOKEN",
        "--sync-session=off",
        "--output-format=json",
        "--version",
    ]
    assert all(sum(arg.startswith("--model=") for arg in args) == 1 for args in calls)
    assert all("--allow-all-tools" not in args for args in calls)
    assert output_limits == [investigation.CLI_PREFLIGHT_OUTPUT_LIMIT_BYTES] * 3


def test_copilot_cli_preflight_requires_successful_empty_allowlist_parse(monkeypatch):
    calls = []

    def fake_run(args, cwd, timeout, output_limit):
        calls.append(args)
        if "--help" in args:
            help_output = (
                b"--model --available-tools --disable-builtin-mcps "
                b"--no-custom-instructions --no-ask-user --max-ai-credits "
                b"--output-format --prompt --secret-env-vars --sync-session "
                b"--usage-output-file"
            )
            return help_output, b""
        if "permissions" in args:
            return (
                b"--available-tools do not expose tools filtered out by the list",
                b"",
            )
        raise investigation.InvestigationBlocked("CLI exited unsuccessfully")

    monkeypatch.setattr(investigation, "_run_cli_process", fake_run)
    result = investigation.CopilotCLIProvider("copilot").verify_capabilities()

    assert not result.model_flag_accepted
    assert not result.empty_tool_allowlist_argument_accepted
    assert not result.permits_invocation
    assert result.blocker == investigation.CLI_PREFLIGHT_BLOCKER
    assert len(calls) == 3


def test_copilot_cli_preflight_fails_closed_when_help_lacks_required_flags(
    monkeypatch,
):
    calls = []

    def fake_run(args, cwd, timeout, output_limit):
        calls.append(args)
        return b"--model", b""

    monkeypatch.setattr(investigation, "_run_cli_process", fake_run)
    result = investigation.CopilotCLIProvider("copilot").verify_capabilities()

    assert not result.model_flag_accepted
    assert not result.empty_tool_allowlist_argument_accepted
    assert not result.permits_invocation
    assert result.blocker == investigation.CLI_PREFLIGHT_BLOCKER
    assert len(calls) == 1


def test_copilot_cli_args_use_pinned_model_empty_tools_and_usage_capture(tmp_path):
    shim = tmp_path / "copilot.ps1"
    shim.touch()

    args = investigation._build_cli_args(
        str(shim), "sanitized prompt", tmp_path / "usage.json"
    )

    if os.name == "nt":
        assert "powershell.exe" in args[0].lower()
        assert args[1:7] == [
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(shim),
        ]
        cli_args = args[7:]
    else:
        assert args[0] == str(shim)
        cli_args = args[1:]
    assert cli_args[:2] == ["--model=gpt-6-luna", "--prompt"]
    assert cli_args[2] == "sanitized prompt"
    assert cli_args[3:] == [
        "--output-format=json",
        "--available-tools=",
        "--disable-builtin-mcps",
        "--no-custom-instructions",
        "--no-ask-user",
        "--max-ai-credits=30",
        f"--usage-output-file={tmp_path / 'usage.json'}",
        "--secret-env-vars=GH_TOKEN,COPILOT_GITHUB_TOKEN,GITHUB_TOKEN",
        "--sync-session=off",
    ]


def test_cli_usage_parser_accepts_only_one_verified_luna_request(tmp_path):
    usage_file = tmp_path / "usage.json"
    usage_file.write_text(
        json.dumps(
            {
                "currentModel": "gpt-6-luna",
                "totalUserRequests": 1,
                "totalPremiumRequestCost": 1,
                "totalNanoAiu": 87207000,
                "lastCallInputTokens": 15005,
                "lastCallOutputTokens": 75,
            }
        ),
        encoding="utf-8",
    )

    usage = investigation._parse_cli_usage(usage_file)

    assert usage.current_model == "gpt-6-luna"
    assert usage.total_user_requests == 1
    assert usage.total_premium_request_cost == 1
    assert usage.total_nano_aiu == 87207000
    assert usage.last_call_input_tokens == 15005
    assert usage.last_call_output_tokens == 75


@pytest.mark.parametrize(
    "value",
    [
        {
            "currentModel": "other",
            "totalUserRequests": 1,
            "totalPremiumRequestCost": 1,
            "totalNanoAiu": 1,
            "lastCallInputTokens": 1,
            "lastCallOutputTokens": 1,
        },
        {
            "currentModel": "gpt-6-luna",
            "totalUserRequests": 2,
            "totalPremiumRequestCost": 1,
            "totalNanoAiu": 1,
            "lastCallInputTokens": 1,
            "lastCallOutputTokens": 1,
        },
        {
            "currentModel": "gpt-6-luna",
            "totalUserRequests": 1,
            "totalPremiumRequestCost": 0,
            "totalNanoAiu": 0,
            "lastCallInputTokens": 1,
            "lastCallOutputTokens": 1,
        },
        {
            "currentModel": "gpt-6-luna",
            "totalUserRequests": True,
            "totalPremiumRequestCost": 1,
            "totalNanoAiu": 1,
            "lastCallInputTokens": 1,
            "lastCallOutputTokens": 1,
        },
    ],
)
def test_cli_usage_parser_rejects_mismatched_or_unverified_usage(tmp_path, value):
    usage_file = tmp_path / "usage.json"
    usage_file.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(investigation.InvestigationRejected, match="usage"):
        investigation._parse_cli_usage(usage_file)


def test_cli_usage_parser_rejects_oversized_usage_file(tmp_path):
    usage_file = tmp_path / "usage.json"
    usage_file.write_bytes(b" " * (investigation.CLI_PREFLIGHT_OUTPUT_LIMIT_BYTES + 1))

    with pytest.raises(investigation.InvestigationRejected, match="exceeded its limit"):
        investigation._parse_cli_usage(usage_file)


def test_cli_usage_parser_rejects_missing_file(tmp_path):
    with pytest.raises(investigation.InvestigationRejected, match="usage"):
        investigation._parse_cli_usage(tmp_path / "missing-usage.json")


def test_direct_cli_call_requires_verified_capabilities_and_sanitized_prompt(
    monkeypatch,
):
    calls = []

    def fake_run(args, cwd, timeout, output_limit=investigation.CLI_OUTPUT_LIMIT_BYTES):
        calls.append(args)
        return b"", b""

    monkeypatch.setattr(investigation, "_run_cli_process", fake_run)
    provider = investigation.CopilotCLIProvider("copilot")
    with pytest.raises(investigation.InvestigationBlocked):
        provider.invoke("SYNTHETIC_SECRET_SENTINEL")
    assert not provider.verify_capabilities().permits_invocation
    provider._verified = True  # A stale or forged flag must not bypass the gate.
    with pytest.raises(investigation.InvestigationBlocked):
        provider.invoke("SYNTHETIC_SECRET_SENTINEL")
    assert calls == [["copilot", "--model=gpt-6-luna", "--help"]]


def test_real_provider_blocked_without_storing_summary(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'blocked.sqlite'}")
    Base.metadata.create_all(engine)
    calls = []

    def fake_run(args, cwd, timeout, output_limit):
        calls.append(args)
        return b"--model", b""

    monkeypatch.setattr(investigation, "_run_cli_process", fake_run)
    monkeypatch.setenv("GH_TOKEN", "arbitrary-token")
    with Session(engine) as session:
        record = _database_record(session)
        provider = investigation.CopilotCLIProvider("copilot", costs_authorized=True)
        with pytest.raises(investigation.InvestigationBlocked):
            investigation.investigate_and_store(session, record.id, provider)
        session.refresh(record)
        assert record.investigation_summary is None
    engine.dispose()
    assert all(
        "--prompt" not in args and "--allow-all-tools" not in args for args in calls
    )


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


@pytest.mark.parametrize(
    "usage",
    [
        None,
        {},
        replace(_usage(), current_model="other"),
        replace(_usage(), total_user_requests=True),
        replace(_usage(), total_user_requests=2),
        replace(_usage(), total_premium_request_cost=True),
        replace(_usage(), total_premium_request_cost=float("nan")),
        replace(_usage(), total_premium_request_cost=0, total_nano_aiu=0),
        replace(_usage(), last_call_input_tokens=True),
        replace(_usage(), last_call_input_tokens=0),
        replace(_usage(), last_call_output_tokens=-1),
    ],
)
def test_missing_or_invalid_usage_is_not_stored(tmp_path, usage):
    engine = create_engine(f"sqlite:///{tmp_path / 'invalid-usage.sqlite'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        record = _database_record(session)
        provider = FakeProvider(
            investigation.ProviderResponse("gpt-6-luna", "gpt-6-luna", "ok", usage)
        )
        with pytest.raises(investigation.InvestigationRejected, match="usage"):
            investigation.investigate_and_store(session, record.id, provider)
        session.refresh(record)
        assert record.investigation_summary is None
    engine.dispose()


@pytest.mark.parametrize("platform", ["posix", "nt", "unsupported"])
def test_process_creation_is_blocked_on_all_platforms(tmp_path, monkeypatch, platform):
    def forbidden(*args, **kwargs):
        pytest.fail("subprocess creation must not be attempted")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "name", platform)
    with pytest.raises(investigation.InvestigationBlocked, match="process"):
        investigation._run_cli_process(["unused"], tmp_path, timeout=60)


def test_real_preflight_reports_process_blocker_without_starting_cli(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("subprocess creation must not be attempted")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    provider = investigation.CopilotCLIProvider("copilot", costs_authorized=True)
    result = provider.verify_capabilities()
    assert not result.permits_invocation
    assert result.blocker == investigation.CLI_PROCESS_BLOCKER
    with pytest.raises(investigation.InvestigationBlocked):
        provider.invoke("unused")


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
