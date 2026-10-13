"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { UserProfile } from "@/lib/api";

interface AuthContextValue {
  accessToken: string | null;
  user: UserProfile | null;
  establishSession: (accessToken: string, user: UserProfile) => void;
  clearSession: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserProfile | null>(null);

  const establishSession = useCallback(
    (token: string, profile: UserProfile) => {
      setAccessToken(token);
      setUser(profile);
    },
    [],
  );
  const clearSession = useCallback(() => {
    setAccessToken(null);
    setUser(null);
  }, []);
  const value = useMemo(
    () => ({ accessToken, user, establishSession, clearSession }),
    [accessToken, user, establishSession, clearSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider.");
  }
  return context;
}
