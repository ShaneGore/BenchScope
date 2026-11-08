import { ErrorState, StartupState } from '@/components/ui/State';
import { ClerkProvider, useAuth } from '@clerk/react';
import { useCallback, useEffect, useLayoutEffect, useState, type ReactNode } from 'react';
import { resetStore } from '@/mock/store';
import { APP_MODE } from '@/lib/mode';
import { setApiSessionTokenProvider } from '@/services/api-benchmark-service';

const publishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

export function AuthBoundary({ children }: { children: ReactNode }) {
  if (APP_MODE !== 'hosted') return children;
  if (!publishableKey) {
    return (
      <main role="alert" className="p-8 text-text-primary">
        Clerk authentication is not configured for hosted mode.
      </main>
    );
  }
  return <ClerkStartup publishableKey={publishableKey}>{children}</ClerkStartup>;
}

function ClerkStartup({ children, publishableKey }: { children: ReactNode; publishableKey: string }) {
  const [attempt, setAttempt] = useState(0);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (ready) return;
    const timer = window.setTimeout(() => setFailed(true), 30000);
    return () => window.clearTimeout(timer);
  }, [attempt, ready]);
  const onReady = useCallback((value: boolean) => setReady(value), []);
  if (failed) return <ErrorState title="Authentication could not start" description="Authentication took too long to start. Please retry." onRetry={() => {
    setReady(false);
    setFailed(false);
    setAttempt((value) => value + 1);
  }} />;
  return (
    <>
      {!ready && <StartupState />}
      <ClerkProvider key={attempt} publishableKey={publishableKey}>
        <ClerkSession onReady={onReady}>{children}</ClerkSession>
      </ClerkProvider>
    </>
  );
}

function ClerkSession({ children, onReady }: { children: ReactNode; onReady: (value: boolean) => void }) {
  const { getToken, isLoaded, isSignedIn, userId, sessionId } = useAuth();
  const identity = isSignedIn ? `${userId ?? ''}:${sessionId ?? ''}` : null;
  const [activeUserId, setActiveUserId] = useState<string | null>();
  const [signingOut, setSigningOut] = useState(false);

  useLayoutEffect(() => {
    const hide = () => setSigningOut(true);
    const restore = () => {
      if (isSignedIn) setApiSessionTokenProvider(() => getToken());
      setSigningOut(false);
    };
    window.addEventListener('benchscope-sign-out', hide);
    window.addEventListener('benchscope-sign-out-failed', restore);
    return () => {
      window.removeEventListener('benchscope-sign-out', hide);
      window.removeEventListener('benchscope-sign-out-failed', restore);
    };
  }, [getToken, isSignedIn]);

  useLayoutEffect(() => {
    if (!isLoaded) {
      onReady(false);
      return;
    }
    setApiSessionTokenProvider(undefined);
    resetStore('hosted');
    if (isSignedIn) setApiSessionTokenProvider(() => getToken());
    setActiveUserId(identity);
    setSigningOut(false);
    onReady(true);
    return () => {
      setApiSessionTokenProvider(undefined);
      resetStore('hosted');
    };
  }, [getToken, isLoaded, isSignedIn, identity, onReady]);

  if (!isLoaded || signingOut || activeUserId !== identity) return null;
  // A new identity gets a fresh component tree and no prior mock/server state.
  return <div key={identity ?? 'signed-out'}>{children}</div>;
}

export function HostedAuthControls() {
  const { isLoaded, isSignedIn, signOut } = useAuth();
  if (!isLoaded) return null;

  if (!isSignedIn) {
    return (
      <button
        className="text-xs font-medium text-primary-500 hover:text-primary-400"
        onClick={() => {
          window.location.hash = '/sign-in';
        }}
      >
        Sign in
      </button>
    );
  }

  return (
    <button
      className="text-xs font-medium text-text-secondary hover:text-text-primary"
      onClick={async () => {
        window.dispatchEvent(new Event('benchscope-sign-out'));
        resetStore('hosted');
        setApiSessionTokenProvider(undefined);
        try {
          await signOut({
            redirectUrl: `${window.location.origin}${window.location.pathname}#/sign-in`,
          });
        } catch {
          window.dispatchEvent(new Event('benchscope-sign-out-failed'));
        }
      }}
    >
      Sign out
    </button>
  );
}
