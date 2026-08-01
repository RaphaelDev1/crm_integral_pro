"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { CatalogueSourceForm, catalogueSourceToFormValues } from "@/components/admin/CatalogueSourceForm";
import { AdminGuard } from "@/components/layout/AdminGuard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { DataTable } from "@/components/ui/data-table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  sourcesCatalogueResource,
  useIngererSourceCatalogue,
  useOffresStaging,
  useRejeterOffreStaging,
  useValiderOffreStaging,
} from "@/lib/hooks/useCatalogue";
import type { CatalogueSourceCreateInput, CatalogueSourceUpdateInput } from "@/lib/schemas/catalogue";
import type { CatalogueSource, OffreStaging } from "@/lib/types";

export default function CataloguePage() {
  return (
    <AdminGuard>
      <div className="space-y-4">
        <h1 className="text-xl font-bold text-primary">Catalogue</h1>
        <Tabs defaultValue="sources">
          <TabsList>
            <TabsTrigger value="sources">Sources</TabsTrigger>
            <TabsTrigger value="staging">Offres détectées</TabsTrigger>
          </TabsList>
          <TabsContent value="sources">
            <SourcesTab />
          </TabsContent>
          <TabsContent value="staging">
            <StagingTab />
          </TabsContent>
        </Tabs>
      </div>
    </AdminGuard>
  );
}

function SourcesTab() {
  const [createOpen, setCreateOpen] = useState(false);
  const [editCible, setEditCible] = useState<CatalogueSource | null>(null);

  const sourcesQuery = sourcesCatalogueResource.useList();
  const createMutation = sourcesCatalogueResource.useCreate({
    onSuccess: () => {
      toast.success("Source ajoutée.");
      setCreateOpen(false);
    },
  });
  const updateMutation = sourcesCatalogueResource.useUpdate({
    onSuccess: () => {
      toast.success("Source mise à jour.");
      setEditCible(null);
    },
  });
  const deleteMutation = sourcesCatalogueResource.useDelete({
    onSuccess: () => toast.success("Source supprimée."),
  });
  const ingererMutation = useIngererSourceCatalogue();

  const handleDelete = (source: CatalogueSource) => {
    if (!window.confirm(`Supprimer la source "${source.fournisseur} — ${source.url}" ?`)) return;
    deleteMutation.mutate(source.id);
  };

  const handleIngerer = (source: CatalogueSource) => {
    ingererMutation.mutate(source.id, {
      onSuccess: (resume) =>
        toast.success(
          `Ingestion terminée : ${resume.detectees} nouvelle(s), ${resume.changements} changement(s), ${resume.a_verifier} à vérifier.`
        ),
    });
  };

  const columns = useMemo<ColumnDef<CatalogueSource>[]>(
    () => [
      { accessorKey: "fournisseur", header: "Fournisseur" },
      { accessorKey: "univers", header: "Univers" },
      { accessorKey: "categorie", header: "Catégorie" },
      { accessorKey: "date_derniere_ingestion", header: "Dernière ingestion" },
      {
        id: "robots_ok",
        header: "robots.txt",
        cell: ({ row }) => <Badge variant={row.original.robots_ok ? "default" : "destructive"}>{row.original.robots_ok ? "Autorisé" : "Bloqué"}</Badge>,
      },
      {
        id: "actif",
        header: "Statut",
        cell: ({ row }) => <Badge variant={row.original.actif ? "default" : "secondary"}>{row.original.actif ? "Active" : "Inactive"}</Badge>,
      },
    ],
    []
  );

  return (
    <Card>
      <CardContent className="pt-6 space-y-4">
        <div className="flex justify-end gap-2">
          <Button onClick={() => setCreateOpen(true)}>Nouvelle source</Button>
        </div>

        {sourcesQuery.isLoading ? (
          <Skeleton className="h-64 w-full" />
        ) : (
          <DataTable
            columns={columns}
            data={sourcesQuery.data ?? []}
            globalFilterPlaceholder="Rechercher une source…"
            emptyMessage="Aucune source de catalogue pour le moment."
            rowActions={(source) => (
              <>
                <DropdownMenuItem onSelect={() => handleIngerer(source)} disabled={ingererMutation.isPending}>
                  Ingérer maintenant
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => setEditCible(source)}>Modifier</DropdownMenuItem>
                <DropdownMenuItem onSelect={() => handleDelete(source)} className="text-destructive">
                  Supprimer
                </DropdownMenuItem>
              </>
            )}
          />
        )}

        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Nouvelle source de catalogue</DialogTitle>
            </DialogHeader>
            <CatalogueSourceForm
              mode="create"
              defaultValues={{ univers: "", categorie: "", fournisseur: "", url: "", type_source: "page_officielle", methode: "requests", frequence_h: 24, actif: true } as CatalogueSourceCreateInput}
              onSubmit={(values) => createMutation.mutate(values as CatalogueSourceCreateInput)}
              submitError={createMutation.error}
              submitLabel="Créer"
              isSubmitting={createMutation.isPending}
            />
          </DialogContent>
        </Dialog>

        <Dialog open={editCible !== null} onOpenChange={(open) => !open && setEditCible(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Modifier la source</DialogTitle>
            </DialogHeader>
            {editCible && (
              <CatalogueSourceForm
                mode="edit"
                defaultValues={catalogueSourceToFormValues(editCible)}
                onSubmit={(values) => updateMutation.mutate({ id: editCible.id, values: values as CatalogueSourceUpdateInput })}
                submitError={updateMutation.error}
                submitLabel="Enregistrer"
                isSubmitting={updateMutation.isPending}
              />
            )}
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
}

function StagingTab() {
  const [statut, setStatut] = useState("en_attente");
  const stagingQuery = useOffresStaging(statut);
  const validerMutation = useValiderOffreStaging();
  const rejeterMutation = useRejeterOffreStaging();

  const columns = useMemo<ColumnDef<OffreStaging>[]>(
    () => [
      { accessorKey: "fournisseur", header: "Fournisseur" },
      { accessorKey: "nom_offre", header: "Offre" },
      { accessorKey: "univers", header: "Univers" },
      { accessorKey: "categorie", header: "Catégorie" },
      {
        id: "prix_mensuel",
        header: "Prix (€/mois)",
        cell: ({ row }) => (row.original.prix_mensuel != null ? row.original.prix_mensuel.toFixed(2) : "—"),
      },
      {
        id: "offre_existante_id",
        header: "Type",
        cell: ({ row }) => <Badge variant="secondary">{row.original.offre_existante_id ? "Changement" : "Nouvelle offre"}</Badge>,
      },
      {
        id: "statut",
        header: "Statut",
        cell: ({ row }) => <Badge variant={row.original.statut === "a_verifier" ? "destructive" : "secondary"}>{row.original.statut}</Badge>,
      },
    ],
    []
  );

  return (
    <Card>
      <CardContent className="pt-6 space-y-4">
        <Select value={statut} onValueChange={setStatut}>
          <SelectTrigger className="w-64">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="en_attente">En attente</SelectItem>
            <SelectItem value="a_verifier">À vérifier (prix non détecté)</SelectItem>
            <SelectItem value="validee">Validées</SelectItem>
            <SelectItem value="rejetee">Rejetées</SelectItem>
          </SelectContent>
        </Select>

        {stagingQuery.isLoading ? (
          <Skeleton className="h-64 w-full" />
        ) : (
          <DataTable
            columns={columns}
            data={stagingQuery.data ?? []}
            emptyMessage="Aucune offre détectée."
            rowActions={
              statut === "en_attente" || statut === "a_verifier"
                ? (offre) => (
                    <>
                      <DropdownMenuItem onSelect={() => validerMutation.mutate(offre.id, { onSuccess: () => toast.success("Offre validée et ajoutée au catalogue.") })}>
                        Valider
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onSelect={() => rejeterMutation.mutate(offre.id, { onSuccess: () => toast.success("Offre rejetée.") })}
                        className="text-destructive"
                      >
                        Rejeter
                      </DropdownMenuItem>
                    </>
                  )
                : undefined
            }
          />
        )}
      </CardContent>
    </Card>
  );
}
