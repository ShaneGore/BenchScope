import { ArrowLeft } from 'lucide-react';
import type { BenchmarkRun } from '@/types';
import { getBenchmarkService } from '@/services/benchmark-service';
import { APP_MODE } from '@/lib/mode';
import { linkProps, navigate } from '@/lib/router';
import { useAsync } from '@/lib/hooks';
import { METRIC_DEFS, metricAvailable, runProfileLabel } from '@/lib/metrics';
import { comparableTaskRuns, taskResult } from '@/lib/task-results';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { EmptyState, ErrorState, SkeletonText } from '@/components/ui/State';

export function ComparePage({ ids }: { ids: string[] }) {
  const store = getBenchmarkService(APP_MODE);
  const validIds = ids.filter(Boolean);
  const queryKey = validIds.join(',');
  const { data, loading, error, refetch } = useAsync(
    () => (validIds.length >= 2 ? store.compareRuns(validIds) : Promise.resolve([] as BenchmarkRun[])),
    [queryKey]
  );

  const runs = data ?? [];
  const taskComparable = comparableTaskRuns(runs);
  const hasV2Runs = runs.some((run) => run.benchmark_details != null);
  const comparePassRate = !hasV2Runs || taskComparable;

  if (validIds.length < 2) {
    return (
      <div className="flex flex-col gap-6 animate-fadeIn">
        <h1 className="text-xl font-semibold text-text-primary tracking-tight">Compare runs</h1>
        <EmptyState
          title="Select at least two completed runs"
          description="Choose completed runs from history to compare their metrics side by side."
          action={
            <Button size="md" variant="primary" onClick={() => navigate('/runs')}>
              Go to history
            </Button>
          }
        />
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-6 animate-fadeIn">
        <h1 className="text-xl font-semibold text-text-primary tracking-tight">Compare runs</h1>
        <Card>
          <SkeletonText lines={8} />
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col gap-6 animate-fadeIn">
        <h1 className="text-xl font-semibold text-text-primary tracking-tight">Compare runs</h1>
        <ErrorState onRetry={refetch} description="Could not load comparison data." />
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div className="flex flex-col gap-6 animate-fadeIn">
        <h1 className="text-xl font-semibold text-text-primary tracking-tight">Compare runs</h1>
        <EmptyState
          title="No comparable runs"
          description="Selected runs are not completed or could not be found."
          action={
            <Button size="md" variant="primary" onClick={() => navigate('/runs')}>
              Go to history
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 animate-fadeIn">
      <div className="flex items-center gap-3">
        <button
          {...linkProps('/runs')}
          className="text-text-muted hover:text-text-primary transition-colors"
          aria-label="Back to history"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <h1 className="text-xl font-semibold text-text-primary tracking-tight">Compare runs</h1>
      </div>

      <Card className="!p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-surface/40">
                <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wide">
                  Metric
                </th>
                {runs.map((r) => (
                  <th
                    key={r.id}
                    className="px-4 py-3 text-right text-xs font-medium text-text-muted uppercase tracking-wide min-w-[140px]"
                  >
                    <div className="flex flex-col items-end gap-1">
                      <span className="text-text-primary normal-case tracking-normal">
                        {runProfileLabel(r)}
                      </span>
                      <span className="font-mono text-[10px] text-text-disabled">{r.id}</span>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {METRIC_DEFS.filter((def) => def.key !== 'pass_rate' || comparePassRate).map((def) => (
                <tr key={def.key} className="hover:bg-surface-raised/30">
                  <td className="px-4 py-3 text-text-secondary font-medium">{def.label}</td>
                  {runs.map((r) => {
                    const value = r.metrics[def.key];
                    const available = metricAvailable(value);
                    return (
                      <td
                        key={r.id}
                        className={`px-4 py-3 text-right font-mono tabular-nums ${
                          available ? 'text-text-primary' : 'text-unavailable'
                        }`}
                      >
                        {available ? def.fmt(value as number) : 'Unavailable'}
                      </td>
                    );
                  })}
                </tr>
              ))}
              <tr className="hover:bg-surface-raised/30">
                <td className="px-4 py-3 text-text-secondary font-medium">Status</td>
                {runs.map((r) => (
                  <td key={r.id} className="px-4 py-3 text-right">
                    <StatusBadge status={r.status} size="sm" />
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      </Card>

      {taskComparable && runs[0].benchmark_details && (
        <Card>
          <CardHeader
            title="Per-task outcomes"
            subtitle={`${runs[0].benchmark_details.benchmark_id} · ${runs[0].benchmark_details.release}`}
          />
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wide">Task</th>
                  {runs.map((run) => (
                    <th key={run.id} className="px-4 py-3 text-right text-xs font-medium text-text-muted min-w-[140px]">
                      {runProfileLabel(run)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {runs[0].benchmark_details.expected_task_ids.map((taskId) => (
                  <tr key={taskId}>
                    <td className="px-4 py-3 font-mono text-text-secondary">{taskId}</td>
                    {runs.map((run) => {
                      const passed = taskResult(run, taskId);
                      return (
                        <td key={run.id} className="px-4 py-3 text-right text-text-primary">
                          {passed == null ? 'Not run' : passed ? 'Pass' : 'Fail'}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {hasV2Runs && !taskComparable && (
        <p className="text-xs text-text-muted">
          Task outcomes and pass rates are hidden because the selected runs do not share the same benchmark release, manifest, and expected task set.
        </p>
      )}

      <p className="text-xs text-text-muted">
        Charts are deferred; this table renders only metrics available for the selected runs. Missing metrics
        remain unavailable and are never coerced to zero.
      </p>
    </div>
  );
}
