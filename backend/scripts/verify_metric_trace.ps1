param([switch]$LibraryOnly)

$ErrorActionPreference = "Stop"

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$composeFile = Join-Path $repositoryRoot "compose.yaml"
$projectName = "benchscope-metric-trace-$([guid]::NewGuid().ToString('N').Substring(0, 12))"
$temporaryDirectory = Join-Path $PSScriptRoot $projectName
$environmentFile = Join-Path $temporaryDirectory "synthetic.env"
$composeOverrideFile = Join-Path $temporaryDirectory "synthetic-api-image.yaml"
$secretFile = Join-Path $temporaryDirectory "synthetic-alert-secret"
$composeFiles = @("--file", $composeFile, "--file", (Join-Path $repositoryRoot "compose.observability.yaml"), "--file", $composeOverrideFile)
$dockerContext = $null
$started = $false
$imageAttempted = $false
$directoryCreated = $false
$savedEnvironment = @{}
$environmentNames = @()

function Get-SourceFingerprint {
    param([string]$Backend)
    $paths = @("Dockerfile", ".dockerignore", "pyproject.toml", "uv.lock", "alembic.ini")
    $files = @($paths | ForEach-Object { Get-Item -LiteralPath (Join-Path $Backend $_) }) +
        @(Get-ChildItem -LiteralPath (Join-Path $Backend "app"), (Join-Path $Backend "alembic") -File -Recurse -Force |
            Where-Object { $_.FullName -notmatch '[\\/](__pycache__|\.venv|secrets)[\\/]' -and $_.Extension -notin @(".pem", ".key", ".gguf", ".safetensors", ".onnx", ".pt", ".pth") })
    $lines = foreach ($file in ($files | Sort-Object FullName)) {
        if ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Build input is a link: $($file.FullName)" }
        "$($file.FullName.Substring($Backend.Length + 1)) $((Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash)"
    }
    $bytes = [Text.Encoding]::UTF8.GetBytes(($lines -join "`n"))
    $hash = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($hash.ComputeHash($bytes))).Replace("-", "").ToLowerInvariant() }
    finally { $hash.Dispose() }
}

function Get-TraceSpans {
    param($Trace, [string]$TraceId)
    foreach ($batch in $Trace.batches) {
        foreach ($scope in $batch.scopeSpans) {
            foreach ($span in $scope.spans) {
                $id = ([BitConverter]::ToString([Convert]::FromBase64String($span.traceId))).Replace("-", "").ToLowerInvariant()
                if ($id -eq $TraceId -and $span.name -eq "GET /api/v1/runs") {
                    ([BitConverter]::ToString([Convert]::FromBase64String($span.spanId))).Replace("-", "").ToLowerInvariant()
                }
            }
        }
    }
}

function Test-CorrelatedLog {
    param($Result, [string]$TraceId, [string[]]$SpanIds)
    foreach ($stream in $Result.data.result) {
        $metadata = $stream.stream
        if ($null -eq $metadata) { continue }
        foreach ($value in $stream.values) {
            if ($value.Count -lt 2 -or $value[1] -ne "HTTP request completed") { continue }
            if ($metadata.trace_id -eq $TraceId -and $SpanIds -contains $metadata.span_id -and
                $metadata.http_route -eq "/api/v1/runs" -and
                $metadata.http_request_method -eq "GET" -and
                "$($metadata.http_response_status_code)" -eq "200") { return $true }
        }
    }
    return $false
}

function Assert-SourceUnchanged {
    param([string]$Backend, [string]$Expected)
    if ((Get-SourceFingerprint $Backend) -ne $Expected) { throw "API build inputs changed during verification." }
}

function Assert-ImageMatches {
    param([string]$Expected, [string]$Actual)
    if (-not $Expected -or $Actual -ne $Expected) { throw "API container is not running the freshly built image." }
}

function Find-Exemplar {
    param($Result, [string]$TraceId)
    $found = $null
    foreach ($candidate in $Result.data) {
        if ($candidate.seriesLabels.PSObject.Properties.Name -contains "trace_id") {
            throw "The trace ID was incorrectly added as a metric label."
        }
        foreach ($item in $candidate.exemplars) {
            if ($item.labels.trace_id -eq $TraceId) {
                $found = $item
            }
        }
    }
    return $found
}

function Remove-DisposableResources {
    param([bool]$Started, [bool]$ImageAttempted, [string]$Image, [string]$Directory)
    $errors = @()
    if ($Started) {
        try { Invoke-Compose -ComposeArguments @("down", "--volumes") }
        catch { $errors += "Could not clean disposable project $projectName : $_" }
    }
    if ($ImageAttempted) {
        $found = @(& docker --context $dockerContext image ls --quiet $Image)
        if ($LASTEXITCODE -ne 0) { $errors += "Could not inspect disposable image $Image" }
        elseif ($found.Count -gt 0) {
            & docker --context $dockerContext image rm $Image
            if ($LASTEXITCODE -ne 0) { $errors += "Could not remove disposable image $Image" }
        }
    }
    if ($Directory -and (Test-Path -LiteralPath $Directory)) {
        try { Remove-Item -LiteralPath $Directory -Recurse -Force }
        catch { $errors += "Could not remove disposable files $Directory : $_" }
    }
    if ($errors.Count -gt 0) { throw ($errors -join "; ") }
}

if ($LibraryOnly) { return }

function Get-FreeLoopbackPort {
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
    try {
        $listener.Start()
        return ([Net.IPEndPoint]$listener.LocalEndpoint).Port
    } finally {
        $listener.Stop()
    }
}

function Invoke-Compose {
    param([Parameter(Mandatory)][string[]]$ComposeArguments)

    & docker --context $dockerContext compose `
        --project-name $projectName `
        --project-directory $repositoryRoot `
        @composeFiles `
        --env-file $environmentFile `
        @ComposeArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose failed (exit $LASTEXITCODE): $($ComposeArguments -join ' ')"
    }
}

function Wait-ForHttp {
    param(
        [Parameter(Mandatory)][string]$Uri,
        [int]$Attempts = 60
    )

    for ($attempt = 0; $attempt -lt $Attempts; $attempt++) {
        try {
            return Invoke-RestMethod -Uri $Uri -TimeoutSec 3
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    throw "Local service did not become ready: $Uri"
}

try {
    if ($env:DOCKER_HOST) {
        throw "DOCKER_HOST is set; refusing an ambiguous Docker endpoint."
    }

    $dockerContext = (& docker context show).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Could not identify the active Docker context."
    }
    $contextInfo = (& docker context inspect $dockerContext | ConvertFrom-Json)[0]
    if ($LASTEXITCODE -ne 0 -or
        $contextInfo.Endpoints.docker.Host -notmatch "^(npipe://|unix://)") {
        throw "The active Docker context is not a local named-pipe or Unix-socket engine."
    }

    $requiredServiceImages = @(
        "postgres:17-alpine",
        "otel/opentelemetry-collector-contrib:0.136.0",
        "prom/prometheus:v3.5.0",
        "grafana/loki:3.5.3",
        "grafana/tempo:2.8.1",
        "grafana/grafana:12.1.1"
    )
    $apiImage = "${projectName}-api:verify"
    $buildBaseImages = @("ghcr.io/astral-sh/uv:0.12.5", "python:3.12-slim")
    $availableImages = @(
        & docker --context $dockerContext image ls --format "{{.Repository}}:{{.Tag}}"
    )
    if ($LASTEXITCODE -ne 0) {
        throw "Could not inspect local Docker images."
    }
    $missingImages = @(
        ($requiredServiceImages + $buildBaseImages) | Where-Object { $availableImages -notcontains $_ }
    )
    if ($missingImages.Count -gt 0) {
        throw "Required images are not already local; no pull was attempted: $($missingImages -join ', ')"
    }
    if ($availableImages -contains $apiImage) { throw "Disposable image tag already exists: $apiImage" }
    $backend = (Resolve-Path (Join-Path $repositoryRoot "backend")).Path
    $revision = (& git -C $repositoryRoot rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0) { throw "Could not identify source revision." }
    $fingerprint = Get-SourceFingerprint $backend
    Write-Output "Source revision: $revision; API build-input SHA256: $fingerprint (includes checkout changes)."

    $ports = @{}
    foreach ($name in @("POSTGRES_PORT", "API_PORT", "OTLP_PORT", "PROMETHEUS_PORT", "LOKI_PORT", "TEMPO_PORT", "GRAFANA_PORT")) {
        $port = $null
        for ($attempt = 0; $attempt -lt 20; $attempt++) {
            $candidate = Get-FreeLoopbackPort
            if ($ports.Values -notcontains $candidate) {
                $port = $candidate
                break
            }
        }
        if ($null -eq $port) {
            throw "Could not reserve a unique available loopback port for $name."
        }
        $ports[$name] = $port
    }

    New-Item -ItemType Directory -Path $temporaryDirectory | Out-Null
    $directoryCreated = $true
    [IO.File]::WriteAllText(
        $composeOverrideFile,
        "services:`n  api:`n    image: $apiImage`n",
        [Text.UTF8Encoding]::new($false)
    )
    $postgresPassword = [guid]::NewGuid().ToString("N")
    $alertBearer = [guid]::NewGuid().ToString("N")
    [IO.File]::WriteAllText(
        $secretFile,
        ([guid]::NewGuid().ToString("N")),
        [Text.UTF8Encoding]::new($false)
    )

    $environment = [ordered]@{
        POSTGRES_DB                  = "benchscope_synthetic"
        POSTGRES_USER                = "benchscope_synthetic"
        POSTGRES_PASSWORD            = $postgresPassword
        POSTGRES_PORT                = $ports.POSTGRES_PORT
        APP_ENV                      = "development"
        LOCAL_AUTH_BYPASS            = "true"
        API_PORT                     = $ports.API_PORT
        OTLP_PORT                    = $ports.OTLP_PORT
        PROMETHEUS_PORT              = $ports.PROMETHEUS_PORT
        LOKI_PORT                    = $ports.LOKI_PORT
        TEMPO_PORT                   = $ports.TEMPO_PORT
        GRAFANA_PORT                 = $ports.GRAFANA_PORT
        ALERT_RECEIVER_BEARER        = $alertBearer
        ALERT_RECEIVER_SECRET_FILE   = $secretFile.Replace("\", "/")
    }
    $environmentText = @(
        foreach ($entry in $environment.GetEnumerator()) {
            "$($entry.Key)=$($entry.Value)"
        }
    ) -join "`n"
    [IO.File]::WriteAllText(
        $environmentFile,
        "$environmentText`n",
        [Text.UTF8Encoding]::new($false)
    )

    $environmentNames = @($environment.Keys) + @(
        [Environment]::GetEnvironmentVariables("Process").Keys |
            Where-Object { $_ -like "COMPOSE_*" }
    )
    $savedEnvironment = @{}
    foreach ($name in ($environmentNames | Select-Object -Unique)) {
        $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
        [Environment]::SetEnvironmentVariable($name, $null, "Process")
    }

    Invoke-Compose -ComposeArguments @("config", "--quiet")
    $existingContainers = @(
        & docker --context $dockerContext compose `
            --project-name $projectName `
            --project-directory $repositoryRoot `
            @composeFiles `
            --env-file $environmentFile ps --all --quiet
    )
    if ($LASTEXITCODE -ne 0 -or $existingContainers.Count -gt 0) {
        throw "The disposable Compose project name is unexpectedly in use."
    }

    Write-Output "Building $apiImage with local bases and TLS-verified locked dependencies."
    $imageAttempted = $true
    & docker --context $dockerContext build --pull=false --network default --tag $apiImage --build-arg "APP_REVISION=$revision" $backend
    if ($LASTEXITCODE -ne 0) { throw "API build failed while installing locked dependencies; check package-index connectivity." }
    Assert-SourceUnchanged $backend $fingerprint
    $imageId = (& docker --context $dockerContext image inspect --format '{{.Id}}' $apiImage).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $imageId) { throw "Could not identify freshly built API image." }
    Write-Output "Starting isolated project $projectName using image $imageId."
    $started = $true
    Invoke-Compose -ComposeArguments @(
        "up", "--detach", "--no-build", "--pull", "never",
        "api", "prometheus", "otel-collector", "grafana"
    )
    $containerId = (& docker --context $dockerContext compose --project-name $projectName --project-directory $repositoryRoot @composeFiles --env-file $environmentFile ps --quiet api).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $containerId) { throw "Could not identify the API container." }
    $runningImage = (& docker --context $dockerContext inspect --format '{{.Image}}' $containerId).Trim()
    if ($LASTEXITCODE -ne 0) { throw "Could not inspect the API container image." }
    Assert-ImageMatches $imageId $runningImage

    $apiUri = "http://127.0.0.1:$($ports.API_PORT)"
    $prometheusUri = "http://127.0.0.1:$($ports.PROMETHEUS_PORT)"
    $tempoUri = "http://127.0.0.1:$($ports.TEMPO_PORT)"
    $lokiUri = "http://127.0.0.1:$($ports.LOKI_PORT)"
    $grafanaUri = "http://127.0.0.1:$($ports.GRAFANA_PORT)"
    Wait-ForHttp -Uri "$apiUri/ready" | Out-Null
    Wait-ForHttp -Uri "$prometheusUri/-/ready" | Out-Null
    Wait-ForHttp -Uri "$tempoUri/ready" | Out-Null
    Wait-ForHttp -Uri "$grafanaUri/api/health" | Out-Null

    $traceId = [guid]::NewGuid().ToString("N")
    $parentSpanId = [guid]::NewGuid().ToString("N").Substring(0, 16)
    $traceparent = "00-$traceId-$parentSpanId-01"
    $requestStart = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $response = Invoke-RestMethod `
        -Uri "$apiUri/api/v1/runs" `
        -Headers @{ traceparent = $traceparent } `
        -TimeoutSec 10
    if ($response.items.Count -ne 0) {
        throw "The disposable synthetic database unexpectedly returned run records."
    }
    Write-Output "Synthetic GET /api/v1/runs returned an empty page from the disposable database."

    $query = [uri]::EscapeDataString(
        'benchscope_http_server_requests_total{http_route="/api/v1/runs"}'
    )
    $exemplar = $null
    for ($attempt = 0; $attempt -lt 45 -and $null -eq $exemplar; $attempt++) {
        $end = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        $result = Invoke-RestMethod `
            -Uri "$prometheusUri/api/v1/query_exemplars?query=$query&start=$($requestStart - 5)&end=$end" `
            -TimeoutSec 10
        $exemplar = Find-Exemplar $result $traceId
        if ($null -eq $exemplar) { Start-Sleep -Seconds 2 }
    }
    if ($null -eq $exemplar) {
        throw "Prometheus did not expose the synthetic request's exact trace exemplar."
    }
    $tempoTrace = $null
    $tempoSpanIds = @()
    for ($attempt = 0; $attempt -lt 30 -and $null -eq $tempoTrace; $attempt++) {
        try {
            $candidateTrace = Invoke-RestMethod `
                -Uri "$tempoUri/api/traces/$traceId" `
                -TimeoutSec 10
            $candidateIds = @(Get-TraceSpans $candidateTrace $traceId)
            if ($candidateIds.Count -gt 0) {
                $tempoTrace = $candidateTrace
                $tempoSpanIds = $candidateIds
            }
        } catch {
            # Tempo may not have received the batch yet.
        }
        if ($null -eq $tempoTrace) { Start-Sleep -Seconds 2 }
    }
    if ($null -eq $tempoTrace) {
        throw "Tempo did not return a span with the exact synthetic trace ID $traceId."
    }
    $grafanaTrace = Invoke-RestMethod `
        -Uri "$grafanaUri/api/datasources/proxy/uid/tempo/api/traces/$traceId" `
        -TimeoutSec 10
    $grafanaSpanIds = @(Get-TraceSpans $grafanaTrace $traceId)
    if (@($grafanaSpanIds | Where-Object { $tempoSpanIds -contains $_ }).Count -eq 0) {
        throw "Anonymous Grafana Tempo proxy did not return a span with the exact synthetic trace ID $traceId."
    }

    $logQuery = [uri]::EscapeDataString('{service_name="benchscope-api"} |= "HTTP request completed"')
    $foundLog = $false
    $lastLokiError = $null
    for ($attempt = 0; $attempt -lt 45 -and -not $foundLog; $attempt++) {
        try {
            $logResult = Invoke-RestMethod -Uri "$lokiUri/loki/api/v1/query_range?query=$logQuery&start=$($requestStart - 5)000000000&limit=1000" -TimeoutSec 10
            $foundLog = Test-CorrelatedLog $logResult $traceId $tempoSpanIds
        } catch {
            $lastLokiError = $_.Exception.Message
        }
        if (-not $foundLog) { Start-Sleep -Seconds 2 }
    }
    if (-not $foundLog) {
        if ($lastLokiError) { Write-Output "Last Loki query error: $lastLokiError" }
        try {
            $diagnosticQuery = [uri]::EscapeDataString('{service_name=~".+"} |= "HTTP request completed"')
            $diagnostic = Invoke-RestMethod -Uri "$lokiUri/loki/api/v1/query_range?query=$diagnosticQuery&start=$($requestStart - 5)000000000&limit=100" -TimeoutSec 10
            Write-Output "Loki diagnostic response: $($diagnostic | ConvertTo-Json -Depth 8 -Compress)"
        } catch {
            Write-Output "Loki diagnostic query failed: $($_.Exception.Message)"
        }
        $collectorLogs = & docker --context $dockerContext compose `
            --project-name $projectName `
            --project-directory $repositoryRoot `
            @composeFiles `
            --env-file $environmentFile `
            logs --no-color --tail 40 otel-collector loki 2>&1
        if ($LASTEXITCODE -eq 0) { Write-Output "Collector and Loki logs:`n$($collectorLogs -join "`n")" }
        throw "Loki did not return the synthetic HTTP completed log with the matching trace and span IDs."
    }
    Assert-SourceUnchanged $backend $fingerprint
    $currentContainer = (& docker --context $dockerContext compose --project-name $projectName --project-directory $repositoryRoot @composeFiles --env-file $environmentFile ps --quiet api).Trim()
    if ($LASTEXITCODE -ne 0 -or $currentContainer -ne $containerId) { throw "API container changed during verification." }
    $runningImage = (& docker --context $dockerContext inspect --format '{{.Image}}' $currentContainer).Trim()
    if ($LASTEXITCODE -ne 0) { throw "Could not inspect the API container image." }
    Assert-ImageMatches $imageId $runningImage

    $buildInfo = Invoke-RestMethod `
        -Uri "$prometheusUri/api/v1/status/buildinfo" `
        -TimeoutSec 10
    $versionCode = "import importlib.metadata as m; print(', '.join(f'{p}=={m.version(p)}' for p in ('opentelemetry-sdk', 'opentelemetry-exporter-prometheus', 'prometheus-client')))"
    $pythonVersions = & docker --context $dockerContext compose `
        --project-name $projectName `
        --project-directory $repositoryRoot `
        @composeFiles `
        --env-file $environmentFile `
        exec --no-TTY api uv run --no-sync python -c $versionCode
    if ($LASTEXITCODE -ne 0) {
        throw "Could not report the API's locked telemetry package versions."
   }

    Write-Output "Prometheus version: $($buildInfo.data.version)"
    Write-Output "Compose image versions: Prometheus 3.5.0; Grafana 12.1.1; Collector 0.136.0; Tempo 2.8.1; Loki 3.5.3; PostgreSQL 17-alpine."
    Write-Output "API telemetry packages: $pythonVersions"
    Write-Output "Metric exemplar trace_id: $($exemplar.labels.trace_id)"
    Write-Output "Verified exemplar, Tempo, Loki HTTP completed log and anonymous Grafana proxy for trace $traceId; Tempo span IDs: $($tempoSpanIds -join ', ')."
} finally {
    try { Remove-DisposableResources $started $imageAttempted $apiImage $(if ($directoryCreated) { $temporaryDirectory } else { "" }) }
    finally {
        foreach ($name in $savedEnvironment.Keys) {
            [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], "Process")
        }
    }
}
