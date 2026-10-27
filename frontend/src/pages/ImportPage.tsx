import { useRef, useState } from 'react';
import { FileUp, Upload } from 'lucide-react';
import type { ApiError, BenchmarkRun, ImportError } from '@/types';
import { getBenchmarkService } from '@/services/benchmark-service';
import { APP_MODE, canImport } from '@/lib/mode';
import { navigate } from '@/lib/router';
import { fmtDate } from '@/lib/format';
import { runProfileLabel } from '@/lib/metrics';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/State';

export function ImportPage() {
  const store = getBenchmarkService(APP_MODE);
  const [file, setFile] = useState<File | null>(null);
  const [payload, setPayload] = useState<unknown>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<
    | { kind: 'success'; run: BenchmarkRun }
    | { kind: 'duplicate'; run?: BenchmarkRun }
    | { kind: 'error'; status: number; errors: ImportError[] }
    | null
  >(null);
  const inputRef = useRef<HTMLInputElement>(null);

  if (!canImport) {
    return (
      <div className="flex flex-col gap-6 animate-fadeIn">
        <h1 className="text-xl font-semibold text-text-primary tracking-tight">Import result</h1>
        <EmptyState
          title="Import not available"
          description="Import is disabled in this mode."
        />
      </div>
    );
  }

  const handleFile = async (f: File) => {
    setFile(f);
    setParseError(null);
    setResult(null);
    try {
      const text = await f.text();
      const json = JSON.parse(text);
      setPayload(json);
    } catch {
      setParseError('File is not valid JSON.');
      setPayload(null);
    }
  };

  const handleSubmit = async () => {
    if (!payload) return;
    setSubmitting(true);
    setResult(null);
    try {
      const res = await store.importRun(payload);
      if (res.ok) {
        setResult({ kind: 'success', run: res.run });
      } else if (res.status === 409) {
        setResult({ kind: 'duplicate', run: res.existingRun });
      } else {
        setResult({ kind: 'error', status: res.status, errors: res.errors });
      }
    } catch (e) {
      const err = e as ApiError;
      setResult({
        kind: 'error',
        status: err.status,
        errors: [{ message: String(err.detail ?? 'Import failed') }],
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 animate-fadeIn">
      <div>
        <h1 className="text-xl font-semibold text-text-primary tracking-tight">Import result</h1>
        <p className="text-sm text-text-secondary mt-1">
          Upload a supported benchmark result JSON file.
        </p>
      </div>

      <Card>
        <CardHeader title="Select file" icon={<FileUp className="h-4 w-4" />} />
        <div className="flex flex-col gap-3">
          <input
            ref={inputRef}
            type="file"
            accept="application/json,.json"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleFile(f);
            }}
          />
          <div className="flex items-center gap-3">
            <Button
              variant="secondary"
              leftIcon={<Upload className="h-4 w-4" />}
              onClick={() => inputRef.current?.click()}
            >
              Choose file
            </Button>
            {file && <span className="text-sm text-text-secondary truncate">{file.name}</span>}
          </div>
          {parseError && (
            <p className="text-sm text-status-failed-fg">{parseError}</p>
          )}
          <Button
            variant="primary"
            loading={submitting}
            disabled={!payload}
            onClick={handleSubmit}
          >
            Import
          </Button>
        </div>
      </Card>

      {result?.kind === 'success' && (
        <Card>
          <CardHeader title="Imported run" />
          <p className="text-sm text-text-secondary mb-3">
            Run imported successfully. Missing metrics remain unavailable.
          </p>
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-text-primary">{runProfileLabel(result.run)}</p>
              <p className="text-xs text-text-muted font-mono">{result.run.id}</p>
              <p className="text-xs text-text-muted">{fmtDate(result.run.started_at)}</p>
            </div>
            <Button size="sm" variant="ghost" onClick={() => navigate(`/runs/${result.run.id}`)}>
              View detail
            </Button>
          </div>
        </Card>
      )}

      {result?.kind === 'duplicate' && (
        <Card>
          <CardHeader title="Duplicate import" />
          <p className="text-sm text-text-secondary mb-3">
            This result already exists in your history.
          </p>
          {result.run && (
            <Button size="sm" variant="ghost" onClick={() => navigate(`/runs/${result.run?.id}`)}>
              View existing run
            </Button>
          )}
        </Card>
      )}

      {result?.kind === 'error' && (
        <Card>
          <CardHeader title="Import failed" />
          <ul className="flex flex-col gap-1 text-sm text-status-failed-fg">
            {result.errors.map((err, i) => (
              <li key={i}>
                {err.field ? `${err.field}: ` : ''}
                {err.message}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
