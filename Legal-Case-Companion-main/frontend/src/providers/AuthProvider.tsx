"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { apiClient } from "@/api/client";

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
  login: (token: string, user: User) => void;
  logout: () => Promise<void>;
  checkSession: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  login: () => {},
  logout: async () => {},
  checkSession: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const checkSession = useCallback(async () => {
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem("access_token") : null;
      if (token) {
        let baseUser: User | null = null;
        try {
          const payload = JSON.parse(atob(token.split('.')[1]));
          baseUser = {
            id: payload.sub,
            email: payload.email || "",
            role: (payload.role as UserRole) || "CLIENT",
            account_status: "ACTIVE"
          };
          setUser(baseUser);
        } catch {
          // Token decode failed
        }

        // Validate token against backend authoritative profile endpoint
        try {
          const profile = await apiClient.get("/api/v1/profiles/me");
          if (profile) {
            setUser({
              id: profile.user_id || baseUser?.id || profile.id,
              email: baseUser?.email || "",
              role: baseUser?.role || "CLIENT",
              account_status: "ACTIVE",
              full_name: profile.full_name,
              location: profile.location,
            });
          }
        } catch (profileErr) {
          console.warn("Could not fetch user profile:", profileErr);
        }
      } else {
        setUser(null);
      }
    } catch (e) {
      console.error("Session check failed", e);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      void checkSession();
    }, 0);

    const handleSessionExpired = () => {
      setUser(null);
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.href = "/login?expired=1";
      }
    };

    window.addEventListener("lcc:session-expired", handleSessionExpired);

    return () => {
      clearTimeout(timer);
      window.removeEventListener("lcc:session-expired", handleSessionExpired);
    };
  }, [checkSession]);

  const login = (token: string, userObj: User) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem("access_token", token);
    }
    setUser(userObj);
  };

  const logout = async () => {
    try {
      await apiClient.post("/api/v1/auth/logout", {});
    } catch (e) {
      console.error(e);
    }
    if (typeof window !== 'undefined') {
      localStorage.removeItem("access_token");
    }
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, checkSession }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);

