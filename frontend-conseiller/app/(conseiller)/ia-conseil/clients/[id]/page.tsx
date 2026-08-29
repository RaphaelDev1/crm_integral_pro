"use client";

import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  iaConseilClientsResource,
  useCreerSessionTrame,
  useCrossSell,
  useIaConseilCategories,
  useScoreClient,
} from "@/lib/hooks/useIaConseil";
import type { Canal } from "@/lib/types-ia-conseil";

const SEGMENT_LABELS: Record<string, string> = {
  infidele: "Infidèle",
  econome: "Économe",
  premium: "Premium",
  ethique: "Éthique",
  equilibre: "Équilibré",
};

const CANAUX: { valeur: Canal; label: string }[] = [
  { valeur: "visio", label: "Visio (partage d'écran)" },
  { valeur: "telephone", label: "Téléphone" },
  { valeur: "physique", label: "Rendez-vous physique" },
];

export default function IaConseilClientDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const clientId = params.id;

  const [categorieSlug, setCategorieSlug] = useState<string>("");
  const [canal, setCanal] = useState<Canal>("visio");

  const clientQuery = iaConseilClientsResource.useOne(clientId);
  const categoriesQuery = useIaConseilCategories();
  const crossSellQuery = useCrossSell(clientId);
  const scoreQuery = useScoreClient(clientId);
  const creerSession = useCreerSessionTrame();

  const demarrerTrame = () => {
    if (!categorieSlug) return;
    creerSession.mutate(
      { client_id: clientId, categorie_slug: categorieSlug, canal },
      {
        onSuccess: (session) => router.push(`/ia-conseil/clients/${clientId}/trame/${session.id}`),
        onError: () => toast.error("Impossible de démarrer la trame."),
      }
    );
  };

  if (clientQuery.isLoading) return <Skeleton className="h-64 w-full" />;
  if (!clientQuery.data) return <p className="text-sm text-muted-foreground">Client introuvable.</p>;

  const client = clientQuery.data;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-primary">
        {`${client.prenom ?? ""} ${client.nom ?? ""}`.trim() || "Client"}
      </h1>
      <p className="text-sm text-muted-foreground">
        {client.email ?? "—"} · {client.telephone ?? "—"}
      </p>

      <Card className="max-w-md">
        <CardHeader>
          <CardTitle className="text-base">Démarrer une trame</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Select value={categorieSlug} onValueChange={setCategorieSlug}>
            <SelectTrigger>
              <SelectValue placeholder="Catégorie…" />
            </SelectTrigger>
            <SelectContent>
              {(categoriesQuery.data ?? []).map((categorie) => (
                <SelectItem key={categorie.slug} value={categorie.slug}>
                  {categorie.nom}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={canal} onValueChange={(v) => setCanal(v as Canal)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CANAUX.map((option) => (
                <SelectItem key={option.valeur} value={option.valeur}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Button className="w-full" onClick={demarrerTrame} disabled={!categorieSlug || creerSession.isPending}>
            {creerSession.isPending ? "Démarrage…" : "Démarrer la trame"}
          </Button>
        </CardContent>
      </Card>

      {scoreQuery.data && (scoreQuery.data.proba_churn != null || scoreQuery.data.segment) && (
        <Card className="max-w-md">
          <CardHeader>
            <CardTitle className="text-base">Scoring client</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {scoreQuery.data.proba_churn != null && (
              <p>
                Risque de résiliation : <strong>{Math.round(scoreQuery.data.proba_churn * 100)}%</strong>{" "}
                <Badge variant="outline" className="ml-1">
                  {scoreQuery.data.source === "modele" ? "modèle" : "estimation"}
                </Badge>
              </p>
            )}
            {scoreQuery.data.proba_cross_sell != null && (
              <p>Potentiel cross-sell : {Math.round(scoreQuery.data.proba_cross_sell * 100)}%</p>
            )}
            {scoreQuery.data.segment && <p>Segment : {SEGMENT_LABELS[scoreQuery.data.segment] ?? scoreQuery.data.segment}</p>}
          </CardContent>
        </Card>
      )}

      {(crossSellQuery.data ?? []).length > 0 && (
        <Card className="max-w-md border-l-4 border-l-violet-300">
          <CardHeader>
            <CardTitle className="text-base">À proposer aussi</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 text-sm">
              {(crossSellQuery.data ?? []).map((suggestion, i) => (
                <li key={i}>{suggestion.message}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
