import type { ReactNode } from 'react';

export function ClerkProvider({ children }: { children: ReactNode }) {
  return children;
}

export function useAuth() {
  return {
    isLoaded: true,
    isSignedIn: false,
    userId: undefined,
    getToken: async () => null,
    signOut: async () => undefined,
  };
}

export function SignIn() {
  return <div>Clerk sign-in stub</div>;
}

export function SignUp() {
  return <div>Clerk sign-up stub</div>;
}
