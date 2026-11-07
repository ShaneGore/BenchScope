import type { ReactNode } from 'react';
import { Inbox, TriangleAlert } from 'lucide-react';

export function StartupState() {
  return (
    <main className="p-8 text-sm text-text-secondary" role="status">
      Starting BenchScope. Please wait while the application loads.
    </main>
  );
}

export function DemoMethodology() {
  return (
    <details className="rounded-lg border border-border bg-surface/40 px-4 py-3">
      <summary className="cursor-pointer text-sm font-medium text-text-secondary">How to read these results</summary>
      <p className="mt-3 text-sm text-text-secondary leading-relaxed">
      Source: Local-LLM-Coding-Benchmark-v2. All 15 configurations record 47 of 47
      tasks; pass rate counts passed tasks. One Bonsai reasoning-on trial had a
      provider error. Throughput is mean output tokens per request-second for
      trials with a measured rate (46 for that run, otherwise 47 local trials).
      The two OpenRouter runs are hosted, not local, and have no throughput here.
      Settings differ, including MTP, reasoning and context; compare with care.
      Missing run timestamps are shown as unavailable.
      </p>
    </details>
  );
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden />;
}

export function SkeletonText({ lines = 3 }: { lines?: number }) {
  return (
    <div className="flex flex-col gap-2" aria-hidden>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className={i === lines - 1 ? 'h-3 w-2/3' : 'h-3 w-full'}
        />
      ))}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-16 px-6 animate-fadeIn">
      <div className="mb-4 text-text-muted">
        {icon ?? <Inbox className="h-10 w-10" strokeWidth={1.5} />}
      </div>
      <h3 className="text-base font-semibold text-text-primary mb-1.5">{title}</h3>
      {description && (
        <p className="text-sm text-text-secondary max-w-md mb-5 leading-relaxed">
          {description}
        </p>
      )}
      {action}
    </div>
  );
}

export function ErrorState({
  title = 'Something went wrong',
  description,
  onRetry,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-16 px-6 animate-fadeIn">
      <div className="mb-4 text-status-failed-fg">
        <TriangleAlert className="h-10 w-10" strokeWidth={1.5} />
      </div>
      <h3 className="text-base font-semibold text-text-primary mb-1.5">{title}</h3>
      <p className="text-sm text-text-secondary max-w-md mb-5 leading-relaxed">
        {description ?? 'A transient error occurred. Try again.'}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="text-sm text-primary-500 hover:text-primary-hover font-medium transition-colors"
        >
          Retry request
        </button>
      )}
    </div>
  );
}

export function Alert({
  variant = 'info',
  title,
  children,
  icon,
  action,
}: {
  variant?: 'info' | 'warning' | 'error' | 'success';
  title?: string;
  children?: ReactNode;
  icon?: ReactNode;
  action?: ReactNode;
}) {
  const styles = {
    info: 'border-primary-500/30 bg-primary-500/10 text-primary-500',
    warning:
      'border-status-interrupted-border bg-status-interrupted-bg text-status-interrupted-fg',
    error: 'border-status-failed-border bg-status-failed-bg text-status-failed-fg',
    success:
      'border-status-completed-border bg-status-completed-bg text-status-completed-fg',
  }[variant];
  return (
    <div
      className={`flex items-start gap-3 rounded-lg border px-4 py-3 text-sm ${styles}`}
      role="alert"
    >
      {icon && <span className="shrink-0 mt-0.5">{icon}</span>}
      <div className="flex-1 min-w-0">
        {title && <p className="font-semibold mb-0.5">{title}</p>}
        {children && <div className="text-sm opacity-90">{children}</div>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
