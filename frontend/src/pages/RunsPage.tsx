import { useState } from 'react';
import { Filter, ListTree, X } from 'lucide-react';
import type { RunFilters, RunStatus } from '@/types';
import { getBenchmarkService } from '@/services/benchmark-service';
import { useAsync } from '@/lib/hooks';
import { APP_MODE, canDelete } from '@/lib/mode';
import { navigate } from '@/lib/router';
import { fmtDate, fmtMs, fmtNum, fmtRate } from '@/lib/format';
import { metricAvailable, runProfileLabel } from '@/lib/metrics';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { Field, Select, TextInput } from '@/components/ui/Field';
import { Modal } from '@/components/ui/Modal';
import {
  EmptyState,
  ErrorState,
  Skeleton,
} from '@/components/ui/State';

const STATUS_OPTIONS: { value: RunStatus; label: string }[] = [
  { value: 'completed', label: 'Completed' },
  { value: 'running', label: 'Running' },
  { value: 'failed', label: 'Failed' },
  { value: 'interrupted', label: 'Interrupted' },
];

export function RunsPage({ initialStatus }: { initialStatus?: string }) {
  const store = getBenchmarkService(APP_MODE);
  const [filters, setFilters] = useState<RunFilters>({
    status: (initialStatus as RunStatus) || null,
    model: null,
    from: null,
    to: null,
    limit: 50,
  });
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const queryKey = JSON.stringify(filters);
  const { data, loading, error, refetch } = useAsync(
    () => store.listRuns(filters),
    [queryKey]
  );

  const runs = data?.items ?? [];
  const completedSelected = selected.size >= 2;
  const toggleSelect = (id: string, status: RunStatus) => {
    if (status !== 'completed') return;
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else if (next.size < 4) next.add(id);
      return next;
    });
  };

  return (
    <div className="flex flex-col gap-6 animate-fadeIn">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-text-primary tracking-tight">Run history</h1>
          <p className="text-sm text-text-secondary mt-1">Browse, filter, and compare your benchmark runs.</p>
        </div>
        {completedSelected && (
          <Button
            size="sm"
            variant="primary"
            onClick={() => navigate(`/compare?ids=${Array.from(selected).join(',')}`)}
          >
            Compare {selected.size} runs
          </Button>
        )}
      </div>

      <FilterBar
        filters={filters}
        onChange={setFilters}
        onClear={() => {
          setFilters({ status: null, model: null, from: null, to: null, limit: 50 });
          setSelected(new Set());
        }}
      />

      <Card className="!p-0 overflow-hidden">
        {error ? (
          <ErrorState onRetry={refetch} description="Could not load runs." />
        ) : loading ? (
          <RunsSkeleton />
        ) : runs.length === 0 ? (
          <EmptyState
            icon={<ListTree className="h-9 w-9" strokeWidth={1.5} />}
            title="No runs match"
            description="No runs match the current filters. Try clearing filters or importing a result."
            action={
              <Button size="sm" variant="ghost" leftIcon={<X className="h-3.5 w-3.5" />} onClick={() => setFilters({ status: null, model: null, from: null, to: null, limit: 50 })}>
                Clear filters
              </Button>
            }
          />
        ) : (
          <RunsTable
            runs={runs}
            selected={selected}
            onToggle={toggleSelect}
            onDelete={canDelete ? setDeleteId : undefined}
          />
        )}
      </Card>

      {data?.has_more && (
        <div className="text-center text-xs text-text-muted">
          Showing {runs.length} runs — more available with pagination.
        </div>
      )}

      {deleteId && (
        <DeleteConfirm
          runId={deleteId}
          error={deleteError}
          onClose={() => {
            setDeleteId(null);
            setDeleteError(null);
          }}
          onConfirm={async () => {
            try {
              await store.deleteRun(deleteId);
              setSelected((p) => {
                const n = new Set(p);
                n.delete(deleteId);
                return n;
              });
              setDeleteId(null);
              setDeleteError(null);
              refetch();
            } catch (e) {
              setDeleteError(String((e as import('@/types').ApiError).detail ?? 'Delete failed'));
            }
          }}
        />
      )}
    </div>
  );
}

function FilterBar({
  filters,
  onChange,
  onClear,
}: {
  filters: RunFilters;
  onChange: (f: RunFilters) => void;
  onClear: () => void;
}) {
  const set = (patch: Partial<RunFilters>) => onChange({ ...filters, ...patch });
  const hasFilters = filters.status || filters.model || filters.from || filters.to;
  return (
    <Card className="!py-3.5">
      <div className="flex items-center gap-2 mb-3 text-text-muted">
        <Filter className="h-3.5 w-3.5" />
        <span className="text-xs font-medium uppercase tracking-wide">Filters</span>
        {hasFilters && (
          <button onClick={onClear} className="ml-auto text-xs text-primary-500 hover:text-primary-hover transition-colors">
            Clear all
          </button>
        )}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <Field label="Status">
          <Select
            value={filters.status ?? ''}
            onChange={(e) => set({ status: (e.target.value as RunStatus) || null })}
          >
            <option value="">All statuses</option>
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </Select>
        </Field>
        <Field label="Model">
          <TextInput
            value={filters.model ?? ''}
            placeholder="Exact model name"
            onChange={(e) => set({ model: e.target.value || null })}
          />
        </Field>
        <Field label="From date">
          <TextInput
            type="date"
            value={filters.from ? filters.from.slice(0, 10) : ''}
            onChange={(e) => set({ from: e.target.value ? new Date(e.target.value).toISOString() : null })}
          />
        </Field>
        <Field label="To date">
          <TextInput
            type="date"
            value={filters.to ? filters.to.slice(0, 10) : ''}
            onChange={(e) => set({ to: e.target.value ? new Date(e.target.value).toISOString() : null })}
          />
        </Field>
      </div>
    </Card>
  );
}

function RunsTable({
  runs,
  selected,
  onToggle,
  onDelete,
}: {
  runs: import('@/types').BenchmarkRun[];
  selected: Set<string>;
  onToggle: (id: string, status: RunStatus) => void;
  onDelete?: (id: string) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left">
            <th className="w-8 px-4 py-2.5">
              <span className="sr-only">Select for compare</span>
            </th>
            <th className="px-2 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-text-muted">Status</th>
            <th className="px-2 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-text-muted">Profile</th>
            <th className="px-2 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-text-muted hidden md:table-cell">Config</th>
            <th className="px-2 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-text-muted text-right">Quality</th>
            <th className="px-2 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-text-muted text-right hidden lg:table-cell">Gen t/s</th>
            <th className="px-2 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-text-muted text-right hidden lg:table-cell">TTFT</th>
            <th className="px-2 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-text-muted hidden sm:table-cell">Started</th>
            <th className="w-10 px-2 py-2.5"><span className="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border-subtle">
          {runs.map((r) => {
            const isSel = selected.has(r.id);
            const canSel = r.status === 'completed';
            return (
              <tr
                key={r.id}
                className={`group hover:bg-surface-raised/30 transition-colors ${isSel ? 'bg-primary-500/5' : ''}`}
              >
                <td className="px-4 py-2.5">
                  <input
                    type="checkbox"
                    disabled={!canSel}
                    checked={isSel}
                    onChange={() => onToggle(r.id, r.status)}
                    aria-label={`Select run ${r.profile_snapshot.name} for comparison`}
                    className="h-3.5 w-3.5 rounded border-border-strong bg-surface-raised text-primary-600 focus:ring-1 focus:ring-primary-500 disabled:opacity-30"
                  />
                </td>
                <td className="px-2 py-2.5">
                  <button onClick={() => navigate(`/runs/${r.id}`)} className="block">
                    <StatusBadge status={r.status} size="sm" showDot />
                  </button>
                </td>
                <td className="px-2 py-2.5">
                  <button onClick={() => navigate(`/runs/${r.id}`)} className="text-left">
                    <div className="text-text-primary text-sm">{runProfileLabel(r)}</div>
                    <div className="text-[11px] text-text-muted font-mono">{r.profile_snapshot.model_name}</div>
                  </button>
                </td>
                <td className="px-2 py-2.5 hidden md:table-cell">
                  <span className="text-xs text-text-secondary font-mono">{r.benchmark_config.name}</span>
                </td>
                <td className="px-2 py-2.5 text-right font-mono tabular-nums text-xs">
                  {metricAvailable(r.metrics.quality_score) ? (
                    <span className="text-text-primary">{fmtRate(r.metrics.quality_score!)}</span>
                  ) : (
                    <span className="text-unavailable">--</span>
                  )}
                </td>
                <td className="px-2 py-2.5 text-right font-mono tabular-nums text-xs hidden lg:table-cell">
                  {metricAvailable(r.metrics.generation_throughput_tps) ? (
                    <span className="text-text-primary">{fmtNum(r.metrics.generation_throughput_tps!, 1)}</span>
                  ) : (
                    <span className="text-unavailable">--</span>
                  )}
                </td>
                <td className="px-2 py-2.5 text-right font-mono tabular-nums text-xs hidden lg:table-cell">
                  {metricAvailable(r.metrics.ttft_ms) ? (
                    <span className="text-text-primary">{fmtMs(r.metrics.ttft_ms!)}</span>
                  ) : (
                    <span className="text-unavailable">--</span>
                  )}
                </td>
                <td className="px-2 py-2.5 hidden sm:table-cell">
                  <span className="text-xs text-text-muted font-mono">{fmtDate(r.started_at)}</span>
                </td>
                <td className="px-2 py-2.5">
                  {onDelete && (
                    <button
                      onClick={() => onDelete(r.id)}
                      className="text-text-muted hover:text-status-failed-fg transition-colors opacity-0 group-hover:opacity-100"
                      aria-label="Delete run"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function RunsSkeleton() {
  return (
    <div className="divide-y divide-border-subtle">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-4 py-3.5">
          <Skeleton className="h-3.5 w-3.5 rounded" />
          <Skeleton className="h-5 w-20 rounded-full" />
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-3 w-24" />
          <div className="flex-1" />
          <Skeleton className="h-3 w-24" />
        </div>
      ))}
    </div>
  );
}

function DeleteConfirm({
  runId,
  error,
  onClose,
  onConfirm,
}: {
  runId: string;
  error: string | null;
  onClose: () => void;
  onConfirm: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  return (
    <Modal
      open
      onClose={onClose}
      title="Delete run"
      footer={
        <>
          <Button size="sm" variant="ghost" onClick={onClose}>Cancel</Button>
          <Button
            size="sm"
            variant="danger"
            loading={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await onConfirm();
              } finally {
                setBusy(false);
              }
            }}
          >
            Delete
          </Button>
        </>
      }
    >
      <p>This will permanently remove run <span className="font-mono text-text-primary">{runId}</span> from your history. This action cannot be undone.</p>
      {error && <p className="mt-3 text-sm text-status-failed-fg">{error}</p>}
    </Modal>
  );
}
