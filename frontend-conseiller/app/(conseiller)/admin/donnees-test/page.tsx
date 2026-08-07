"use client";

import { useState } from "react";
import { toast } from "sonner";

import { AdminGuard } from "@/components/layout/AdminGuard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { usePurgerDonneesTest } from "@/lib/hooks/useDonneesTest";

const CONFIRMATION_ATTENDUE = "SUPPRIMER";

export default function DonneesTestPage() {
  const [confirmation, setConfirmation] = useState("");
  const purgeMutation = usePurgerDonneesTest();

  const handlePurger = () => {
    if (confirmation !== CONFIRMATION_ATTENDUE) return;
    if (!window.confirm("Dernière confirmation : supprimer TOUS les prospects et clients (irréversible) ?")) return;

    purgeMutation.mutate(undefined, {
      onSuccess: (resultat) => {
        toast.success(
          `${resultat.clients_supprimes} client(s), ${resultat.prospects_supprimes} prospect(s) et ${resultat.fichiers_supprimes} fichier(s) supprimés.`
        );
        setConfirmation("");
      },
    });
  };

  return (
    <AdminGuard>
      <div className="space-y-4">
        <h1 className="text-xl font-bold text-primary">Données de test</h1>

        <Card className="border-destructive/50">
          <CardHeader>
            <CardTitle className="text-destructive">Supprimer tous les prospects et clients</CardTitle>
            <CardDescription>
              Supprime définitivement TOUS les prospects et clients, ainsi que tout ce qui en dépend (dossiers,
              mandats, documents, factures, commissions...) et les fichiers associés (photos, PDF) sur le
              stockage. À utiliser uniquement pour désencombrer la base entre deux sessions de test — action
              irréversible, indisponible en production.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>
                Tapez <span className="font-mono font-semibold">{CONFIRMATION_ATTENDUE}</span> pour confirmer
              </Label>
              <Input
                value={confirmation}
                onChange={(e) => setConfirmation(e.target.value)}
                placeholder={CONFIRMATION_ATTENDUE}
                className="max-w-xs"
              />
            </div>
            <Button
              variant="destructive"
              disabled={confirmation !== CONFIRMATION_ATTENDUE || purgeMutation.isPending}
              onClick={handlePurger}
            >
              {purgeMutation.isPending ? "Suppression en cours…" : "Supprimer tous les prospects et clients"}
            </Button>
          </CardContent>
        </Card>
      </div>
    </AdminGuard>
  );
}
