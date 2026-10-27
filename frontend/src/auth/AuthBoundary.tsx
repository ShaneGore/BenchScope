import { ClerkProvider, useAuth } from '@clerk/react';
import { useLayoutEffect, type ReactNode } from 'react';
import { resetStore } from '@/mock/store';
import { APP_MODE } from '@/lib/mode';
import { setApiSessionTokenProvider } from '@/services/api-benchmark-service';

const publishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

export function AuthBoundary({ children }: { children: ReactNode }) {
  if (APP_MODE !== 'hosted') return children;
  if (!publishableKey) {
    return (
      <main className="p-8 text-text-primary">
        Clerk authentication is not configured for hosted mode.
      </main>
    );
  }
  return (
    <ClerkProvider publishableKey={publishableKey}>
      <ClerkSession>{children}</ClerkSession>
    </ClerkProvider>
  );
}

function ClerkSession({ children }: { children: ReactNode }) {
  const { getToken, userId } = useAuth();

  useLayoutEffect(() => {
    setApiSessionTokenProvider(() => getToken());
    resetStore('hosted');
    return () => {
      setApiSessionTokenProvider(undefined);
      resetStore('hosted');
    };
  }, [getToken, userId]);

  // A new identity gets a fresh component tree and no prior mock/server state.
  return <div key={userId ?? 'signed-out'}>{children}</div>;
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
        resetStore('hosted');
        setApiSessionTokenProvider(undefined);
        await signOut({
          redirectUrl: `${window.location.origin}${window.location.pathname}#/sign-in`,
        });
      }}
    >
      Sign out
    </button>
  );
}
