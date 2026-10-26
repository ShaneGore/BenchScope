import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react';

interface FieldProps {
  label: string;
  error?: string;
  hint?: string;
  required?: boolean;
  children: ReactNode;
}

export function Field({ label, error, hint, required, children }: FieldProps) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-xs font-medium text-text-secondary flex items-center gap-1">
        {label}
        {required && <span className="text-status-failed-fg">*</span>}
      </span>
      {children}
      {hint && !error && (
        <span className="text-[11px] text-text-muted">{hint}</span>
      )}
      {error && (
        <span className="text-[11px] text-status-failed-fg">{error}</span>
      )}
    </label>
  );
}

const baseInput =
  'w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm text-text-primary placeholder:text-text-disabled focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500/40 transition-colors disabled:opacity-60 disabled:cursor-not-allowed';

export function TextInput({
  invalid,
  className = '',
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }) {
  return (
    <input
      className={`${baseInput} ${invalid ? 'border-status-failed-border' : ''} ${className}`}
      {...props}
    />
  );
}

export function TextArea({
  invalid,
  className = '',
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement> & { invalid?: boolean }) {
  return (
    <textarea
      className={`${baseInput} ${invalid ? 'border-status-failed-border' : ''} ${className}`}
      {...props}
    />
  );
}

export function Select({
  invalid,
  className = '',
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean }) {
  return (
    <select
      className={`${baseInput} ${invalid ? 'border-status-failed-border' : ''} ${className}`}
      {...props}
    >
      {children}
    </select>
  );
}
