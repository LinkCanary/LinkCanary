import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { getSession, signOut as authSignOut } from '../services/auth';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const s = await getSession();
    setSession(s);
    setLoading(false);
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const logout = useCallback(async () => {
    await authSignOut();
    setSession(null);
    window.location.href = '/login';
  }, []);

  return (
    <AuthContext.Provider value={{ session, loading, refresh, logout, isAuthenticated: !!session }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
