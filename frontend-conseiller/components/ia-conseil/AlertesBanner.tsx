"use client";

import { AlertTriangle, Info, ShieldAlert } from "lucide-react";

import { cn } from "@/lib/utils";
import type { AlerteOut } from "@/lib/types-ia-conseil";

const STYLES: Record<AlerteOut["severite"], { classe: string; icone: typeof AlertTriangle }> = {
  critique: { classe: "border-destructive/50 bg-destructive/10 text-destructive", icone: ShieldAlert },
  attention: { classe: "border-amber-400/50 bg-amber-50 text-amber-900", icone: AlertTriangle },
  info: { classe: "border-slate-300 bg-slate-50 text-slate-700", icone: Info },
};

// Bandeau d'alertes (§Vision du rendu final : "attention : conso 8 Go mais
// forfait 200 Go proposé") — agrège les alertes de la meilleure offre
// recommandée (rang 1), la plus susceptible d'être réellement souscrite.
export function AlertesBanner({ alertes }: { alertes: AlerteOut[] }) {
  if (alertes.length === 0) return null;

  return (
    <div className="space-y-2">
      {alertes.map((alerte, index) => {
        const style = STYLES[alerte.severite] ?? STYLES.info;
        const Icone = style.icone;
        return (
          <div key={`${alerte.regle}-${index}`} className={cn("flex items-start gap-2 rounded-md border p-3 text-sm", style.classe)}>
            <Icone className="mt-0.5 h-4 w-4 shrink-0" />
            <p>{alerte.message}</p>
          </div>
        );
      })}
    </div>
  );
}
