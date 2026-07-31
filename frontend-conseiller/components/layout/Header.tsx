"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/contexts/AuthContext";

export function Header() {
  const { user, logout } = useAuth();
  const router = useRouter();

  async function onLogout() {
    await logout();
    router.replace("/login");
  }

  return (
    <header className="h-14 shrink-0 bg-white border-b border-slate-200 flex items-center justify-end gap-4 px-6">
      <div className="text-sm text-right">
        <p className="font-medium text-slate-800">{user?.nom_complet}</p>
        <p className="text-xs text-slate-500">{user?.role}</p>
      </div>
      <button
        onClick={onLogout}
        className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm text-slate-600 hover:bg-slate-100"
        title="Déconnexion"
      >
        <LogOut size={16} />
        Déconnexion
      </button>
    </header>
  );
}
