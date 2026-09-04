"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { apiClient, performTokenRefresh } from "@/api/client";
import {
  getTabSessionId,
  getSessionAccessToken,
  setSessionAccessToken,
  getSessionRefreshToken,
  setSessionRefreshToken,
  clearTabSession,
  purgeLegacyGlobalStorage,
} from "@/api/session";

export type UserRole = "CLIENT" | "LAWYER" | "ADMIN";

export interface User {
  id: string;
  email: string;
  role: UserRole;
  account_status: string;
  full_name?: string;
  location?: string | null;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (token: string, user: User, refreshToken?: string) => void;
  logout: () => Promise<void>;
  checkSession: () => Promise<void>;
  refreshSession: () => Promise<boolean>;
  getCurrentSessionId: () => string;
  getCurrentAccessToken: () => string | null;
  setCurrentAccessToken: (token: string) => void;
  clearCurrentAccessToken: () => void;
  getAuthenticatedUser: () => User | null;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  login: () => {},
  logout: async () => {},
  checkSession: async () => {},
  refreshSession: async () => false,
  getCurrentSessionId: () => "ssr-session",
  getCurrentAccessToken: () => null,
  setCurrentAccessToken: () => {},
  clearCurrentAccessToken: () => {},
  getAuthenticatedUser: () => null,
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const checkSession = useCallback(async () => {
    try {
      const token = getSessionAccessToken();
      if (token) {
        let decodedRole: UserRole | null = null;
        let decodedId: string | null = null;
        let decodedEmail: string | null = null;

        try {
          const payload = JSON.parse(atob(token.split(".")[1]));
          if (
            payload.role &&
            (payload.role === "CLIENT" || payload.role === "LAWYER" || payload.role === "ADMIN")
          ) {
            decodedRole = payload.role as UserRole;
          }
          if (payload.sub) decodedId = payload.sub;
          if (payload.email) decodedEmail = payload.email;
        } catch {
          // Token decode failed - wait for server validation
        }

        // Fast optimistic paint if valid claims exist
        if (decodedRole && decodedId) {
          setUser({
            id: decodedId,
            email: decodedEmail || "",
            role: decodedRole,
            account_status: "ACTIVE",
          });
        }

        // Authoritative verification against backend /api/v1/auth/me
        try {
          const me = (await apiClient.get("/api/v1/auth/me")) as {
            id: string;
            email: string;
            role: UserRole;
            account_status: string;
            full_name?: string;
            location?: string | null;
          };

          if (me && me.role && (me.role === "CLIENT" || me.role === "LAWYER" || me.role === "ADMIN")) {
            setUser({
              id: me.id,
              email: me.email,
              role: me.role,
              account_status: me.account_status || "ACTIVE",
              full_name: me.full_name,
              location: me.location,
            });
          } else {
            // Missing or invalid role from server is an invalid auth state (never default to CLIENT)
            console.warn("[LCC-Auth] Authoritative identity returned invalid role:", me);
            clearTabSession();
            setUser(null);
          }
        } catch (meErr: any) {
          console.warn("[LCC-Auth] Could not fetch authoritative identity:", meErr);
          if (meErr?.status === 401 || meErr?.status === 403) {
            clearTabSession();
            setUser(null);
          }
        }
      } else {
        setUser(null);
      }
    } catch (e) {
      console.error("[LCC-Auth] Session check failed:", e);
      clearTabSession();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshSession = useCallback(async (): Promise<boolean> => {
    try {
      const newToken = await performTokenRefresh();
      if (newToken) {
        await checkSession();
        return true;
      }
      return false;
    } catch (err) {
      console.warn("[LCC-Auth] refreshSession error:", err);
      return false;
    }
  }, [checkSession]);

  useEffect(() => {
    // Purge legacy browser-wide localStorage keys once on mount
    purgeLegacyGlobalStorage();

    const sessionId = getTabSessionId();

    const timer = setTimeout(() => {
      void checkSession();
    }, 0);

    const handleSessionExpired = (e: Event) => {
      const customEvent = e as CustomEvent<{ sessionId?: string }>;
      if (customEvent.detail?.sessionId && customEvent.detail.sessionId !== sessionId) {
        // Event is explicitly for a different browser tab session
        return;
      }

      clearTabSession();
      setUser(null);
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.href = "/login?expired=1";
      }
    };

    window.addEventListener(`lcc:session-expired:${sessionId}`, handleSessionExpired);
    window.addEventListener("lcc:session-expired", handleSessionExpired);

    return () => {
      clearTimeout(timer);
      window.removeEventListener(`lcc:session-expired:${sessionId}`, handleSessionExpired);
      window.removeEventListener("lcc:session-expired", handleSessionExpired);
    };
  }, [checkSession]);

  const login = (token: string, userObj: User, refreshToken?: string) => {
    setSessionAccessToken(token);
    if (refreshToken) {
      setSessionRefreshToken(refreshToken);
    }
    setUser(userObj);
  };

  const logout = async () => {
    try {
      const refreshToken = getSessionRefreshToken();
      await apiClient.post("/api/v1/auth/logout", { refresh_token: refreshToken });
    } catch (e) {
      console.warn("[LCC-Auth] Logout API call failed:", e);
    } finally {
      // Only clears current tab's session
      clearTabSession();
      setUser(null);
    }
  };

  const getCurrentSessionId = useCallback(() => getTabSessionId(), []);
  const getCurrentAccessToken = useCallback(() => getSessionAccessToken(), []);
  const setCurrentAccessToken = useCallback((token: string) => setSessionAccessToken(token), []);
  const clearCurrentAccessToken = useCallback(() => clearTabSession(), []);
  const getAuthenticatedUser = useCallback(() => user, [user]);

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        logout,
        checkSession,
        refreshSession,
        getCurrentSessionId,
        getCurrentAccessToken,
        setCurrentAccessToken,
        clearCurrentAccessToken,
        getAuthenticatedUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
