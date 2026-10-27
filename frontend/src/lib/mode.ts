import type { AppMode } from '@/types';

const RAW_MODE = (import.meta.env.VITE_APP_MODE ?? 'local') as string;

function normalize(m: string): AppMode {
  if (m === 'hosted' || m === 'demo') return m;
  return 'local';
}

export const APP_MODE: AppMode = normalize(RAW_MODE);

export const modeLabel: Record<AppMode, string> = {
  local: 'Local',
  hosted: 'Hosted',
  demo: 'Demo',
};

export const canLaunch = APP_MODE === 'local';
export const canImport = APP_MODE !== 'demo';
export const canEditProfiles = APP_MODE !== 'demo';
export const canDelete = APP_MODE !== 'demo';
export const canRetry = APP_MODE === 'local';
export const showEndpointFields = APP_MODE === 'local';
export const isDemo = APP_MODE === 'demo';
export const isHosted = APP_MODE === 'hosted';
export const isLocal = APP_MODE === 'local';
