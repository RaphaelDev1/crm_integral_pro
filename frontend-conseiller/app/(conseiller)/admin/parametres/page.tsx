"use client";

import { useRef, useState } from "react";
import { toast } from "sonner";

import { AdminGuard } from "@/components/layout/AdminGuard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useMajParametre, useParametresListe, useUploadLogo } from "@/lib/hooks/useParametres";
import type { Parametre } from "@/lib/types";

export default function ParametresPage() {
  return (
    <AdminGuard>
      <div className="space-y-4">
        <h1 className="text-xl font-bold text-primary">Paramètres</h1>
        <LogoCard />
        <ReglagesCard />
      </div>
    </AdminGuard>
  );
}

function LogoCard() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadMutation = useUploadLogo();

  const handleFichierChoisi = (event: React.ChangeEvent<HTMLInputElement>) => {
    const fichier = event.target.files?.[0];
    if (!fichier) return;
    uploadMutation.mutate(fichier, {
      onSuccess: () => toast.success("Logo mis à jour."),
      onSettled: () => {
        if (fileInputRef.current) fileInputRef.current.value = "";
      },
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Logo (restitutions PDF)</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <Label>Fichier (JPG, PNG ou WEBP, 5 Mo max)</Label>
        <Input ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/webp" onChange={handleFichierChoisi} />
        {uploadMutation.isPending && <p className="text-sm text-muted-foreground">Envoi en cours…</p>}
        {uploadMutation.data && <p className="text-sm text-muted-foreground">Clé de stockage : {uploadMutation.data.valeur}</p>}
      </CardContent>
    </Card>
  );
}

function ReglagesCard() {
  const parametresQuery = useParametresListe();
  const [nouvelleCle, setNouvelleCle] = useState("");
  const [nouvelleValeur, setNouvelleValeur] = useState("");
  const majMutation = useMajParametre();

  const handleAjouter = () => {
    if (!nouvelleCle.trim()) return;
    majMutation.mutate(
      { cle: nouvelleCle.trim(), valeur: nouvelleValeur },
      {
        onSuccess: () => {
          toast.success("Paramètre ajouté.");
          setNouvelleCle("");
          setNouvelleValeur("");
        },
      }
    );
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Réglages</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {parametresQuery.isLoading ? (
          <Skeleton className="h-48 w-full" />
        ) : (parametresQuery.data ?? []).length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucun paramètre pour le moment.</p>
        ) : (
          <div className="space-y-2">
            {(parametresQuery.data ?? []).map((parametre) => (
              <ParametreRow key={parametre.cle} parametre={parametre} />
            ))}
          </div>
        )}

        <div className="flex items-end gap-2 pt-4 border-t">
          <div className="space-y-2 flex-1">
            <Label>Nouvelle clé</Label>
            <Input value={nouvelleCle} onChange={(e) => setNouvelleCle(e.target.value)} placeholder="ex. nom_societe" />
          </div>
          <div className="space-y-2 flex-1">
            <Label>Valeur</Label>
            <Input value={nouvelleValeur} onChange={(e) => setNouvelleValeur(e.target.value)} />
          </div>
          <Button onClick={handleAjouter} disabled={majMutation.isPending || !nouvelleCle.trim()}>
            Ajouter
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function ParametreRow({ parametre }: { parametre: Parametre }) {
  const [valeur, setValeur] = useState(parametre.valeur ?? "");
  const majMutation = useMajParametre();
  const modifie = valeur !== (parametre.valeur ?? "");

  return (
    <div className="flex items-center gap-2">
      <Label className="w-56 shrink-0 truncate" title={parametre.cle}>
        {parametre.cle}
      </Label>
      <Input value={valeur} onChange={(e) => setValeur(e.target.value)} className="flex-1" />
      <Button
        size="sm"
        variant="outline"
        disabled={!modifie || majMutation.isPending}
        onClick={() =>
          majMutation.mutate(
            { cle: parametre.cle, valeur },
            { onSuccess: () => toast.success(`Paramètre "${parametre.cle}" mis à jour.`) }
          )
        }
      >
        Enregistrer
      </Button>
    </div>
  );
}
