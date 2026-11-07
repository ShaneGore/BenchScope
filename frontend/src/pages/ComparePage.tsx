import { useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import type { ApiError, AppMode, BenchmarkRun } from '@/types';
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

export function ComparePage({ ids, serviceMode = APP_MODE }: { ids: string[]; serviceMode?: AppMode }) {
  const isDemo = serviceMode === 'demo';
  const historyPath = isDemo ? '/demo' : '/runs';
  const store = getBenchmarkService(serviceMode);
  const validIds = ids.filter(Boolean);
  const queryKey = validIds.join(',');
  const { data, loading, error, refetch } = useAsync(
    () => (validIds.length >= 2 ? store.compareRuns(validIds) : Promise.resolve([] as BenchmarkRun[])),
    [queryKey, serviceMode]
  );

  const runs = data ?? [];
  const taskComparable = comparableTaskRuns(runs);
  const hasV2Runs = runs.some((run) => run.benchmark_details != null);
  const comparePassRate = !hasV2Runs || taskComparable;

  if (validIds.length < 2) {
    if (isDemo) return <DemoRunPicker initialIds={validIds} />;
    return (
      <div className="flex flex-col gap-6 animate-fadeIn">
        <h1 className="text-xl font-semibold text-text-primary tracking-tight">Compare runs</h1>
        <EmptyState
          title="Select at least two completed runs"
          description="Choose completed runs from history to compare their metrics side by side."
          action={
            <Button size="md" variant="primary" onClick={() => navigate(historyPath)}>
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
        <ErrorState onRetry={refetch} description={isDemo && typeof (error as ApiError).detail === 'string' ? String((error as ApiError).detail) : 'Could not load comparison data.'} />
        {isDemo && <Button onClick={() => navigate('/demo/compare')}>Choose demo configurations</Button>}
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
            <Button size="md" variant="primary" onClick={() => navigate(historyPath)}>
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
          {...linkProps(historyPath)}
          className="text-text-muted hover:text-text-primary transition-colors"
          aria-label="Back to history"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <h1 className="text-xl font-semibold text-text-primary tracking-tight">Compare runs</h1>
        {isDemo && <Button className="ml-auto" onClick={() => navigate('/demo/compare')}>Change selection</Button>}
      </div>

      {isDemo && <p className="text-sm text-text-secondary">Published summaries from the same 47-task benchmark. Reasoning, MTP, context and hosting differ; these are illustrative comparisons, not a controlled ranking.</p>}
      <ComparisonCharts runs={runs} showPassRate={comparePassRate} />

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
              {METRIC_DEFS.filter((def) => (def.key !== 'pass_rate' || comparePassRate) && (!isDemo || runs.some((run) => metricAvailable(run.metrics[def.key])))).map((def) => (
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
              <tr>
                <td className="px-4 py-3 text-text-secondary font-medium">Configuration</td>
                {runs.map((run) => <td key={run.id} className="px-4 py-3 text-right text-text-secondary text-xs">{run.benchmark_config.name}</td>)}
              </tr>
              <tr>
                <td className="px-4 py-3 text-text-secondary font-medium">Temperature / token limit</td>
                {runs.map((run) => <td key={run.id} className="px-4 py-3 text-right font-mono text-xs text-text-secondary">{run.benchmark_config.temperature ?? 'Unavailable'} / {run.benchmark_config.max_tokens ?? 'Unavailable'}</td>)}
              </tr>
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
            subtitle={`${runs[0].benchmark_details.benchmark_id} Â· ${runs[0].benchmark_details.release}`}
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
        Missing metrics remain unavailable; metrics with no demo measurements are omitted from the table. Configuration differences can affect both pass rate and throughput.
      </p>
    </div>
  );
}


function DemoRunPicker({ initialIds }: { initialIds: string[] }) {
  const store = getBenchmarkService('demo');
  const { data, loading, error, refetch } = useAsync(() => store.listRuns(), []);
  const [selected, setSelected] = useState<string[]>(initialIds);
  if (loading) return <Card><SkeletonText lines={6} /></Card>;
  if (error) return <ErrorState onRetry={refetch} description="Could not load demo configurations." />;
  const runs = data?.items ?? [];
  return (
    <div className="flex flex-col gap-6 animate-fadeIn">
      <div>
        <h1 className="text-xl font-semibold text-text-primary">Compare demo configurations</h1>
        <p className="mt-2 text-sm text-text-secondary">Choose two to six configurations from the published 47-task benchmark. No account needed.</p>
      </div>
      <Card>
        <fieldset>
          <legend className="mb-3 text-sm font-medium text-text-primary">Configurations</legend>
          <div className="divide-y divide-border-subtle">
            {runs.map((run) => (
              <label key={run.id} className="flex items-center gap-3 py-3 cursor-pointer">
                <input type="checkbox" className="accent-primary-500 h-4 w-4" checked={selected.includes(run.id)} disabled={!selected.includes(run.id) && selected.length >= 6}
                  onChange={(event) => setSelected((ids) => event.target.checked ? [...ids, run.id] : ids.filter((id) => id !== run.id))} />
                <span className="flex-1 min-w-0">
                  <span className="block text-sm text-text-primary">{runProfileLabel(run)}</span>
                  <span className="block text-xs text-text-muted">{run.benchmark_config.name}</span>
                </span>
                <span className="font-mono text-xs text-text-secondary">{run.metrics.pass_rate != null ? `${(run.metrics.pass_rate * 100).toFixed(2)}%` : 'Unavailable'}</span>
              </label>
            ))}
          </div>
        </fieldset>
      </Card>
      <div className="flex items-center gap-4">
        <Button disabled={selected.length < 2} onClick={() => navigate(`/demo/compare?ids=${selected.map(encodeURIComponent).join(',')}`)}>Compare selected</Button>
        <span className="text-sm text-text-muted" aria-live="polite">{selected.length} selected · choose 2–6</span>
      </div>
    </div>
  );
}

function ComparisonCharts({ runs, showPassRate }: { runs: BenchmarkRun[]; showPassRate: boolean }) {
  const definitions = METRIC_DEFS.filter((definition) =>
    (definition.key === 'pass_rate' && showPassRate) || definition.key === 'generation_throughput_tps'
  );
  const colours = ['bg-primary-500', 'bg-emerald-500', 'bg-violet-500', 'bg-amber-500', 'bg-cyan-500', 'bg-rose-500'];
  return (
    <div className="grid lg:grid-cols-2 gap-4">
      {definitions.map((definition) => {
        const available = runs.map((run) => run.metrics[definition.key]).filter((value): value is number => metricAvailable(value));
        const maximum = definition.key === 'pass_rate' ? 1 : Math.max(1, ...available);
        return (
          <Card key={definition.key}>
            <CardHeader title={definition.key === 'pass_rate' ? 'Pass rate comparison' : 'Generation throughput comparison'} subtitle={definition.key === 'pass_rate' ? 'Share of benchmark tasks passed · scale 0–100%' : 'Mean output tokens per request-second'} />
            <div className="space-y-4">
              {runs.map((run, index) => {
                const value = run.metrics[definition.key];
                const measured = metricAvailable(value);
                return (
                  <div key={run.id}>
                    <div className="flex justify-between items-start gap-3 mb-1.5 text-xs">
                      <span className="text-text-secondary">{runProfileLabel(run)}<span className="block text-[10px] text-text-muted">{run.benchmark_config.name}</span></span>
                      <span className="font-mono whitespace-nowrap text-text-primary">{measured ? definition.fmt(value as number) : 'Unavailable'}</span>
                    </div>
                    {measured && <div className="h-2 rounded-full bg-surface-raised" role="img" aria-label={`${runProfileLabel(run)}: ${definition.fmt(value as number)}`}>
                      <div className={`h-2 rounded-full ${colours[index % colours.length]}`} style={{ width: `${Math.min(100, Math.max(0, (value as number) / maximum * 100))}%` }} />
                    </div>}
                  </div>
                );
              })}
            </div>
          </Card>
        );
      })}
    </div>
  );
}
