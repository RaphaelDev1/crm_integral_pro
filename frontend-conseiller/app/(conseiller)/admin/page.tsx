"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/contexts/AuthContext";

// Gate supplémentaire par rapport aux 5 autres sections : accessible aux
// seuls comptes "Admin" (le lien est déjà masqué dans la Sidebar, ce garde
// couvre l'accès direct par URL). Rappel : aide d'affichage, le backend
// revalide le rôle sur chaque endpoint admin.
export default function AdminPage() {
  const { estAdmin } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!estAdmin()) {
      router.replace("/dashboard");
    }
  }, [estAdmin, router]);

  if (!estAdmin()) {
    return null;
  }

  return (
    <div>
      <h1 className="text-xl font-bold text-primary mb-2">Admin</h1>
      <p className="text-sm text-slate-500">Section en construction.</p>
    </div>
  );
}
