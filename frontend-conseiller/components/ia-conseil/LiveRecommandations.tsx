"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EconomieTicker } from "@/components/ia-conseil/EconomieTicker";
import { cn } from "@/lib/utils";
import type { RecommandationOut } from "@/lib/types-ia-conseil";

interface LiveRecommandationsProps {
  recommandations: RecommandationOut[];
  presentation: boolean;
  isLoading?: boolean;
}

// Colonne droite de la vue Trame Live : score de recommandation vivant,
// recalculé à chaque réponse (§Vision du rendu final). En mode présentation,
// la commission (donnée backoffice, jamais montrée au client) est masquée.
export function LiveRecommandations({ recommandations, presentation, isLoading }: LiveRecommandationsProps) {
  const meilleure = recommandations[0];

  return (
    <div className="space-y-4">
      <EconomieTicker economieAnnuelle={meilleure?.economie_annuelle ?? null} />

      <div className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {isLoading ? "Calcul en cours…" : `Top ${recommandations.length} recommandation${recommandations.length > 1 ? "s" : ""}`}
        </p>
        {recommandations.map((reco) => (
          <Card key={reco.offre_id} className={cn(reco.rang === 1 && "border-primary")}>
            <CardHeader className="flex-row items-center justify-between space-y-0 py-3">
              <CardTitle className="text-sm">
                {reco.rang}. {reco.offre?.nom ?? "Offre"}
              </CardTitle>
              <Badge variant={reco.rang === 1 ? "default" : "outline"}>{reco.score.toFixed(0)}/100</Badge>
            </CardHeader>
            <CardContent className="space-y-1 pb-3 pt-0 text-sm">
              {reco.offre?.prix_mensuel != null && <p className="font-medium">{reco.offre.prix_mensuel} €/mois</p>}
              {reco.economie_mensuelle != null && (
                <p className="text-emerald-700">Économie : {reco.economie_mensuelle.toFixed(0)} €/mois</p>
              )}
              {reco.justifications.length > 0 && (
                <ul className="list-inside list-disc text-xs text-muted-foreground">
                  {reco.justifications.slice(0, 3).map((justification) => (
                    <li key={justification}>{justification}</li>
                  ))}
                </ul>
              )}
              {!presentation && reco.offre?.fournisseur_id && (
                <p className="text-xs text-muted-foreground">Fournisseur : {reco.offre.fournisseur_id.slice(0, 8)}…</p>
              )}
            </CardContent>
          </Card>
        ))}
        {!isLoading && recommandations.length === 0 && (
          <p className="text-sm text-muted-foreground">Aucune recommandation pour l&apos;instant.</p>
        )}
      </div>
    </div>
  );
}
