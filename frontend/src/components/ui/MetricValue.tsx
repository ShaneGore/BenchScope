import type { ReactNode } from 'react';

interface MetricValueProps {
  label: string;
  value: ReactNode;
  unit?: string;
  available?: boolean;
  hint?: string;
}

export function MetricValue({ label, value, unit, available = true, hint }: MetricValueProps) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[11px] uppercase tracking-wide text-text-muted font-medium">
        {label}
      </span>
      <span
        className={`font-mono tabular-nums text-base ${available ? 'text-text-primary' : 'text-unavailable'}`}
        title={available ? hint : 'Unavailable'}
      >
        {available ? (
          <>
            {value}
            {unit && <span className="text-text-muted ml-1 text-xs font-sans">{unit}</span>}
          </>
        ) : (
          'Unavailable'
        )}
      </span>
      {hint && available && (
        <span className="text-[11px] text-text-muted leading-tight">{hint}</span>
      )}
    </div>
  );
}

export function MetricGrid({
  children,
  cols = 3,
}: {
  children: ReactNode;
  cols?: 2 | 3 | 4;
}) {
  const gridCols = {
    2: 'grid-cols-2 sm:grid-cols-2',
    3: 'grid-cols-2 sm:grid-cols-3',
    4: 'grid-cols-2 sm:grid-cols-4',
  }[cols];
  return <div className={`grid ${gridCols} gap-4`}>{children}</div>;
}
