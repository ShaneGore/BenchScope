import { useEffect, useState } from 'react';
import { useAuth } from '@clerk/react';
import { AppShell } from '@/components/AppShell';
import { useHashRoute, parseRoute, navigate } from '@/lib/router';
import { APP_MODE } from '@/lib/mode';
import { DashboardPage } from '@/pages/DashboardPage';
import { RunsPage } from '@/pages/RunsPage';
import { RunDetailPage } from '@/pages/RunDetailPage';
import { ComparePage } from '@/pages/ComparePage';
import { ProfilesPage } from '@/pages/ProfilesPage';
import { ImportPage } from '@/pages/ImportPage';
import { BenchmarkPage } from '@/pages/BenchmarkPage';
import { SignIn, SignUp } from '@clerk/react';
import { getBenchmarkCapability } from '@/services/runner-service';

function SignInPage() {
  if (APP_MODE === 'hosted') {
    return <SignIn routing="hash" signUpUrl="/sign-up" />;
  }
  return (
    <div className="flex flex-col gap-6 animate-fadeIn">
      <h1 className="text-xl font-semibold text-text-primary tracking-tight">Sign in</h1>
      <p className="text-sm text-text-secondary">
        Hosted authentication is not wired in this mock build. In production this route is handled by
        Clerk. Current mode: {APP_MODE}.
      </p>
    </div>
  );
}

function SignUpPage() {
  if (APP_MODE === 'hosted') {
    return <SignUp routing="hash" signInUrl="/sign-in" />;
  }
  return (
    <div className="flex flex-col gap-6 animate-fadeIn">
      <h1 className="text-xl font-semibold text-text-primary tracking-tight">Sign up</h1>
      <p className="text-sm text-text-secondary">
        Hosted authentication is not wired in this mock build. In production this route is handled by
        Clerk. Current mode: {APP_MODE}.
      </p>
    </div>
  );
}

function NotFoundPage() {
  return (
    <div className="flex flex-col gap-6 animate-fadeIn">
      <h1 className="text-xl font-semibold text-text-primary tracking-tight">Page not found</h1>
      <p className="text-sm text-text-secondary">The requested route does not exist.</p>
    </div>
  );
}

function getQuery(path: string): Record<string, string> {
  const q = path.split('?')[1];
  if (!q) return {};
  const params: Record<string, string> = {};
  q.split('&').forEach((pair) => {
    const [k, v] = pair.split('=');
    if (k) params[decodeURIComponent(k)] = decodeURIComponent(v ?? '');
  });
  return params;
}

export default function App() {
  return APP_MODE === 'hosted' ? <HostedApp /> : <ModeApp />;
}

function ModeApp() {
  const path = useHashRoute();
  const [capability, setCapability] = useState<boolean | null>(
    APP_MODE === 'local' ? null : false
  );

  useEffect(() => {
    if (APP_MODE === 'local') {
      void getBenchmarkCapability().then(setCapability);
    }
  }, []);

  useEffect(() => {
    if (path === '/benchmark' && APP_MODE === 'local' && capability === false) {
      navigate('/');
    }
  }, [path, capability]);

  return (
    <AppRoutes
      path={path}
      runnerEnabled={capability === true}
      publicOnly={APP_MODE === 'demo' || path.startsWith('/demo')}
    />
  );
}

function HostedApp() {
  const { isLoaded, isSignedIn } = useAuth();
  const path = useHashRoute();
  const route = parseRoute(path);
  const protectedRoute = [
    'dashboard',
    'runs',
    'run-detail',
    'compare',
    'profiles',
    'import',
  ].includes(route.name);
  const redirect =
    route.name === 'benchmark'
      ? isSignedIn
        ? '/'
        : '/demo'
      : !isSignedIn && route.name === 'dashboard'
        ? '/demo'
        : !isSignedIn && protectedRoute
          ? '/sign-in'
          : null;

  useEffect(() => {
    if (isLoaded && redirect) navigate(redirect);
  }, [isLoaded, redirect]);

  if (!isLoaded || redirect) return null;
  return <AppRoutes path={path} runnerEnabled={false} publicOnly={!isSignedIn} />;
}

function AppRoutes({
  path,
  runnerEnabled,
  publicOnly,
}: {
  path: string;
  runnerEnabled: boolean;
  publicOnly: boolean;
}) {
  const route = parseRoute(path);
  const query = getQuery(path);

  let page: React.ReactNode = null;
  switch (route.name) {
    case 'dashboard':
      page = <DashboardPage benchmarkEnabled={runnerEnabled} />;
      break;
    case 'demo':
      page = <DashboardPage serviceMode="demo" />;
      break;
    case 'demo-run-detail':
      page = <RunDetailPage id={route.params.id} serviceMode="demo" />;
      break;
    case 'runs':
      page = <RunsPage initialStatus={query.status} />;
      break;
    case 'run-detail':
      page = <RunDetailPage id={route.params.id} runnerEnabled={runnerEnabled} />;
      break;
    case 'compare': {
      const ids = (query.ids ?? '').split(',').filter(Boolean);
      page = <ComparePage ids={ids} />;
      break;
    }
    case 'profiles':
      page = <ProfilesPage />;
      break;
    case 'import':
      page = <ImportPage />;
      break;
    case 'benchmark':
      page = runnerEnabled ? <BenchmarkPage runnerEnabled /> : null;
      break;
    case 'sign-in':
      page = <SignInPage />;
      break;
    case 'sign-up':
      page = <SignUpPage />;
      break;
    default:
      page = <NotFoundPage />;
  }

  return (
    <AppShell
      currentPath={path}
      launchEnabled={APP_MODE === 'local' && runnerEnabled}
      publicOnly={publicOnly || APP_MODE === 'demo' || path.startsWith('/demo')}
    >
      {page}
    </AppShell>
  );
}
