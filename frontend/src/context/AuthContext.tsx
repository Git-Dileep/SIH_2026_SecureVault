import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';

export type UserRole = 'admin' | 'employee';

export interface User {
  name: string;
  email: string;
  initials: string;
  role: UserRole;
}

interface AuthContextValue {
  user: User;
  isAdmin: boolean;
  setRole: (role: UserRole) => void;
}

const DEFAULT_USER: User = {
  name: 'Local Operator',
  email: 'operator@securevault.local',
  initials: 'LO',
  role: (localStorage.getItem('sv_role') as UserRole) || 'admin',
};

const AuthContext = createContext<AuthContextValue | null>(null);

/**
 * Simulated auth provider for hackathon demo.
 * Stores role in localStorage so it persists across reloads.
 * Drop-in replacement point for real Clerk integration later.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User>(DEFAULT_USER);

  const setRole = useCallback((role: UserRole) => {
    localStorage.setItem('sv_role', role);
    setUser((prev) => ({ ...prev, role }));
  }, []);

  return (
    <AuthContext.Provider value={{ user, isAdmin: user.role === 'admin', setRole }}>
      {children}
    </AuthContext.Provider>
  );
}

/**
 * Hook to access the current user and role.
 * Throws if used outside AuthProvider.
 */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within <AuthProvider>');
  }
  return ctx;
}
