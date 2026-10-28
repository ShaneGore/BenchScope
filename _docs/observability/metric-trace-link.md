# Local metric-to-trace link

The request counter carries a W3C trace ID as an OpenMetrics exemplar, not as a
metric label. The route, method, and status-code labels remain bounded. The
Prometheus scrape negotiates OpenMetrics, and Grafana maps the exemplar's
`trace_id` to the provisioned Tempo data source. The local journey dashboard
shows exemplars on its request-rate panel.

## Compatibility evidence

The locked Python versions are `opentelemetry-sdk==1.45.1`,
`opentelemetry-exporter-prometheus==0.66b1`, and `prometheus-client==0.26.0`.
The installed OpenTelemetry Prometheus reader's collector does not render SDK
exemplars; the pre-change `/metrics` output therefore had no exemplar syntax.
The installed Prometheus client does support `Counter.inc(exemplar=...)` and
OpenMetrics exposition. BenchScope uses it for the existing request-counter
name while OpenTelemetry continues to export the request-duration histogram.

The local stack versions are Prometheus `3.5.0`, Grafana `12.1.1`, OpenTelemetry
Collector Contrib `0.136.0`, and Tempo `2.8.1` (the runtime Prometheus and
Grafana version commands and the Compose image tags were checked). Prometheus
3.5.0 negotiates OpenMetrics 1.0.0 and requires
`--enable-feature=exemplar-storage`; the flag was observed empty before enabling
it, and Prometheus returned no exemplars until the flag was set. Grafana's
provisioned Prometheus data source maps the exemplar label `trace_id` to Tempo's
data-source UID `tempo`.

## Reproduce with synthetic local traffic

Start the normal local Compose stack, then run this PowerShell from the
repository root. It sends only a synthetic `GET /api/v1/runs`; it does not
import or persist a result. Add the normal local authorization header if the
local stack requires one.

```powershell
$traceId = [guid]::NewGuid().ToString("N")
$parentSpanId = [guid]::NewGuid().ToString("N").Substring(0, 16)
$traceparent = "00-$traceId-$parentSpanId-01"
$start = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()

$response = Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/v1/runs" `
  -Headers @{ traceparent = $traceparent }
if ($null -eq $response) { throw "Synthetic API request failed" }

$query = [uri]::EscapeDataString(
  'benchscope_http_server_requests_total{http_route="/api/v1/runs"}'
)
$series = $null
$exemplar = $null
for ($attempt = 0; $attempt -lt 20 -and $null -eq $exemplar; $attempt++) {
  $end = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
  $data = Invoke-RestMethod `
    -Uri "http://127.0.0.1:9090/api/v1/query_exemplars?query=$query&start=$($start - 5)&end=$end"
  foreach ($candidate in $data.data) {
    $match = @($candidate.exemplars |
      Where-Object { $_.labels.trace_id -eq $traceId } |
      Select-Object -First 1)
    if ($match.Count -gt 0) {
      $series = $candidate.seriesLabels
      $exemplar = $match[0]
      break
    }
  }
  if ($null -eq $exemplar) { Start-Sleep -Seconds 2 }
}
if ($null -eq $exemplar) { throw "Prometheus did not return the synthetic trace exemplar" }
if ($series.PSObject.Properties.Name -contains "trace_id") {
  throw "Trace ID unexpectedly appears as a metric label"
}

$trace = $null
for ($attempt = 0; $attempt -lt 20 -and $null -eq $trace; $attempt++) {
  try {
    $trace = Invoke-RestMethod -Uri "http://127.0.0.1:3200/api/traces/$traceId"
    $tempoTraceIds = @(
      foreach ($batch in $trace.batches) {
        foreach ($scope in $batch.scopeSpans) {
          foreach ($span in $scope.spans) {
            ([BitConverter]::ToString(
              [Convert]::FromBase64String($span.traceId)
            )).Replace("-", "").ToLowerInvariant()
          }
        }
      }
    )
    if ($tempoTraceIds -notcontains $traceId) { $trace = $null }
  } catch {
    $trace = $null
    Start-Sleep -Seconds 2
  }
}
if ($null -eq $trace) { throw "Tempo trace ID did not match $traceId" }
"Verified metric exemplar and Tempo trace: $traceId"
```

In Grafana, use an account allowed to access Explore, open **BenchScope local
journey**, hover the synthetic request-rate observation, and click its
**Trace** exemplar. The exemplar label is the same ID checked above; the
provisioned destination opens that ID in Tempo. The link was clicked in Grafana
12.1.1 and its Tempo Explore query contained the exact synthetic trace ID. A
Viewer-only anonymous session can see the dashboard/exemplar but is redirected
away from Explore; sign in with an authorized account to follow the trace link.
The Prometheus exemplar API and Tempo trace API checks above independently
confirm that the link target is the exact synthetic trace, not a time-window
guess.

The backend test `test_request_metric_exposes_exact_trace_as_openmetrics_exemplar`
also sends a synthetic request and verifies that the OpenMetrics counter
sample's exemplar exactly matches the exported span trace ID. Existing tests
continue to check that trace IDs, owner IDs, and run IDs are absent from metric
labels and that trace/log correlation is preserved.
