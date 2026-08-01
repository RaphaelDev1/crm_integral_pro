"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/contexts/AuthContext";

// Garde d'affichage partagée par toutes les pages /admin/* — le backend
// revalide toujours le rôle sur chaque endpoint admin (require_role("Admin")),
// ce garde ne fait que masquer l'UI et rediriger en cas d'accès direct par URL.
export function AdminGuard({ children }: { children: React.ReactNode }) {
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

  return <>{children}</>;
}
