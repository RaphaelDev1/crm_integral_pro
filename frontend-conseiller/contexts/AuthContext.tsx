"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { backendFetch } from "@/lib/backend-fetch";

export interface AuthUser {
  id: number;
  username: string;
  nom_complet: string;
  role: string;
  actif: boolean;
  doit_changer_mdp: boolean;
}

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  // Mêmes règles que src/app.py:248-256 (peut_modifier/est_admin) : aides
  // d'affichage pour l'UX, jamais une frontière de sécurité — le backend
  // revalide toujours les permissions sur chaque endpoint.
  peutModifier: () => boolean;
  estAdmin: () => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    try {
      const res = await backendFetch("/auth/me");
      setUser(res.ok ? await res.json() : null);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const login = useCallback(async (username: string, password: string) => {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      throw new Error(data?.detail || "Identifiant ou mot de passe incorrect.");
    }
    setUser(data.user);
  }, []);

  const logout = useCallback(async () => {
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => {});
    setUser(null);
  }, []);

  const peutModifier = useCallback(() => user?.role === "Conseiller" || user?.role === "Admin", [user]);
  const estAdmin = useCallback(() => user?.role === "Admin", [user]);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, peutModifier, estAdmin }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth doit être utilisé à l'intérieur de <AuthProvider>.");
  return ctx;
}
