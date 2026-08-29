"use client";

import Link from "next/link";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useIntegrerOffreVeilleMarche, useRapportsVeilleMarche } from "@/lib/hooks/useIaConseil";
import type { RapportVeilleMarche } from "@/lib/types-ia-conseil";

// Revue des rapports hebdomadaires de l'agent de veille marché autonome
// (§3.4, backend/services/veille_marche_agent.py — outil serveur web_search,
// tourne chaque lundi via Celery beat). Chaque offre détectée est intégrée
// en brouillon (valide=false) dans le catalogue via "Intégrer au
// catalogue" — la publication finale (prix, fournisseur canonique) se fait
// ensuite dans Admin > Catalogue, jamais automatiquement d'ici.
export default function VeilleMarchePage() {
  const rapportsQuery = useRapportsVeilleMarche();
  const integrer = useIntegrerOffreVeilleMarche();

  const onIntegrer = (rapport: RapportVeilleMarche, index: number) => {
    integrer.mutate(
      { rapportId: rapport.id, index },
      {
        onSuccess: () => toast.success("Offre intégrée en brouillon — à finaliser dans Admin > Catalogue."),
        onError: () => toast.error("Impossible d'intégrer cette offre."),
      }
    );
  };

  const rapports = (rapportsQuery.data ?? []).filter((r) => r.offres_detectees.length > 0);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-primary">IA Conseil — Veille marché</h1>
          <p className="text-sm text-muted-foreground">
            Offres détectées sur le web par l&apos;agent autonome, pas encore au catalogue.
          </p>
        </div>
        <Button variant="outline" asChild>
          <Link href="/ia-conseil/admin/catalogue">Voir le catalogue</Link>
        </Button>
      </div>

      {rapportsQuery.isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : rapports.length === 0 ? (
        <p className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
          Aucune offre en attente de revue pour le moment.
        </p>
      ) : (
        <div className="space-y-4">
          {rapports.map((rapport) => (
            <div key={rapport.id} className="space-y-2 rounded-md border p-3">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium">
                  {rapport.categorie_slug} — semaine du {new Date(rapport.semaine_debut).toLocaleDateString("fr-FR")}
                </p>
                <Badge variant={rapport.statut === "traite" ? "outline" : "default"}>
                  {rapport.statut === "traite" ? "Traité" : "En attente"}
                </Badge>
              </div>

              <div className="space-y-2">
                {rapport.offres_detectees.map((offre, index) => (
                  <div key={index} className="flex items-center justify-between gap-3 rounded-md bg-muted/40 p-2.5 text-sm">
                    <div>
                      <p className="font-medium">
                        {offre.fournisseur} — {offre.nom_offre}
                      </p>
                      <p className="text-muted-foreground">
                        {offre.prix_mensuel != null ? `${offre.prix_mensuel} €/mois` : "Prix à vérifier"}
                        {" · "}
                        <Badge variant={offre.confiance === "fiable" ? "default" : "outline"} className="ml-1">
                          {offre.confiance === "fiable" ? "Fiable" : "À vérifier"}
                        </Badge>
                        {" · "}
                        <a href={offre.url_source} target="_blank" rel="noreferrer" className="underline">
                          Source
                        </a>
                      </p>
                    </div>
                    <Button size="sm" variant="secondary" onClick={() => onIntegrer(rapport, index)} disabled={integrer.isPending}>
                      Intégrer au catalogue
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
