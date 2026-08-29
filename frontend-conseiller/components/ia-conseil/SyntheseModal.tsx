"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, downloadBackendFile } from "@/lib/api";
import { iaConseilSouscriptionsResource, useOverrideAlerte } from "@/lib/hooks/useIaConseil";
import type { AlertesBloquantesPayload, CrossSellSuggestion, RecommandationOut } from "@/lib/types-ia-conseil";

interface SyntheseModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  sessionId: string;
  clientId: string;
  recommandations: RecommandationOut[];
  suggestionsCrossSell?: CrossSellSuggestion[];
}

// Fin de trame (§Vision du rendu final / §1.3-1.4) : synthèse PDF en 1 clic +
// enregistrement de la souscription. La commission prévue est déjà calculée
// côté backend (voir routers/ia_conseil_souscriptions.py::_calculer_commission_prevue)
// à partir du taux du fournisseur — rien à faire ici.
export function SyntheseModal({ open, onOpenChange, sessionId, clientId, recommandations, suggestionsCrossSell = [] }: SyntheseModalProps) {
  const meilleure = recommandations[0];
  const [offreId, setOffreId] = useState(meilleure?.offre_id ?? "");
  const [prixNegocie, setPrixNegocie] = useState(meilleure?.offre?.prix_mensuel?.toString() ?? "");
  const [dateSouscription, setDateSouscription] = useState(() => new Date().toISOString().slice(0, 10));
  const [telechargement, setTelechargement] = useState(false);
  const [alertesBloquantes, setAlertesBloquantes] = useState<AlertesBloquantesPayload | null>(null);
  const [justification, setJustification] = useState("");

  const overrideAlerte = useOverrideAlerte(sessionId);

  const creerSouscription = iaConseilSouscriptionsResource.useCreate({
    onSuccess: () => {
      toast.success("Souscription enregistrée.");
      onOpenChange(false);
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409 && error.payload) {
        setAlertesBloquantes(error.payload as AlertesBloquantesPayload);
      }
    },
  });

  // Lève chaque alerte critique bloquante avec la même justification puis
  // relance la création de souscription (§2.1) — le conseiller n'a qu'un
  // formulaire à remplir même s'il y a plusieurs alertes sur l'offre.
  const leverEtReessayer = async () => {
    if (!alertesBloquantes || justification.trim().length < 10) return;
    try {
      for (const alerte of alertesBloquantes.alertes) {
        await overrideAlerte.mutateAsync({ offre_id: offreId, regle_nom: alerte.regle, justification: justification.trim() });
      }
      setAlertesBloquantes(null);
      setJustification("");
      enregistrerSouscription();
    } catch {
      toast.error("Impossible de lever les alertes.");
    }
  };

  const recoChoisie = recommandations.find((r) => r.offre_id === offreId);

  const telechargerPdf = async () => {
    setTelechargement(true);
    try {
      await downloadBackendFile(`/api/v1/sessions/${sessionId}/pdf`, `synthese-ia-conseil-${sessionId}.pdf`);
    } catch {
      toast.error("Impossible de générer le PDF.");
    } finally {
      setTelechargement(false);
    }
  };

  const enregistrerSouscription = () => {
    if (!offreId) return;
    creerSouscription.mutate({
      client_id: clientId,
      offre_id: offreId,
      session_id: sessionId,
      date_souscription: dateSouscription || null,
      prix_mensuel_negocie: prixNegocie ? Number(prixNegocie) : null,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Synthèse de la trame</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <Button variant="outline" className="w-full" onClick={telechargerPdf} disabled={telechargement}>
            {telechargement ? "Génération…" : "Télécharger la synthèse PDF"}
          </Button>

          <div className="space-y-3 rounded-md border p-3">
            <p className="text-sm font-medium">Enregistrer une souscription</p>

            <div className="space-y-1.5">
              <Label>Offre retenue</Label>
              <Select
                value={offreId}
                onValueChange={(valeur) => {
                  setOffreId(valeur);
                  setAlertesBloquantes(null);
                  setJustification("");
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Choisir une offre" />
                </SelectTrigger>
                <SelectContent>
                  {recommandations.map((reco) => (
                    <SelectItem key={reco.offre_id} value={reco.offre_id}>
                      {reco.rang}. {reco.offre?.nom ?? "Offre"} ({reco.score.toFixed(0)}/100)
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Prix mensuel négocié (€)</Label>
                <Input type="number" value={prixNegocie} onChange={(e) => setPrixNegocie(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label>Date de souscription</Label>
                <Input type="date" value={dateSouscription} onChange={(e) => setDateSouscription(e.target.value)} />
              </div>
            </div>

            {recoChoisie && recoChoisie.economie_annuelle != null && (
              <p className="text-sm text-emerald-700">Économie estimée : {recoChoisie.economie_annuelle.toFixed(0)} €/an</p>
            )}
          </div>

          {suggestionsCrossSell.length > 0 && (
            <div className="space-y-1.5 rounded-md border border-violet-200 bg-violet-50 p-3">
              <p className="text-sm font-medium text-violet-900">À proposer aussi</p>
              <ul className="space-y-1 text-sm text-violet-900">
                {suggestionsCrossSell.map((suggestion, i) => (
                  <li key={i}>{suggestion.message}</li>
                ))}
              </ul>
            </div>
          )}

          {alertesBloquantes && (
            <div className="space-y-3 rounded-md border border-destructive/50 bg-destructive/5 p-3">
              <p className="text-sm font-medium text-destructive">Alerte(s) critique(s) à lever avant de souscrire</p>
              <ul className="space-y-1 text-sm">
                {alertesBloquantes.alertes.map((alerte) => (
                  <li key={alerte.regle}>{alerte.message}</li>
                ))}
              </ul>
              <div className="space-y-1.5">
                <Label>Justification (obligatoire, min. 10 caractères)</Label>
                <Textarea value={justification} onChange={(e) => setJustification(e.target.value)} rows={2} />
              </div>
              <Button
                variant="destructive"
                size="sm"
                onClick={leverEtReessayer}
                disabled={justification.trim().length < 10 || overrideAlerte.isPending}
              >
                {overrideAlerte.isPending ? "Levée en cours…" : "Lever les alertes et réessayer"}
              </Button>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Fermer
          </Button>
          <Button onClick={enregistrerSouscription} disabled={!offreId || creerSouscription.isPending || Boolean(alertesBloquantes)}>
            {creerSouscription.isPending ? "Enregistrement…" : "Enregistrer la souscription"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
