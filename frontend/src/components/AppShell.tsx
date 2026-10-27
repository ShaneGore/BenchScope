import type { ReactNode } from 'react';
import {
  Activity,
  BarChart3,
  FlaskConical,
  Gauge,
  LayoutDashboard,
  ListTree,
  Upload,
  UserCog,
} from 'lucide-react';
import { APP_MODE, canLaunch, isDemo, modeLabel } from '@/lib/mode';
import { linkProps, navigate, useScrollTopOnRoute } from '@/lib/router';
import { HostedAuthControls } from '@/auth/AuthBoundary';

interface NavItem {
  to: string;
  label: string;
  icon: typeof Gauge;
  localOnly?: boolean;
}

const navItems: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/runs', label: 'History', icon: ListTree },
  { to: '/compare', label: 'Compare', icon: BarChart3 },
  { to: '/profiles', label: 'Profiles', icon: UserCog },
  { to: '/import', label: 'Import', icon: Upload },
  { to: '/benchmark', label: 'Benchmark', icon: FlaskConical, localOnly: true },
];

const modeBadge: Record<string, { label: string; cls: string }> = {
  local: { label: 'LOCAL', cls: 'text-status-running-fg bg-status-running-bg border-status-running-border' },
  hosted: { label: 'HOSTED', cls: 'text-primary-500 bg-primary-500/10 border-primary-500/30' },
  demo: { label: 'DEMO', cls: 'text-status-interrupted-fg bg-status-interrupted-bg border-status-interrupted-border' },
};

export function AppShell({
  currentPath,
  children,
}: {
  currentPath: string;
  children: ReactNode;
}) {
  useScrollTopOnRoute(currentPath);
  const items = navItems.filter((n) => !n.localOnly || canLaunch);

  return (
    <div className="min-h-screen flex flex-col">
      <Header currentPath={currentPath} />
      <MobileNav currentPath={currentPath} />
      <div className="flex flex-1 min-h-0">
        <Sidebar items={items} currentPath={currentPath} />
        <main className="flex-1 min-w-0 overflow-x-hidden">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-6 lg:py-8">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}

function Header({ currentPath }: { currentPath: string }) {
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-canvas/85 backdrop-blur-md">
      <div className="flex h-14 items-center justify-between px-4 sm:px-6 lg:px-8">
        <button
          className="flex items-center gap-2.5"
          onClick={() => navigate('/')}
          aria-label="BenchScope home"
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-600 text-white shadow-sm shadow-primary-600/30">
            <Gauge className="h-4.5 w-4.5" strokeWidth={2.25} />
          </span>
          <span className="hidden sm:flex flex-col leading-none text-left">
            <span className="text-sm font-semibold text-text-primary">BenchScope</span>
            <span className="text-[10px] text-text-muted tracking-wide uppercase">
              Benchmark Observatory
            </span>
          </span>
        </button>

        <div className="flex items-center gap-3">
          <span
            className={`hidden sm:inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10px] font-semibold tracking-wider ${modeBadge[APP_MODE].cls}`}
          >
            {modeBadge[APP_MODE].label} MODE
          </span>
          {isDemo ? (
            <button
              {...linkProps('/demo')}
              className={`text-xs font-medium transition-colors ${
                currentPath.startsWith('/demo')
                  ? 'text-primary-500'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              Demo Data
            </button>
          ) : (
            <button
              {...linkProps('/demo')}
              className="text-xs text-text-muted hover:text-text-secondary transition-colors"
            >
              View Demo
            </button>
          )}
          {APP_MODE === 'hosted' && <HostedAuthControls />}
        </div>
      </div>
    </header>
  );
}

function Sidebar({
  items,
  currentPath,
}: {
  items: NavItem[];
  currentPath: string;
}) {
  const isActive = (to: string) =>
    to === '/' ? currentPath === '/' : currentPath.startsWith(to);

  return (
    <aside className="hidden md:flex w-56 shrink-0 flex-col border-r border-border bg-surface/40 py-4 px-3 gap-0.5 sticky top-14 self-start h-[calc(100vh-3.5rem)] overflow-y-auto">
      {items.map((item) => {
        const Icon = item.icon;
        const active = isActive(item.to);
        return (
          <button
            key={item.to}
            {...linkProps(item.to)}
            className={`flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-all ${
              active
                ? 'bg-surface-raised text-text-primary border border-border'
                : 'text-text-secondary hover:text-text-primary hover:bg-surface-raised/50 border border-transparent'
            }`}
            aria-current={active ? 'page' : undefined}
          >
            <Icon className={`h-4 w-4 ${active ? 'text-primary-500' : ''}`} />
            {item.label}
            {item.localOnly && (
              <span className="ml-auto text-[9px] text-status-running-fg/70 font-semibold tracking-wider">
                LOCAL
              </span>
            )}
          </button>
        );
      })}
      <div className="mt-auto pt-4">
        <div className="rounded-md border border-border bg-surface-raised/50 p-3">
          <div className="flex items-center gap-2 text-text-muted">
            <Activity className="h-3.5 w-3.5" />
            <span className="text-[11px] font-medium">Mode: {modeLabel[APP_MODE]}</span>
          </div>
          <p className="mt-1.5 text-[10px] text-text-disabled leading-snug">
            {isDemo
              ? 'Read-only synthetic dataset.'
              : canLaunch
                ? 'Full local workflow enabled.'
                : 'Import & compare only.'}
          </p>
        </div>
      </div>
    </aside>
  );
}

export function MobileNav({ currentPath }: { currentPath: string }) {
  const items = navItems.filter((n) => !n.localOnly || canLaunch);
  const isActive = (to: string) =>
    to === '/' ? currentPath === '/' : currentPath.startsWith(to);

  return (
    <nav className="md:hidden sticky top-14 z-30 border-b border-border bg-canvas/90 backdrop-blur-md overflow-x-auto">
      <div className="flex gap-1 px-3 py-2 min-w-max">
        {items.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.to);
          return (
            <button
              key={item.to}
              {...linkProps(item.to)}
              className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium whitespace-nowrap transition-colors ${
                active
                  ? 'bg-surface-raised text-text-primary'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {item.label}
            </button>
          );
        })}
      </div>
    </nav>
  );
}
