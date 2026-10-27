import { useCallback, useEffect, useState } from 'react';
import { ArrowLeft, RefreshCw, Trash2 } from 'lucide-react';
import type { ApiError, BenchmarkRun } from '@/types';
import { getBenchmarkService } from '@/services/benchmark-service';
import { LocalRunnerService } from '@/services/runner-service';
import { APP_MODE, canDelete } from '@/lib/mode';
import { linkProps, navigate } from '@/lib/router';
import { usePolling } from '@/lib/hooks';
import { fmtDate, fmtElapsed } from '@/lib/format';
import { METRIC_DEFS, metricAvailable, runProfileLabel } from '@/lib/metrics';
import { taskResult } from '@/lib/task-results';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { Modal } from '@/components/ui/Modal';
import { EmptyState, ErrorState, Skeleton, SkeletonText } from '@/components/ui/State';

export function RunDetailPage({
  id,
  serviceMode = APP_MODE,
  runnerEnabled = false,
}: {
  id: string;
  serviceMode?: typeof APP_MODE | 'demo';
  runnerEnabled?: boolean;
}) {
  const store = getBenchmarkService(serviceMode);
  const canDeleteRun = serviceMode !== 'demo' && canDelete;
  const canRetryRun = serviceMode === 'local' && runnerEnabled;
  const [run, setRun] = useState<BenchmarkRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await store.getRun(id);
      setRun(r);
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setLoading(false);
    }
  }, [id, store]);

  useEffect(() => {
    load();
  }, [load]);

  usePolling(
    run?.status === 'running',
    async () => {
      try {
        const r = await store.getRun(id);
        setRun(r);
      } catch {
        // ignore polling errors
      }
    },
    1000
  );

  if (loading) return <RunDetailSkeleton />;
  if (error) {
    if (error.status === 404) {
      return (
        <EmptyState
          title="Run not found"
          description={`No run exists with id ${id}.`}
          action={
            <Button size="sm" variant="ghost" onClick={() => navigate(serviceMode === 'demo' ? '/demo' : '/runs')}>
              {serviceMode === 'demo' ? 'Back to demo' : 'Back to history'}
            </Button>
          }
        />
      );
    }
    return <ErrorState onRetry={load} description="Could not load run detail." />;
  }
  if (!run) return null;
  const handleDelete = async () => {
    setBusy(true);
    setActionError(null);
    try {
      await store.deleteRun(run.id);
      navigate('/runs');
    } catch (e) {
      setActionError((e as ApiError).detail?.toString?.() ?? 'Delete failed');
    } finally {
      setBusy(false);
      setDeleteOpen(false);
    }
  };

  const handleRetry = async () => {
    setBusy(true);
    setActionError(null);
    try {
      const next = await new LocalRunnerService().retry(run.id);
      navigate(`/runs/${next.id}`);
    } catch (e) {
      setActionError((e as ApiError).detail?.toString?.() ?? 'Retry failed');
    } finally {
      setBusy(false);
    }
  };

  const isFailed = run.status === 'failed' || run.status === 'interrupted';

  return (
    <div className="flex flex-col gap-6 animate-fadeIn">
      <div className="flex items-center gap-3">
        <button
          {...linkProps(serviceMode === 'demo' ? '/demo' : '/runs')}
          className="text-text-muted hover:text-text-primary transition-colors"
          aria-label="Back to history"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-semibold text-text-primary tracking-tight truncate">
            {runProfileLabel(run)}
          </h1>
          <p className="text-sm text-text-secondary mt-1 font-mono truncate">{run.id}</p>
        </div>
        <StatusBadge status={run.status} />
      </div>

      {actionError && (
        <div className="rounded-md border border-status-failed-border bg-status-failed-bg px-4 py-2 text-sm text-status-failed-fg">
          {actionError}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2">
          <CardHeader title="Metrics" subtitle="Available metrics only; missing values stay unavailable" />
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            {METRIC_DEFS.map((def) => {
              const value = run.metrics[def.key];
              const available = metricAvailable(value);
              return (
                <div key={def.key} className="flex flex-col gap-1">
                  <span className="text-[11px] uppercase tracking-wide text-text-muted font-medium">
                    {def.label}
                  </span>
                  <span
                    className={`font-mono tabular-nums text-base ${
                      available ? 'text-text-primary' : 'text-unavailable'
                    }`}
                  >
                    {available ? def.fmt(value as number) : 'Unavailable'}
                  </span>
                </div>
              );
            })}
          </div>
        </Card>

        <Card>
          <CardHeader title="Run metadata" />
          <dl className="flex flex-col gap-2 text-sm">
            <MetaRow label="Model" value={run.profile_snapshot.model_name} />
            <MetaRow label="Profile" value={run.profile_snapshot.name} />
            <MetaRow label="Quantization" value={run.profile_snapshot.quantization ?? 'Unavailable'} />
            <MetaRow
              label="Context"
              value={run.profile_snapshot.context_length?.toLocaleString() ?? 'Unavailable'}
            />
            <MetaRow label="Engine" value={run.profile_snapshot.inference_engine ?? 'Unavailable'} />
            <MetaRow label="Config" value={run.benchmark_config.name} />
            {run.benchmark_details && (
              <>
                <MetaRow label="Seed" value={run.benchmark_config.seed?.toString() ?? 'Unavailable'} />
                <MetaRow label="Repeat" value={run.benchmark_config.repeat_index?.toString() ?? 'Unavailable'} />
              </>
            )}
            {run.benchmark_details && (
              <>
                <MetaRow label="Benchmark" value={run.benchmark_details.benchmark_id} />
                <MetaRow label="Release" value={run.benchmark_details.release} />
                <MetaRow
                  label="Task coverage"
                  value={`${run.task_results?.length ?? 0}/${run.benchmark_details.expected_task_ids.length}`}
                />
              </>
            )}
            <MetaRow label="Started" value={fmtDate(run.started_at)} />
            <MetaRow label="Ended" value={fmtDate(run.ended_at)} />
            <MetaRow label="Elapsed" value={fmtElapsed(run.started_at, run.ended_at)} />
            <MetaRow label="Source" value={run.source ?? 'Unavailable'} />
            <MetaRow label="Artifact" value={run.artifact_ref ?? 'Unavailable'} />
          </dl>
        </Card>
      </div>

      {run.benchmark_details && (
        <Card>
          <CardHeader
            title="Benchmark task outcomes"
            subtitle={`${run.benchmark_details.benchmark_id} · ${run.benchmark_details.release}`}
          />
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="px-2 py-2 text-[11px] font-semibold uppercase tracking-wide text-text-muted">Task</th>
                  <th className="px-2 py-2 text-right text-[11px] font-semibold uppercase tracking-wide text-text-muted">Outcome</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {run.benchmark_details.expected_task_ids.map((taskId) => {
                  const passed = taskResult(run, taskId);
                  return (
                    <tr key={taskId}>
                      <td className="px-2 py-2 font-mono text-text-secondary">{taskId}</td>
                      <td className="px-2 py-2 text-right text-text-primary">
                        {passed == null ? 'Not run' : passed ? 'Pass' : 'Fail'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-text-muted font-mono break-all">
            Manifest SHA-256: {run.benchmark_details.manifest_sha256}
          </p>
        </Card>
      )}

      {isFailed && (
        <Card>
          <CardHeader title="Diagnostics" />
          <dl className="flex flex-col gap-2 text-sm">
            <MetaRow label="Category" value={run.error_category ?? 'Unavailable'} />
            <MetaRow label="Message" value={run.error_message_sanitised ?? 'Unavailable'} />
            <MetaRow
              label="Exit code"
              value={run.process_exit_code != null ? String(run.process_exit_code) : 'Unavailable'}
            />
          </dl>
        </Card>
      )}

      {run.hardware_snapshot && (
        <Card>
          <CardHeader title="Hardware snapshot" />
          <dl className="flex flex-col gap-2 text-sm">
            <MetaRow label="GPU" value={run.hardware_snapshot.gpu ?? 'Unavailable'} />
            <MetaRow
              label="VRAM"
              value={
                run.hardware_snapshot.gpu_vram_gb != null
                  ? `${run.hardware_snapshot.gpu_vram_gb} GB`
                  : 'Unavailable'
              }
            />
            <MetaRow label="CPU" value={run.hardware_snapshot.cpu ?? 'Unavailable'} />
            <MetaRow
              label="RAM"
              value={run.hardware_snapshot.ram_gb != null ? `${run.hardware_snapshot.ram_gb} GB` : 'Unavailable'}
            />
            <MetaRow label="OS" value={run.hardware_snapshot.os ?? 'Unavailable'} />
          </dl>
        </Card>
      )}

      {run.events && run.events.length > 0 && (
        <Card>
          <CardHeader title="Event timeline" />
          <ol className="flex flex-col gap-2">
            {run.events.map((e, i) => (
              <li key={i} className="flex items-start gap-3 text-sm">
                <span className="text-[11px] text-text-muted font-mono whitespace-nowrap mt-0.5">
                  {fmtDate(e.ts)}
                </span>
                <div>
                  <p className="text-text-primary font-medium">{e.event}</p>
                  {e.detail && <p className="text-xs text-text-secondary">{e.detail}</p>}
                </div>
              </li>
            ))}
          </ol>
        </Card>
      )}

      <div className="flex flex-wrap gap-2">
        {isFailed && canRetryRun && (
          <Button
            variant="primary"
            leftIcon={<RefreshCw className="h-4 w-4" />}
            onClick={handleRetry}
            loading={busy}
          >
            Retry run
          </Button>
        )}
        {canDeleteRun && (
          <Button variant="danger" leftIcon={<Trash2 className="h-4 w-4" />} onClick={() => setDeleteOpen(true)}>
            Delete
          </Button>
        )}
        {serviceMode !== 'demo' && (
          <Button variant="ghost" onClick={() => navigate(`/compare?ids=${run.id}`)}>
            Compare
          </Button>
        )}
      </div>

      {deleteOpen && (
        <Modal
          open
          onClose={() => setDeleteOpen(false)}
          title="Delete run"
          footer={
            <>
              <Button size="sm" variant="ghost" onClick={() => setDeleteOpen(false)}>
                Cancel
              </Button>
              <Button size="sm" variant="danger" loading={busy} onClick={handleDelete}>
                Delete
              </Button>
            </>
          }
        >
          <p>
            This will permanently remove run <span className="font-mono text-text-primary">{run.id}</span> from
            your history. This action cannot be undone.
          </p>
        </Modal>
      )}
    </div>
  );
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <dt className="text-text-muted shrink-0">{label}</dt>
      <dd className="text-text-primary text-right break-words">{value}</dd>
    </div>
  );
}

function RunDetailSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <Skeleton className="h-6 w-48" />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2">
          <SkeletonText lines={6} />
        </Card>
        <Card>
          <SkeletonText lines={8} />
        </Card>
      </div>
    </div>
  );
}
