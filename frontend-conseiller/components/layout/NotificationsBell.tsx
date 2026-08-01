"use client";

import { Bell } from "lucide-react";
import { useRouter } from "next/navigation";

// Coquille du bouton de notifications : badge relances du jour, cliquable →
// dashboard. Le compte réel n'est pas câblé (aucun endpoint backend de
// relances du jour n'existe encore) — `count` reste à 0 en attendant que ce
// composant reçoive un compte via un hook React Query dédié.
export function NotificationsBell({ count = 0 }: { count?: number }) {
  const router = useRouter();

  return (
    <button
      onClick={() => router.push("/dashboard")}
      className="relative flex h-9 w-9 items-center justify-center rounded-md text-slate-600 hover:bg-slate-100"
      title="Relances du jour"
    >
      <Bell size={18} />
      {count > 0 && (
        <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 text-[10px] font-medium text-white">
          {count > 99 ? "99+" : count}
        </span>
      )}
    </button>
  );
}
