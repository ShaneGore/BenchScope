from pathlib import Path

CONTRACT = Path(__file__).resolve().parents[2] / "openapi.yaml"


def test_contract_artifact_exists() -> None:
    assert CONTRACT.is_file()


def test_contract_declares_bearer_auth() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    assert "bearerAuth" in text
    assert "scheme: bearer" in text


def test_personal_profile_contract_inherits_bearer_auth_and_documents_401() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    profiles = text.split("  /api/v1/profiles:", 1)[1].split("  /api/v1/runs:", 1)[0]
    assert "security: []" not in profiles
    assert '"401":' in profiles


def test_contract_declares_nullable_metrics() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    assert 'quality_score: { type: [number, "null"], minimum: 0 }' in text
    assert 'ttft_ms: { type: [number, "null"], minimum: 0 }' in text


def test_contract_declares_local_only_benchmark_routes() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    assert "/benchmark/runs:" in text
    assert "x-local-only: true" in text
    assert "Not available in this mode" in text


def test_contract_declares_error_schema() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    assert "ApiError:" in text
    assert "detail:" in text


def test_contract_declares_ownership_friendly_404s() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    assert "Not found" in text


def test_demo_contract_is_anonymous_get_only_and_excludes_personal_fields() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    demo_list = text.split("  /api/v1/demo/runs:", 1)[1].split(
        "  /api/v1/demo/runs/{id}:", 1
    )[0]
    demo_detail = text.split("  /api/v1/demo/runs/{id}:", 1)[1]
    demo_schema = text.split("    DemoRun:", 1)[1].split("    ImportResult:", 1)[0]

    assert "security: []" in demo_list
    assert "security: []" in demo_detail
    assert "\n    post:" not in demo_list
    assert "\n    patch:" not in demo_list
    assert "\n    delete:" not in demo_list
    assert "\n    post:" not in demo_detail
    assert "\n    patch:" not in demo_detail
    assert "\n    delete:" not in demo_detail
    assert "DemoRun" in demo_list and "DemoRun" in demo_detail
    assert "endpoint_url" not in demo_schema
    assert "artifact_ref" not in demo_schema
