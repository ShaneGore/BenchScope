import { useMemo } from 'react';
import {
  ArrowRight,
  FlaskConical,
  ListTree,
  Upload,
} from 'lucide-react';
import type { AppMode, BenchmarkRun } from '@/types';
import { getBenchmarkService } from '@/services/benchmark-service';
import { useAsync } from '@/lib/hooks';
import { APP_MODE, canImport, canLaunch, isDemo } from '@/lib/mode';
import { linkProps, navigate } from '@/lib/router';
import { fmtDate, fmtElapsed, fmtMs, fmtNum, fmtRate } from '@/lib/format';
import { metricAvailable, runProfileLabel } from '@/lib/metrics';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { EmptyState, ErrorState, Skeleton, SkeletonText } from '@/components/ui/State';

export function DashboardPage({ serviceMode = APP_MODE }: { serviceMode?: AppMode } = {}) {
  const store = getBenchmarkService(serviceMode);
  const { data, loading, error, refetch } = useAsync(() => store.listRuns({ limit: 50 }), []);

  const summary = useMemo(() => computeSummary(data?.items ?? []), [data]);

  if (loading) return <DashboardSkeleton />;
  if (error) return <ErrorState onRetry={refetch} description="Could not load dashboard data." />;

  const runs = data?.items ?? [];
  const activeRun = runs.find((r) => r.status === 'running');
  const recent = runs.slice(0, 5);

  return (
    <div className="flex flex-col gap-6 animate-fadeIn">
      <PageHeading />

      {activeRun && <ActiveRunBanner run={activeRun} />}

      <SummaryGrid summary={summary} />

      <Card>
        <CardHeader
          title="Recent activity"
          subtitle="Latest benchmark runs"
          icon={<ListTree className="h-4 w-4" />}
          action={
            <Button size="sm" variant="ghost" rightIcon={<ArrowRight className="h-3.5 w-3.5" />} onClick={() => navigate('/runs')}>
              View all
            </Button>
          }
        />
        {runs.length === 0 ? (
          <EmptyState
            icon={<ListTree className="h-9 w-9" strokeWidth={1.5} />}
            title="No runs yet"
            description={
              canLaunch
                ? 'Launch your first benchmark or import an existing result to start building history.'
                : canImport
                  ? 'Import your first benchmark result to start building history.'
                  : 'No runs available in this mode.'
            }
            action={
              canLaunch ? (
                <Button size="md" leftIcon={<FlaskConical className="h-4 w-4" />} onClick={() => navigate('/benchmark')}>
                  Launch benchmark
                </Button>
              ) : canImport ? (
                <Button size="md" leftIcon={<Upload className="h-4 w-4" />} onClick={() => navigate('/import')}>
                  Import result
                </Button>
              ) : null
            }
          />
        ) : (
          <RecentList runs={recent} />
        )}
      </Card>

      {!isDemo && runs.length === 0 && <ZeroActions />}
    </div>
  );
}

function PageHeading() {
  return (
    <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold text-text-primary tracking-tight">Dashboard</h1>
        <p className="text-sm text-text-secondary mt-1">
          Overview of benchmark runs, outcomes, and recent activity.
        </p>
      </div>
      <div className="flex gap-2">
        {canLaunch && (
          <Button size="sm" variant="secondary" leftIcon={<FlaskConical className="h-3.5 w-3.5" />} onClick={() => navigate('/benchmark')}>
            Launch
          </Button>
        )}
        {canImport && (
          <Button size="sm" variant="secondary" leftIcon={<Upload className="h-3.5 w-3.5" />} onClick={() => navigate('/import')}>
            Import
          </Button>
        )}
        <Button size="sm" variant="outline" onClick={() => navigate('/compare')}>
          Compare
        </Button>
      </div>
    </div>
  );
}

interface Summary {
  completed: number;
  failed: number;
  interrupted: number;
  cancelled: number;
  running: number;
  total: number;
  bestQuality: number | null;
  bestThroughput: number | null;
  bestTtft: number | null;
}

function computeSummary(runs: BenchmarkRun[]): Summary {
  const by = (s: BenchmarkRun['status']) => runs.filter((r) => r.status === s).length;
  const completed = runs.filter((r) => r.status === 'completed');
  const pick = (key: keyof BenchmarkRun['metrics'], higher: boolean) => {
    const vals = completed
      .map((r) => r.metrics[key])
      .filter((v): v is number => metricAvailable(v));
    if (vals.length === 0) return null;
    return higher ? Math.max(...vals) : Math.min(...vals);
  };
  return {
    completed: by('completed'),
    failed: by('failed'),
    interrupted: by('interrupted'),
    cancelled: by('cancelled'),
    running: by('running'),
    total: runs.length,
    bestQuality: pick('quality_score', true),
    bestThroughput: pick('generation_throughput_tps', true),
    bestTtft: pick('ttft_ms', false),
  };
}

function SummaryGrid({ summary }: { summary: Summary }) {
  const tiles = [
    { label: 'Completed', value: summary.completed, tone: 'completed' as const, hint: summary.total ? `${Math.round((summary.completed / summary.total) * 100)}% of total` : undefined },
    { label: 'Failed', value: summary.failed, tone: 'failed' as const, hint: summary.failed ? 'Non-success runs' : undefined, link: summary.failed ? '/runs?status=failed' : undefined },
    { label: 'Interrupted', value: summary.interrupted, tone: 'interrupted' as const, hint: summary.interrupted ? 'Recoverable attempts' : undefined, link: summary.interrupted ? '/runs?status=interrupted' : undefined },
    { label: 'Running', value: summary.running, tone: 'running' as const, hint: summary.running ? 'Active benchmark' : undefined, link: summary.running ? '/runs?status=running' : undefined },
  ];
  const toneCls = {
    completed: 'text-status-completed-fg',
    failed: 'text-status-failed-fg',
    interrupted: 'text-status-interrupted-fg',
    running: 'text-status-running-fg',
  };
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {tiles.map((t) => (
        <Card key={t.label} className="!p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-text-secondary">{t.label}</span>
            {t.link && (
              <button
                {...linkProps(t.link)}
                className="text-text-muted hover:text-text-primary transition-colors"
                aria-label={`Filter ${t.label} runs`}
              >
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
          <div className={`mt-2 font-mono tabular-nums text-2xl font-semibold ${toneCls[t.tone]}`}>
            {t.value}
          </div>
          {t.hint && <div className="mt-1 text-[11px] text-text-muted">{t.hint}</div>}
        </Card>
      ))}
    </div>
  );
}

function ActiveRunBanner({ run }: { run: BenchmarkRun }) {
  return (
    <button
      onClick={() => navigate(`/runs/${run.id}`)}
      className="flex items-center gap-3 rounded-lg border border-status-running-border bg-status-running-bg px-4 py-3 text-left hover:bg-status-running-bg/80 transition-colors w-full"
      aria-label={`Active run ${run.profile_snapshot.name} — view detail`}
    >
      <span className="flex h-8 w-8 items-center justify-center rounded-full bg-status-running-bg border border-status-running-border">
        <span className="h-2.5 w-2.5 rounded-full bg-status-running-fg animate-pulseDot" />
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-status-running-fg">Run in progress</p>
        <p className="text-xs text-text-secondary truncate">
          {runProfileLabel(run)} — {run.benchmark_config.name}
        </p>
      </div>
      <span className="font-mono tabular-nums text-xs text-status-running-fg">
        {fmtElapsed(run.started_at, run.ended_at)}
      </span>
      <ArrowRight className="h-4 w-4 text-status-running-fg" />
    </button>
  );
}

function RecentList({ runs }: { runs: BenchmarkRun[] }) {
  return (
    <ul className="divide-y divide-border-subtle">
      {runs.map((r) => (
        <li key={r.id}>
          <button
            onClick={() => navigate(`/runs/${r.id}`)}
            className="flex items-center gap-3 w-full py-3 text-left hover:bg-surface-raised/40 -mx-2 px-2 rounded-md transition-colors"
          >
            <StatusBadge status={r.status} size="sm" showDot />
            <div className="flex-1 min-w-0">
              <p className="text-sm text-text-primary truncate">{runProfileLabel(r)}</p>
              <p className="text-[11px] text-text-muted font-mono truncate">{r.benchmark_config.name}</p>
            </div>
            <div className="hidden sm:flex items-center gap-4 text-right">
              <RecentMetric label="Quality" value={r.metrics.quality_score != null ? fmtRate(r.metrics.quality_score) : null} />
              <RecentMetric label="Gen t/s" value={r.metrics.generation_throughput_tps != null ? fmtNum(r.metrics.generation_throughput_tps, 1) : null} />
              <RecentMetric label="TTFT" value={r.metrics.ttft_ms != null ? fmtMs(r.metrics.ttft_ms) : null} />
            </div>
            <span className="text-[11px] text-text-muted font-mono whitespace-nowrap">{fmtDate(r.started_at)}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}

function RecentMetric({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex flex-col items-end">
      <span className="text-[10px] uppercase tracking-wide text-text-muted">{label}</span>
      <span className={`text-xs font-mono tabular-nums ${value ? 'text-text-primary' : 'text-unavailable'}`}>
        {value ?? 'Unavailable'}
      </span>
    </div>
  );
}

function ZeroActions() {
  return (
    <div className="grid sm:grid-cols-2 gap-3">
      {canLaunch && (
        <Card className="!p-5 hover:border-border-strong transition-colors cursor-pointer" >
          <button {...linkProps('/benchmark')} className="text-left w-full">
            <FlaskConical className="h-6 w-6 text-primary-500 mb-3" />
            <h3 className="text-sm font-semibold text-text-primary">Launch a benchmark</h3>
            <p className="text-xs text-text-secondary mt-1">Select a model profile and config to start a new local run.</p>
          </button>
        </Card>
      )}
      {canImport && (
        <Card className="!p-5 hover:border-border-strong transition-colors cursor-pointer">
          <button {...linkProps('/import')} className="text-left w-full">
            <Upload className="h-6 w-6 text-primary-500 mb-3" />
            <h3 className="text-sm font-semibold text-text-primary">Import a result</h3>
            <p className="text-xs text-text-secondary mt-1">Upload an existing benchmark JSON to add it to your history.</p>
          </button>
        </Card>
      )}
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-4 w-72 mt-2" />
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i} className="!p-4">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-8 w-12 mt-3" />
          </Card>
        ))}
      </div>
      <Card>
        <SkeletonText lines={6} />
      </Card>
    </div>
  );
}
