import { AlertTriangle, CircleSlash, Clock, Loader2, XCircle } from 'lucide-react';
import type { RunStatus } from '@/types';

interface StatusBadgeProps {
  status: RunStatus;
  size?: 'sm' | 'md';
  showDot?: boolean;
}

const config: Record<
  RunStatus,
  { label: string; fg: string; bg: string; border: string; icon: typeof Clock; pulse?: boolean }
> = {
  completed: {
    label: 'Completed',
    fg: 'text-status-completed-fg',
    bg: 'bg-status-completed-bg',
    border: 'border-status-completed-border',
    icon: CircleSlash,
  },
  running: {
    label: 'Running',
    fg: 'text-status-running-fg',
    bg: 'bg-status-running-bg',
    border: 'border-status-running-border',
    icon: Loader2,
    pulse: true,
  },
  failed: {
    label: 'Failed',
    fg: 'text-status-failed-fg',
    bg: 'bg-status-failed-bg',
    border: 'border-status-failed-border',
    icon: XCircle,
  },
  interrupted: {
    label: 'Interrupted',
    fg: 'text-status-interrupted-fg',
    bg: 'bg-status-interrupted-bg',
    border: 'border-status-interrupted-border',
    icon: AlertTriangle,
  },
  cancelled: {
    label: 'Cancelled',
    fg: 'text-status-interrupted-fg',
    bg: 'bg-status-interrupted-bg',
    border: 'border-status-interrupted-border',
    icon: AlertTriangle,
  },
};

export function StatusBadge({ status, size = 'md', showDot = false }: StatusBadgeProps) {
  const c = config[status];
  const Icon = c.icon;
  const sz = size === 'sm' ? 'text-[11px] px-2 py-0.5 gap-1' : 'text-xs px-2.5 py-1 gap-1.5';
  const iconSz = size === 'sm' ? 'h-3 w-3' : 'h-3.5 w-3.5';
  return (
    <span
      className={`inline-flex items-center rounded-full border font-medium ${c.fg} ${c.bg} ${c.border} ${sz}`}
      role="status"
      aria-label={c.label}
    >
      {showDot ? (
        <span
          className={`inline-block rounded-full bg-current ${size === 'sm' ? 'h-1.5 w-1.5' : 'h-2 w-2'} ${c.pulse ? 'animate-pulseDot' : ''}`}
          aria-hidden
        />
      ) : (
        <Icon className={`${iconSz} ${c.pulse ? 'animate-spin' : ''}`} aria-hidden />
      )}
      {c.label}
    </span>
  );
}
