"use client";

import { useEffect, useRef, useState } from "react";
import { FileUp, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAppliquerFacture, useFacture, useTeleverserFacture } from "@/lib/hooks/useIaConseil";

const CHAMPS_LABELS: Record<string, string> = {
  operateur_actuel: "Opérateur actuel",
  cout_actuel_mensuel: "Coût mensuel actuel (€)",
  conso_data_go: "Consommation data (Go)",
  fournisseur_actuel_elec: "Fournisseur actuel (élec)",
  cout_actuel_mensuel_elec: "Coût mensuel actuel élec (€)",
  fournisseur_actuel_gaz: "Fournisseur actuel (gaz)",
  cout_actuel_mensuel_gaz: "Coût mensuel actuel gaz (€)",
};

interface FactureUploadPanelProps {
  sessionId: string;
}

// Import de facture pendant la session (§3.1) : upload -> analyse Claude
// vision en tâche de fond -> le conseiller valide/corrige les valeurs
// proposées avant qu'elles ne remplissent réellement les réponses (jamais
// automatique, voir backend/services/ia_conseil_facture.py::appliquer).
export function FactureUploadPanel({ sessionId }: FactureUploadPanelProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [factureId, setFactureId] = useState<string | undefined>(undefined);
  const [open, setOpen] = useState(false);
  const [valeurs, setValeurs] = useState<Record<string, string>>({});

  const televerser = useTeleverserFacture(sessionId);
  const factureQuery = useFacture(sessionId, factureId);
  const appliquer = useAppliquerFacture(sessionId);

  const facture = factureQuery.data;
  const propositions = facture?.extraction?.propositions_reponses as Record<string, unknown> | undefined;

  // Initialise les champs éditables une seule fois, dès que les
  // propositions de l'analyse arrivent (statut "analysee").
  useEffect(() => {
    if (facture?.statut === "analysee" && propositions && Object.keys(valeurs).length === 0) {
      setValeurs(Object.fromEntries(Object.entries(propositions).map(([k, v]) => [k, String(v)])));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [facture?.statut, propositions]);

  const reinitialiser = () => {
    setOpen(false);
    setFactureId(undefined);
    setValeurs({});
    if (inputRef.current) inputRef.current.value = "";
  };

  const onFichierChoisi = (fichier: File | undefined) => {
    if (!fichier) return;
    televerser.mutate(fichier, {
      onSuccess: (f) => {
        setFactureId(f.id);
        setOpen(true);
      },
      onError: () => toast.error("Impossible d'envoyer la facture."),
    });
  };

  const onAppliquer = () => {
    if (!factureId) return;
    const reponses = Object.fromEntries(
      Object.entries(valeurs)
        .filter(([, v]) => v.trim() !== "")
        .map(([k, v]) => [k, Number.isNaN(Number(v)) ? v : Number(v)])
    );
    appliquer.mutate(
      { factureId, reponses },
      {
        onSuccess: () => {
          toast.success("Réponses mises à jour depuis la facture.");
          reinitialiser();
        },
        onError: () => toast.error("Impossible d'appliquer les réponses."),
      }
    );
  };

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={(e) => onFichierChoisi(e.target.files?.[0])}
      />
      <Button
        variant="outline"
        size="sm"
        className="gap-1.5"
        onClick={() => inputRef.current?.click()}
        disabled={televerser.isPending}
      >
        {televerser.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileUp className="h-4 w-4" />}
        Importer une facture
      </Button>

      <Dialog open={open} onOpenChange={(o) => (o ? setOpen(true) : reinitialiser())}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Facture analysée</DialogTitle>
          </DialogHeader>

          {facture?.statut === "en_attente" && (
            <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Analyse en cours…
            </p>
          )}
          {facture?.statut === "echouee" && (
            <p className="text-sm text-destructive">{facture.erreur ?? "L'analyse de la facture a échoué."}</p>
          )}
          {facture?.statut === "analysee" && (
            <div className="space-y-3">
              {Object.keys(valeurs).length === 0 ? (
                <p className="text-sm text-muted-foreground">Aucune donnée exploitable détectée sur cette facture.</p>
              ) : (
                <>
                  <p className="text-sm text-muted-foreground">
                    Vérifiez et corrigez si besoin avant d&apos;appliquer à la trame.
                  </p>
                  {Object.entries(valeurs).map(([champ, valeur]) => (
                    <div key={champ} className="space-y-1.5">
                      <Label>{CHAMPS_LABELS[champ] ?? champ}</Label>
                      <Input value={valeur} onChange={(e) => setValeurs((v) => ({ ...v, [champ]: e.target.value }))} />
                    </div>
                  ))}
                </>
              )}
            </div>
          )}

          <DialogFooter>
            <Button variant="ghost" onClick={reinitialiser}>
              Fermer
            </Button>
            <Button onClick={onAppliquer} disabled={Object.keys(valeurs).length === 0 || appliquer.isPending}>
              {appliquer.isPending ? "Application…" : "Appliquer à la trame"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
