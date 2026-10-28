$ErrorActionPreference = "Stop"

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$composeFile = Join-Path $repositoryRoot "compose.yaml"
$projectName = "benchscope-metric-trace-$([guid]::NewGuid().ToString('N').Substring(0, 12))"
$temporaryDirectory = Join-Path ([IO.Path]::GetTempPath()) $projectName
$environmentFile = Join-Path $temporaryDirectory "synthetic.env"
$composeOverrideFile = Join-Path $temporaryDirectory "synthetic-api-image.yaml"
$secretFile = Join-Path $temporaryDirectory "synthetic-alert-secret"
$composeFiles = @("--file", $composeFile, "--file", $composeOverrideFile)
$dockerContext = $null
$started = $false
$buildApiImage = $false
$savedEnvironment = @{}
$environmentNames = @()

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
    $apiImage = "benchscope-issue35-api:latest"
    $buildBaseImages = @("ghcr.io/astral-sh/uv:0.12.5", "python:3.12-slim")
    $availableImages = @(
        & docker --context $dockerContext image ls --format "{{.Repository}}:{{.Tag}}"
    )
    if ($LASTEXITCODE -ne 0) {
        throw "Could not inspect local Docker images."
    }
    $missingImages = @(
        $requiredServiceImages | Where-Object { $availableImages -notcontains $_ }
    )
    if ($missingImages.Count -gt 0) {
        throw "Required images are not already local; no pull was attempted: $($missingImages -join ', ')"
    }
    $buildApiImage = $availableImages -notcontains $apiImage
    if ($buildApiImage) {
        $missingBuildBases = @(
            $buildBaseImages | Where-Object { $availableImages -notcontains $_ }
        )
        if ($missingBuildBases.Count -gt 0) {
            throw "Cached API image $apiImage is absent and build bases are not all local; no pull was attempted: $($missingBuildBases -join ', ')"
        }
    }

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

    Write-Output "Starting isolated project $projectName on checked loopback ports."
    if ($buildApiImage) {
        Write-Output "Cached API image $apiImage is absent; building locally from cached bases only."
        $apiBuildOption = "--build"
    } else {
        Write-Output "Using cached API image $apiImage without rebuilding."
        $apiBuildOption = "--no-build"
    }
    $started = $true
    Invoke-Compose -ComposeArguments @(
        "up", "--detach", $apiBuildOption, "--pull", "never",
        "api", "prometheus", "otel-collector", "grafana"
    )

    $apiUri = "http://127.0.0.1:$($ports.API_PORT)"
    $prometheusUri = "http://127.0.0.1:$($ports.PROMETHEUS_PORT)"
    $tempoUri = "http://127.0.0.1:$($ports.TEMPO_PORT)"
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
    $seriesLabels = $null
    for ($attempt = 0; $attempt -lt 45 -and $null -eq $exemplar; $attempt++) {
        $end = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        $result = Invoke-RestMethod `
            -Uri "$prometheusUri/api/v1/query_exemplars?query=$query&start=$($requestStart - 5)&end=$end" `
            -TimeoutSec 10
        foreach ($candidate in $result.data) {
            $matches = @($candidate.exemplars |
                Where-Object { $_.labels.trace_id -eq $traceId } |
                Select-Object -First 1)
            if ($matches.Count -gt 0) {
                $seriesLabels = $candidate.seriesLabels
                $exemplar = $matches[0]
                break
            }
        }
        if ($null -eq $exemplar) { Start-Sleep -Seconds 2 }
    }
    if ($null -eq $exemplar) {
        throw "Prometheus did not expose the synthetic request's exact trace exemplar."
    }
    if ($seriesLabels.PSObject.Properties.Name -contains "trace_id") {
        throw "The trace ID was incorrectly added as a metric label."
    }

    $tempoTrace = $null
    $tempoTraceIds = @()
    for ($attempt = 0; $attempt -lt 30 -and $null -eq $tempoTrace; $attempt++) {
        try {
            $candidateTrace = Invoke-RestMethod `
                -Uri "$tempoUri/api/traces/$traceId" `
                -TimeoutSec 10
            $candidateIds = @(
                foreach ($batch in $candidateTrace.batches) {
                    foreach ($scope in $batch.scopeSpans) {
                        foreach ($span in $scope.spans) {
                            ([BitConverter]::ToString(
                                [Convert]::FromBase64String($span.traceId)
                            )).Replace("-", "").ToLowerInvariant()
                        }
                    }
                }
            )
            if ($candidateIds -contains $traceId) {
                $tempoTrace = $candidateTrace
                $tempoTraceIds = $candidateIds
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
    $grafanaTraceIds = @(
        foreach ($batch in $grafanaTrace.batches) {
            foreach ($scope in $batch.scopeSpans) {
                foreach ($span in $scope.spans) {
                    ([BitConverter]::ToString(
                        [Convert]::FromBase64String($span.traceId)
                    )).Replace("-", "").ToLowerInvariant()
                }
            }
        }
    )
    if ($grafanaTraceIds -notcontains $traceId) {
        throw "Anonymous Grafana Tempo proxy did not return a span with the exact synthetic trace ID $traceId."
    }

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
    Write-Output "Tempo trace IDs: $($tempoTraceIds -join ', ')"
    Write-Output "Anonymous Grafana Tempo proxy trace IDs: $($grafanaTraceIds -join ', ')"
    Write-Output "Verified exact metric-exemplar-to-Tempo trace match: $traceId"
    Write-Output "Verified anonymous Grafana Trace URL returns exact trace: $traceId"
} finally {
    if ($started) {
        try {
            Invoke-Compose -ComposeArguments @("down", "--volumes")
        } catch {
            Write-Warning "Could not clean up only disposable project $projectName : $_"
        }
    }
    foreach ($name in $savedEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], "Process")
    }
    if (Test-Path $temporaryDirectory) {
        Remove-Item -LiteralPath $temporaryDirectory -Recurse -Force
    }
}
