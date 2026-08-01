"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { CommandPalette } from "@/components/layout/CommandPalette";
import { Header } from "@/components/layout/Header";
import { Sidebar } from "@/components/layout/Sidebar";
import { useAuth } from "@/contexts/AuthContext";

// Le middleware (cookie présent) a déjà filtré la navigation en amont ; ce
// garde couvre le cas d'un cookie présent mais invalide/expiré (middleware
// ne vérifie pas la signature) — /auth/me renvoie alors user=null.
export default function ConseillerLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, user, router]);

  if (loading || !user) {
    return <div className="min-h-screen flex items-center justify-center text-sm text-slate-500">Chargement…</div>;
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <Header />
        <main className="flex-1 p-6">{children}</main>
      </div>
      <CommandPalette />
    </div>
  );
}
