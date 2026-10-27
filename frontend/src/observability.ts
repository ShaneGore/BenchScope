import {
  ROOT_CONTEXT,
  SpanStatusCode,
  trace,
  type Tracer,
} from '@opentelemetry/api';
import { W3CTraceContextPropagator } from '@opentelemetry/core';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { Resource } from '@opentelemetry/resources';
import {
  BatchSpanProcessor,
  SimpleSpanProcessor,
  type SpanExporter,
} from '@opentelemetry/sdk-trace-base';
import { WebTracerProvider } from '@opentelemetry/sdk-trace-web';

type TracedOperation<T> = (
  headers: Record<string, string>,
  recordResponse: (statusCode: number) => void
) => Promise<T>;

const propagator = new W3CTraceContextPropagator();
let tracer: Tracer = trace.getTracer('benchscope.frontend');

export function initializeTelemetry(
  endpoint = import.meta.env.VITE_OTEL_EXPORTER_OTLP_ENDPOINT as
    | string
    | undefined,
  testExporter?: SpanExporter
): void {
  try {
    const provider = new WebTracerProvider({
      resource: new Resource({ 'service.name': 'benchscope-frontend' }),
    });
    if (testExporter) {
      provider.addSpanProcessor(new SimpleSpanProcessor(testExporter));
    } else if (endpoint) {
      provider.addSpanProcessor(
        new BatchSpanProcessor(new OTLPTraceExporter({ url: endpoint }), {
          maxQueueSize: 256,
          scheduledDelayMillis: 1000,
        })
      );
    }
    tracer = provider.getTracer('benchscope.frontend');
  } catch {
    tracer = trace.getTracer('benchscope.frontend');
  }
}

export function journeyRoute(
  path: string,
  method: string
): string | undefined {
  const cleanPath = path.split('?', 1)[0];
  if (method.toUpperCase() === 'POST' && cleanPath === '/runs/import') {
    return '/api/v1/runs/import';
  }
  if (method.toUpperCase() === 'GET' && cleanPath === '/runs') {
    return '/api/v1/runs';
  }
  if (
    method.toUpperCase() === 'GET' &&
    /^\/runs\/[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
      cleanPath
    )
  ) {
    return '/api/v1/runs/{id}';
  }
  return undefined;
}

export async function traceJourneyRequest<T>(
  route: string | undefined,
  method: string,
  operation: TracedOperation<T>
): Promise<T> {
  if (!route) return operation({}, () => undefined);

  let span;
  try {
    span = tracer.startSpan(`${method.toUpperCase()} ${route}`, {
      attributes: {
        'http.route': route,
        'http.request.method': method.toUpperCase(),
      },
    });
  } catch {
    return operation({}, () => undefined);
  }

  const headers: Record<string, string> = {};
  try {
    propagator.inject(
      trace.setSpanContext(ROOT_CONTEXT, span.spanContext()),
      headers,
      {
        set: (carrier, key, value) => {
          carrier[key] = value;
        },
      }
    );
  } catch {
    // Trace propagation is best-effort; do not block the request.
  }

  try {
    return await operation(headers, (statusCode) => {
      try {
        span.setAttribute('http.response.status_code', statusCode);
        if (statusCode >= 400) span.setStatus({ code: SpanStatusCode.ERROR });
      } catch {
        // Instrumentation is deliberately isolated from request handling.
      }
    });
  } catch (error) {
    try {
      span.setAttribute('error.type', 'network_error');
      span.setStatus({ code: SpanStatusCode.ERROR });
    } catch {
      // Instrumentation is deliberately isolated from request handling.
    }
    throw error;
  } finally {
    try {
      span.end();
    } catch {
      // Instrumentation is deliberately isolated from request handling.
    }
  }
}
