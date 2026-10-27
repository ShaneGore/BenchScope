from pathlib import Path

CONTRACT = Path(__file__).resolve().parents[2] / "openapi.yaml"


def test_contract_artifact_exists() -> None:
    assert CONTRACT.is_file()


def test_contract_declares_bearer_auth() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    assert "bearerAuth" in text
    assert "scheme: bearer" in text


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
