import { useEffect, useState } from 'react';
import { FlaskConical, Loader2 } from 'lucide-react';
import type { ApiError, BenchmarkConfig, BenchmarkRun, ModelProfile } from '@/types';
import { getStore } from '@/mock/store';
import { APP_MODE, canLaunch } from '@/lib/mode';
import { navigate } from '@/lib/router';
import { useAsync, usePolling } from '@/lib/hooks';
import { fmtDate, fmtElapsed } from '@/lib/format';
import { runProfileLabel } from '@/lib/metrics';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { Field, Select } from '@/components/ui/Field';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { EmptyState, ErrorState, SkeletonText } from '@/components/ui/State';

export function BenchmarkPage() {
  const store = getStore(APP_MODE);
  const { data: profiles, loading: profilesLoading, error: profilesError, refetch } = useAsync(
    () => store.listProfiles(),
    []
  );
  const configs = store.listConfigs();
  const [profileId, setProfileId] = useState('');
  const [configName, setConfigName] = useState(configs[0]?.name ?? '');
  const [activeId, setActiveId] = useState<string | null>(store.getActiveRunId());
  const [activeRun, setActiveRun] = useState<BenchmarkRun | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (profiles && profiles.length > 0 && !profileId) {
      setProfileId(profiles[0].id);
    }
  }, [profiles, profileId]);

  useEffect(() => {
    if (!activeId) {
      setActiveRun(null);
      return;
    }
    store
      .getRun(activeId)
      .then(setActiveRun)
      .catch(() => setActiveId(null));
  }, [activeId, store]);

  usePolling(
    !!activeId && activeRun?.status === 'running',
    async () => {
      if (!activeId) return;
      try {
        const r = await store.getRun(activeId);
        setActiveRun(r);
        if (r.status !== 'running') {
          setActiveId(null);
        }
      } catch {
        // ignore
      }
    },
    1000
  );
  if (!canLaunch) {
    return (
      <div className="flex flex-col gap-6 animate-fadeIn">
        <h1 className="text-xl font-semibold text-text-primary tracking-tight">Launch benchmark</h1>
        <EmptyState
          title="Benchmark launch unavailable"
          description="Benchmarks can only be launched in local mode."
        />
      </div>
    );
  }

  if (profilesLoading) {
    return (
      <div className="flex flex-col gap-6 animate-fadeIn">
        <h1 className="text-xl font-semibold text-text-primary tracking-tight">Launch benchmark</h1>
        <Card>
          <SkeletonText lines={4} />
        </Card>
      </div>
    );
  }

  if (profilesError) {
    return (
      <div className="flex flex-col gap-6 animate-fadeIn">
        <h1 className="text-xl font-semibold text-text-primary tracking-tight">Launch benchmark</h1>
        <ErrorState onRetry={refetch} description="Could not load profiles." />
      </div>
    );
  }

  const availableProfiles = profiles ?? [];
  const selectedConfig = configs.find((c) => c.name === configName) ?? configs[0];

  const handleStart = async () => {
    if (!profileId || !selectedConfig) return;
    setStarting(true);
    setError(null);
    try {
      const run = await store.startBenchmark(profileId, selectedConfig);
      setActiveId(run.id);
      setActiveRun(run);
    } catch (e) {
      const err = e as ApiError;
      setError(String(err.detail ?? 'Failed to start benchmark'));
    } finally {
      setStarting(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 animate-fadeIn">
      <div>
        <h1 className="text-xl font-semibold text-text-primary tracking-tight">Launch benchmark</h1>
        <p className="text-sm text-text-secondary mt-1">
          Start a local benchmark run against a selected profile and config.
        </p>
      </div>

      {error && (
        <div className="rounded-md border border-status-failed-border bg-status-failed-bg px-4 py-2 text-sm text-status-failed-fg">
          {error}
        </div>
      )}

      {availableProfiles.length === 0 ? (
        <EmptyState
          title="No profiles available"
          description="Create a model profile before launching a benchmark."
          action={
            <Button size="md" variant="primary" onClick={() => navigate('/profiles')}>
              Manage profiles
            </Button>
          }
        />
      ) : (
        <>
          <Card>
            <CardHeader title="Launch configuration" />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Profile" required>
                <Select value={profileId} onChange={(e) => setProfileId(e.target.value)}>
                  {availableProfiles.map((p: ModelProfile) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.model_name})
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Benchmark config" required>
                <Select value={configName} onChange={(e) => setConfigName(e.target.value)}>
                  {configs.map((c: BenchmarkConfig) => (
                    <option key={c.name} value={c.name}>
                      {c.name}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
            <div className="mt-4">
              <Button
                variant="primary"
                leftIcon={starting ? <Loader2 className="h-4 w-4 animate-spin" /> : <FlaskConical className="h-4 w-4" />}
                loading={starting}
                disabled={!!activeId}
                onClick={handleStart}
              >
                {activeId ? 'Run in progress' : 'Start benchmark'}
              </Button>
            </div>
          </Card>

          {activeRun && (
            <Card>
              <CardHeader
                title="Active run"
                subtitle="Polling for status updates"
                action={<StatusBadge status={activeRun.status} />}
              />
              <div className="flex flex-col gap-2 text-sm">
                <p className="text-text-primary font-medium">{runProfileLabel(activeRun)}</p>
                <p className="text-xs text-text-muted font-mono">{activeRun.id}</p>
                <p className="text-xs text-text-muted">
                  Started {fmtDate(activeRun.started_at)} · {fmtElapsed(activeRun.started_at, activeRun.ended_at)}
                </p>
                {activeRun.events && activeRun.events.length > 0 && (
                  <ul className="mt-2 flex flex-col gap-1 text-xs text-text-secondary">
                    {activeRun.events.map((e, i) => (
                      <li key={i}>
                        {e.event}
                        {e.detail ? ` — ${e.detail}` : ''}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div className="mt-4 flex gap-2">
                {activeRun.status !== 'running' && (
                  <Button variant="ghost" onClick={() => navigate(`/runs/${activeRun.id}`)}>
                    View detail
                  </Button>
                )}
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
