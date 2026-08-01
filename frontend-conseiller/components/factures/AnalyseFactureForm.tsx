"use client";

import { useRef, useState } from "react";
import { toast } from "sonner";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { clientsResource } from "@/lib/hooks/useClients";
import { useAnalyserFacture } from "@/lib/hooks/useFactures";
import type { FactureAnalyse } from "@/lib/types";

const AUCUN_CLIENT = "__aucun__";

// Composant partagé entre /facturation (onglet "Analyse de factures") et
// /admin/ocr-facture (Phase 5.3 + 8.4) : même formulaire d'upload + résultat
// OCR, seul l'emplacement d'où on y accède change.
export function AnalyseFactureForm() {
  const [clientId, setClientId] = useState<string>(AUCUN_CLIENT);
  const [resultat, setResultat] = useState<FactureAnalyse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const clientsQuery = clientsResource.useList();
  const analyserMutation = useAnalyserFacture();

  const handleFichierChoisi = (event: React.ChangeEvent<HTMLInputElement>) => {
    const fichier = event.target.files?.[0];
    if (!fichier) return;
    analyserMutation.mutate(
      { fichier, clientId: clientId === AUCUN_CLIENT ? undefined : Number(clientId) },
      {
        onSuccess: (data) => {
          setResultat(data);
          toast.success("Facture analysée.");
        },
        onSettled: () => {
          if (fileInputRef.current) fileInputRef.current.value = "";
        },
      }
    );
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Analyser une facture</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Client (optionnel — pour enregistrer l&apos;analyse sur sa fiche)</Label>
            <Select value={clientId} onValueChange={setClientId}>
              <SelectTrigger className="w-80">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={AUCUN_CLIENT}>Analyse ponctuelle (non enregistrée)</SelectItem>
                {(clientsQuery.data ?? []).map((client) => (
                  <SelectItem key={client.id} value={String(client.id)}>
                    {client.prenom} {client.nom}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Facture (PDF)</Label>
            <Input ref={fileInputRef} type="file" accept="application/pdf" onChange={handleFichierChoisi} />
          </div>
          {analyserMutation.isPending && <p className="text-sm text-muted-foreground">Analyse en cours…</p>}
        </CardContent>
      </Card>

      {resultat && (
        <Card>
          <CardHeader>
            <CardTitle>Résultat de l&apos;analyse</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              <dt className="text-muted-foreground">Opérateur</dt>
              <dd>{resultat.operateur}</dd>
              <dt className="text-muted-foreground">Prix HT</dt>
              <dd>{resultat.prix_ht} €</dd>
              <dt className="text-muted-foreground">Prix TTC</dt>
              <dd>{resultat.prix_ttc} €</dd>
              <dt className="text-muted-foreground">Consommation data</dt>
              <dd>{resultat.data_conso_go} Go</dd>
              <dt className="text-muted-foreground">Options</dt>
              <dd>{resultat.options.join(", ") || "—"}</dd>
              <dt className="text-muted-foreground">Engagement</dt>
              <dd>{resultat.engagement_mois} mois</dd>
              <dt className="text-muted-foreground">Fin d&apos;engagement</dt>
              <dd>{resultat.date_fin_engagement}</dd>
              <dt className="text-muted-foreground">IBAN prélèvement</dt>
              <dd>{resultat.iban_prelevement}</dd>
            </dl>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
