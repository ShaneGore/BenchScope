import { useEffect, useSyncExternalStore } from 'react';

function getHashPath(): string {
  const h = window.location.hash.replace(/^#/, '');
  return h || '/';
}

function subscribe(cb: () => void): () => void {
  const onHash = () => cb();
  window.addEventListener('hashchange', onHash);
  return () => window.removeEventListener('hashchange', onHash);
}

export function useHashRoute(): string {
  return useSyncExternalStore(subscribe, getHashPath, () => '/');
}

export function navigate(to: string): void {
  const clean = to.startsWith('#') ? to.slice(1) : to;
  if (getHashPath() === clean) return;
  window.location.hash = clean;
}

export function linkProps(to: string) {
  return {
    href: `#${to}`,
    onClick: (e: React.MouseEvent) => {
      e.preventDefault();
      navigate(to);
    },
  };
}

export function parseRoute(path: string): { name: string; params: Record<string, string> } {
  const segments = path.split('?')[0].split('/').filter(Boolean);
  if (segments.length === 0) return { name: 'dashboard', params: {} };
  const [first, second] = segments;
  if (first === 'runs' && second) return { name: 'run-detail', params: { id: second } };
  if (first === 'runs') return { name: 'runs', params: {} };
  const known = [
    'dashboard',
    'compare',
    'profiles',
    'import',
    'benchmark',
    'demo',
    'sign-in',
    'sign-up',
  ];
  if (known.includes(first)) return { name: first, params: second ? { id: second } : {} };
  return { name: 'not-found', params: {} };
}

export function useScrollTopOnRoute(path: string) {
  useEffect(() => {
    if (typeof window === 'undefined' || /jsdom/i.test(navigator.userAgent)) return;
    try {
      window.scrollTo({ top: 0 });
    } catch {
      // ignore environments without scrollTo
    }
  }, [path]);
}
