"use client";

import { TrendingDown } from "lucide-react";

// Colonne droite : "gros chiffre" d'économie annuelle estimée (§Vision du
// rendu final / §1.2 EconomieTicker.tsx). `economieAnnuelle` est null tant
// que le client n'a pas déclaré son coût actuel (question
// "cout_actuel_mensuel", voir ia_conseil_engine.calculer_recommandations) —
// on l'indique plutôt que d'afficher un faux zéro.
export function EconomieTicker({ economieAnnuelle }: { economieAnnuelle: number | null }) {
  return (
    <div className="rounded-lg border bg-emerald-50 p-4 text-center">
      <div className="flex items-center justify-center gap-1 text-xs font-medium uppercase tracking-wide text-emerald-700">
        <TrendingDown className="h-3.5 w-3.5" />
        Économie estimée
      </div>
      {economieAnnuelle != null ? (
        <p className="mt-1 text-3xl font-bold text-emerald-800">{economieAnnuelle.toFixed(0)} €/an</p>
      ) : (
        <p className="mt-1 text-sm text-emerald-700">Renseignez le coût actuel du client pour l&apos;estimer</p>
      )}
    </div>
  );
}
