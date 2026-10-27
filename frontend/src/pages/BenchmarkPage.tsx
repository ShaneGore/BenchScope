import { useEffect, useState } from 'react';
import { FlaskConical, Loader2 } from 'lucide-react';
import type {
  ApiError,
  BenchmarkConfig,
  BenchmarkRun,
  ModelProfile,
} from '@/types';
import { getStore } from '@/mock/store';
import { getBenchmarkService } from '@/services/benchmark-service';
import { LocalRunnerService, type RunnerStatus } from '@/services/runner-service';
import { APP_MODE } from '@/lib/mode';
import { navigate } from '@/lib/router';
import { useAsync, usePolling } from '@/lib/hooks';
import { fmtDate, fmtElapsed } from '@/lib/format';
import { runProfileLabel } from '@/lib/metrics';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { Field, Select } from '@/components/ui/Field';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { EmptyState, ErrorState, SkeletonText } from '@/components/ui/State';

export function BenchmarkPage({ runnerEnabled = false }: { runnerEnabled?: boolean }) {
  if (APP_MODE !== 'local' || !runnerEnabled) return null;
  return <EnabledBenchmarkPage />;
}

function EnabledBenchmarkPage() {
  const service = getBenchmarkService('local');
  const runner = new LocalRunnerService();
  const configs = getStore('local').listConfigs();
  const { data: profiles, loading, error: profilesError, refetch } = useAsync(
    () => service.listProfiles(),
    []
  );
  const [profileId, setProfileId] = useState('');
  const [configName, setConfigName] = useState(configs[0]?.name ?? '');
  const [activeId, setActiveId] = useState<string | null>(null);
  const [activeRun, setActiveRun] = useState<BenchmarkRun | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (profiles?.length && !profileId) setProfileId(profiles[0].id);
  }, [profiles, profileId]);

  const selectedProfile = profiles?.find((profile) => profile.id === profileId);
  const selectedConfig = configs.find((config) => config.name === configName) ?? configs[0];

  const refreshStatus = async (id: string) => {
    try {
      const status = await runner.status(id);
      const profile = selectedProfile ?? profiles?.[0];
      if (profile) setActiveRun(mapRunnerStatus(status, profile, selectedConfig));
      if (status.status !== 'running') setActiveId(null);
    } catch (e) {
      setError(String((e as ApiError).detail ?? 'Could not load benchmark status.'));
      setActiveId(null);
    }
  };

  useEffect(() => {
    if (activeId) void refreshStatus(activeId);
  }, [activeId]);

  usePolling(
    !!activeId && activeRun?.status === 'running',
    async () => {
      if (activeId) await refreshStatus(activeId);
    },
    1000
  );

  if (loading) {
    return (
      <div className="flex flex-col gap-6 animate-fadeIn">
        <h1 className="text-xl font-semibold text-text-primary tracking-tight">Launch benchmark</h1>
        <Card><SkeletonText lines={4} /></Card>
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
  const handleStart = async () => {
    if (!selectedProfile || !selectedConfig) return;
    setStarting(true);
    setError(null);
    try {
      const run = await runner.start(
        selectedProfile.id,
        globalThis.crypto?.randomUUID?.() ?? '00000000-0000-4000-8000-000000000001'
      );
      setActiveId(run.id);
      setActiveRun({
        id: run.id,
        owner_id: selectedProfile.owner_id,
        status: 'running',
        profile_snapshot: {
          profile_id: selectedProfile.id,
          name: selectedProfile.name,
          model_name: selectedProfile.model_name,
          quantization: selectedProfile.quantization,
          context_length: selectedProfile.context_length,
          inference_engine: selectedProfile.inference_engine,
        },
        benchmark_config: selectedConfig,
        started_at: new Date().toISOString(),
        metrics: {},
        source: 'launched',
      });
    } catch (e) {
      setError(String((e as ApiError).detail ?? 'Failed to start benchmark'));
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
                  {availableProfiles.map((profile: ModelProfile) => (
                    <option key={profile.id} value={profile.id}>
                      {profile.name} ({profile.model_name})
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Benchmark config" required>
                <Select value={configName} onChange={(e) => setConfigName(e.target.value)}>
                  {configs.map((config: BenchmarkConfig) => (
                    <option key={config.name} value={config.name}>{config.name}</option>
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
              </div>
              {activeRun.status !== 'running' && (
                <div className="mt-4">
                  <Button variant="ghost" onClick={() => navigate(`/runs/${activeRun.id}`)}>
                    View detail
                  </Button>
                </div>
              )}
            </Card>
          )}
        </>
      )}
    </div>
  );
}

function mapRunnerStatus(
  status: RunnerStatus,
  profile: ModelProfile,
  config: BenchmarkConfig
): BenchmarkRun {
  return {
    id: status.id,
    owner_id: profile.owner_id,
    status: status.status,
    profile_snapshot: {
      profile_id: profile.id,
      name: profile.name,
      model_name: profile.model_name,
      quantization: profile.quantization,
      context_length: profile.context_length,
      inference_engine: profile.inference_engine,
    },
    benchmark_config: config,
    started_at: status.started_at,
    ended_at: status.completed_at,
    metrics: status.metrics,
    error_category: status.error_category as BenchmarkRun['error_category'],
    error_message_sanitised: status.error_message_sanitised,
    source: 'launched',
  };
}
