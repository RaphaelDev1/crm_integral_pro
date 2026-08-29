"use client";

import type { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { DataTable } from "@/components/ui/data-table";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  useCreerOffreAdmin,
  useIaConseilCategories,
  useIaConseilFournisseurs,
  useIaConseilOffres,
  useModifierOffreAdmin,
  useSupprimerOffreAdmin,
} from "@/lib/hooks/useIaConseil";
import type { OffreConseil, OffreConseilInput } from "@/lib/types-ia-conseil";

// CRUD admin minimal du catalogue IA Conseil (§1.4.C) — canal réel de mise à
// jour tant qu'aucune source partenaire réelle n'est branchée (voir
// backend/services/ia_conseil_catalogue_sync.py). Import CSV en masse et
// workflow brouillon→validée→publiée explicitement hors scope de cette
// itération (§1.4.C du plan les prévoit pour une itération ultérieure).
const VALEURS_INITIALES = (categorieSlug: string): OffreConseilInput => ({
  fournisseur_id: null,
  categorie_slug: categorieSlug,
  nom: "",
  prix_mensuel: null,
  prix_apres_promo: null,
  duree_promo_mois: null,
  engagement_mois: 0,
  frais_mise_en_service: 0,
  caracteristiques: {},
  conditions: null,
  source: "manuel",
  source_ref: null,
  valide: true,
});

export default function IaConseilAdminCataloguePage() {
  const [categorieFiltre, setCategorieFiltre] = useState<string>("");
  const [editing, setEditing] = useState<OffreConseil | null>(null);
  const [creating, setCreating] = useState(false);
  const [valeurs, setValeurs] = useState<OffreConseilInput>(VALEURS_INITIALES(""));
  const [caracteristiquesJson, setCaracteristiquesJson] = useState("{}");

  const categoriesQuery = useIaConseilCategories();
  const fournisseursQuery = useIaConseilFournisseurs(valeurs.categorie_slug || undefined);
  const offresQuery = useIaConseilOffres(categorieFiltre || undefined);

  const creerMutation = useCreerOffreAdmin();
  const modifierMutation = useModifierOffreAdmin();
  const supprimerMutation = useSupprimerOffreAdmin();

  const ouvrirCreation = () => {
    setValeurs(VALEURS_INITIALES(categorieFiltre));
    setCaracteristiquesJson("{}");
    setCreating(true);
  };

  const ouvrirEdition = (offre: OffreConseil) => {
    setEditing(offre);
    setValeurs({ ...offre });
    setCaracteristiquesJson(JSON.stringify(offre.caracteristiques, null, 2));
  };

  const fermer = () => {
    setCreating(false);
    setEditing(null);
  };

  const enregistrer = () => {
    let caracteristiques: Record<string, unknown>;
    try {
      caracteristiques = JSON.parse(caracteristiquesJson);
    } catch {
      toast.error("Caractéristiques : JSON invalide.");
      return;
    }
    const payload = { ...valeurs, caracteristiques };

    if (editing) {
      modifierMutation.mutate(
        { id: editing.id, values: payload },
        { onSuccess: () => (toast.success("Offre modifiée."), fermer()) }
      );
    } else {
      creerMutation.mutate(payload, { onSuccess: () => (toast.success("Offre créée."), fermer()) });
    }
  };

  const supprimer = (offre: OffreConseil) => {
    if (!window.confirm(`Supprimer l'offre "${offre.nom}" ?`)) return;
    supprimerMutation.mutate(offre.id, { onSuccess: () => toast.success("Offre supprimée.") });
  };

  const columns = useMemo<ColumnDef<OffreConseil>[]>(
    () => [
      { id: "nom", header: "Offre", accessorFn: (o) => o.nom },
      { id: "categorie", header: "Catégorie", accessorFn: (o) => o.categorie_slug ?? "—" },
      { id: "prix", header: "Prix", accessorFn: (o) => (o.prix_mensuel != null ? `${o.prix_mensuel} €/mois` : "—") },
      { id: "engagement", header: "Engagement", accessorFn: (o) => `${o.engagement_mois} mois` },
      {
        id: "valide",
        header: "Statut",
        cell: ({ row }) => (
          <Badge variant={row.original.valide ? "default" : "outline"}>{row.original.valide ? "Active" : "Inactive"}</Badge>
        ),
      },
    ],
    []
  );

  const modaleOuverte = creating || editing !== null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-primary">IA Conseil — Admin catalogue</h1>
          <p className="text-sm text-muted-foreground">Offres mobile / box / énergie du sous-système IA Conseil.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" asChild>
            <Link href="/ia-conseil/admin/veille-marche">Veille marché</Link>
          </Button>
          <Button onClick={ouvrirCreation}>Nouvelle offre</Button>
        </div>
      </div>

      <Select value={categorieFiltre || "toutes"} onValueChange={(v) => setCategorieFiltre(v === "toutes" ? "" : v)}>
        <SelectTrigger className="w-64">
          <SelectValue placeholder="Toutes les catégories" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="toutes">Toutes les catégories</SelectItem>
          {(categoriesQuery.data ?? []).map((categorie) => (
            <SelectItem key={categorie.slug} value={categorie.slug}>
              {categorie.nom}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {offresQuery.isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : (
        <DataTable
          columns={columns}
          data={offresQuery.data ?? []}
          globalFilterPlaceholder="Rechercher une offre…"
          emptyMessage="Aucune offre dans cette catégorie."
          onRowClick={ouvrirEdition}
          rowActions={(offre) => (
            <>
              <DropdownMenuItem onSelect={() => ouvrirEdition(offre)}>Modifier</DropdownMenuItem>
              <DropdownMenuItem onSelect={() => supprimer(offre)} className="text-destructive">
                Supprimer
              </DropdownMenuItem>
            </>
          )}
        />
      )}

      <Dialog open={modaleOuverte} onOpenChange={(open) => !open && fermer()}>
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editing ? "Modifier l'offre" : "Nouvelle offre"}</DialogTitle>
          </DialogHeader>

          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Catégorie</Label>
                <Select
                  value={valeurs.categorie_slug ?? ""}
                  onValueChange={(v) => setValeurs((val) => ({ ...val, categorie_slug: v }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Catégorie" />
                  </SelectTrigger>
                  <SelectContent>
                    {(categoriesQuery.data ?? []).map((categorie) => (
                      <SelectItem key={categorie.slug} value={categorie.slug}>
                        {categorie.nom}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Fournisseur</Label>
                <Select
                  value={valeurs.fournisseur_id ?? ""}
                  onValueChange={(v) => setValeurs((val) => ({ ...val, fournisseur_id: v }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Fournisseur" />
                  </SelectTrigger>
                  <SelectContent>
                    {(fournisseursQuery.data ?? []).map((fournisseur) => (
                      <SelectItem key={fournisseur.id} value={fournisseur.id}>
                        {fournisseur.nom}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-1.5">
              <Label>Nom de l&apos;offre</Label>
              <Input value={valeurs.nom} onChange={(e) => setValeurs((v) => ({ ...v, nom: e.target.value }))} />
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1.5">
                <Label>Prix mensuel (€)</Label>
                <Input
                  type="number"
                  value={valeurs.prix_mensuel ?? ""}
                  onChange={(e) => setValeurs((v) => ({ ...v, prix_mensuel: e.target.value ? Number(e.target.value) : null }))}
                />
              </div>
              <div className="space-y-1.5">
                <Label>Engagement (mois)</Label>
                <Input
                  type="number"
                  value={valeurs.engagement_mois}
                  onChange={(e) => setValeurs((v) => ({ ...v, engagement_mois: Number(e.target.value) || 0 }))}
                />
              </div>
              <div className="flex items-end gap-2 pb-2">
                <Checkbox checked={valeurs.valide} onCheckedChange={(c) => setValeurs((v) => ({ ...v, valide: c === true }))} />
                <Label>Active</Label>
              </div>
            </div>

            <div className="space-y-1.5">
              <Label>Caractéristiques (JSON)</Label>
              <Textarea
                rows={6}
                className="font-mono text-xs"
                value={caracteristiquesJson}
                onChange={(e) => setCaracteristiquesJson(e.target.value)}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="ghost" onClick={fermer}>
              Annuler
            </Button>
            <Button onClick={enregistrer} disabled={creerMutation.isPending || modifierMutation.isPending}>
              {creerMutation.isPending || modifierMutation.isPending ? "Enregistrement…" : "Enregistrer"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
