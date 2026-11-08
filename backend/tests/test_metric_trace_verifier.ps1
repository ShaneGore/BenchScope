$ErrorActionPreference = "Stop"
. "$PSScriptRoot\..\scripts\verify_metric_trace.ps1" -LibraryOnly
$verifierSource = Get-Content -LiteralPath (Join-Path $PSScriptRoot "..\scripts\verify_metric_trace.ps1") -Raw

function Assert($condition, $message) {
    if (-not $condition) { throw $message }
}

Assert ($verifierSource.Contains("build --pull=false --network default")) "Fresh image build must allow locked dependency access without pulling base images."

$trace = "0123456789abcdef0123456789abcdef"
$span = "0123456789abcdef"
$traceBytes = [Convert]::ToBase64String([byte[]](0x01,0x23,0x45,0x67,0x89,0xab,0xcd,0xef,0x01,0x23,0x45,0x67,0x89,0xab,0xcd,0xef))
$spanBytes = [Convert]::ToBase64String([byte[]](0x01,0x23,0x45,0x67,0x89,0xab,0xcd,0xef))
$response = @{ batches = @(@{ scopeSpans = @(@{ spans = @(@{ traceId = $traceBytes; spanId = $spanBytes; name = "GET /api/v1/runs" }) }) }) }
$spans = @(Get-TraceSpans $response $trace)
Assert ($spans.Count -eq 1 -and $spans[0] -eq $span) "Expected request span."
Assert (@(Get-TraceSpans $response ("f" * 32)).Count -eq 0) "Wrong trace accepted."
$metric = ('{"data":[{"seriesLabels":{"http_route":"/api/v1/runs"},"exemplars":[{"labels":{"trace_id":"' + $trace + '"}}]}]}') | ConvertFrom-Json
Assert ($null -ne (Find-Exemplar $metric $trace)) "Expected exemplar."
Assert ($null -eq (Find-Exemplar $metric ("f" * 32))) "Wrong exemplar accepted."
$metric.data[0].seriesLabels | Add-Member -NotePropertyName trace_id -NotePropertyValue $trace
$rejected = $false
try { Find-Exemplar $metric $trace } catch { $rejected = $true }
Assert $rejected "Trace metric label accepted."
Assert-ImageMatches "sha256:fresh" "sha256:fresh"
$rejected = $false
try { Assert-ImageMatches "sha256:fresh" "sha256:stale" } catch { $rejected = $true }
Assert $rejected "Wrong image accepted."
$metadata = @{ trace_id = $trace; span_id = $span; http_route = "/api/v1/runs"; http_request_method = "GET"; http_response_status_code = "200" }
$logs = @{ data = @{ result = @(@{ stream = $metadata; values = ,@("123", "HTTP request completed") }) } }
Assert (Test-CorrelatedLog $logs $trace $spans) "Expected correlated log."
$metadata.trace_id = "ffffffffffffffffffffffffffffffff"
Assert (-not (Test-CorrelatedLog $logs $trace $spans)) "Wrong log trace accepted."
$metadata.trace_id = $trace
$metadata.span_id = "ffffffffffffffff"
Assert (-not (Test-CorrelatedLog $logs $trace $spans)) "Wrong span accepted."
$metadata.span_id = $span
$logs.data.result[0].values[0][1] = "different log"
Assert (-not (Test-CorrelatedLog $logs $trace $spans)) "Wrong log accepted."

$fixture = Join-Path $PSScriptRoot ("verifier-test-" + [guid]::NewGuid().ToString("N"))
try {
    New-Item -ItemType Directory -Path "$fixture\app", "$fixture\alembic" -Force | Out-Null
    foreach ($name in @("Dockerfile", ".dockerignore", "pyproject.toml", "uv.lock", "alembic.ini", "app\main.py", "alembic\env.py")) {
        Set-Content -LiteralPath (Join-Path $fixture $name) -Value "original"
    }
    $fingerprint = Get-SourceFingerprint $fixture
    Assert-SourceUnchanged $fixture $fingerprint
    Set-Content -LiteralPath "$fixture\app\main.py" -Value "dirty"
    $rejected = $false
    try { Assert-SourceUnchanged $fixture $fingerprint } catch { $rejected = $true }
    Assert $rejected "Changed source accepted."

    $script:calls = @()
    function Invoke-Compose { param([string[]]$ComposeArguments) $script:calls += "compose $($ComposeArguments -join ' ')"; throw "simulated cleanup failure" }
    function docker { $script:calls += ($args -join " "); $global:LASTEXITCODE = 0; if ($args -contains "ls") { "image-id" } }
    $failed = $false
    try { Remove-DisposableResources $true $true "unique:verify" $fixture } catch { $failed = $_ -match "simulated cleanup failure" }
    Assert $failed "Cleanup failure was not reported."
    Assert ($script:calls -contains "compose down --volumes") "Project cleanup missing."
    Assert (@($script:calls | Where-Object { $_ -match "image rm unique:verify" }).Count -eq 1) "Precise image cleanup missing."
    Assert (-not (Test-Path $fixture)) "Disposable files remain after cleanup failure."
} finally {
    if (Test-Path $fixture) { Remove-Item -LiteralPath $fixture -Recurse -Force }
}
Write-Output "Verifier unit checks passed."
