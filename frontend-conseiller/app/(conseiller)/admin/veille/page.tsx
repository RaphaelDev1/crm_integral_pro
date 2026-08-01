"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { SourceVeilleForm, sourceVeilleToFormValues } from "@/components/admin/SourceVeilleForm";
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
  sourcesVeilleResource,
  useLancerVeilleManuelle,
  useRejeterAlerteVeille,
  useValiderAlerteVeille,
  useVeilleAlertes,
  useVeilleHistorique,
} from "@/lib/hooks/useVeille";
import type { SourceVeilleCreateInput, SourceVeilleUpdateInput } from "@/lib/schemas/veille";
import type { SourceVeille, VeilleAlerte, VeilleHistoriquePrix } from "@/lib/types";

export default function VeillePage() {
  return (
    <AdminGuard>
      <div className="space-y-4">
        <h1 className="text-xl font-bold text-primary">Veille prix</h1>
        <Tabs defaultValue="sources">
          <TabsList>
            <TabsTrigger value="sources">Sources</TabsTrigger>
            <TabsTrigger value="historique">Historique prix</TabsTrigger>
            <TabsTrigger value="alertes">Alertes détectées</TabsTrigger>
          </TabsList>
          <TabsContent value="sources">
            <SourcesTab />
          </TabsContent>
          <TabsContent value="historique">
            <HistoriqueTab />
          </TabsContent>
          <TabsContent value="alertes">
            <AlertesTab />
          </TabsContent>
        </Tabs>
      </div>
    </AdminGuard>
  );
}

function SourcesTab() {
  const [createOpen, setCreateOpen] = useState(false);
  const [editCible, setEditCible] = useState<SourceVeille | null>(null);

  const sourcesQuery = sourcesVeilleResource.useList();
  const createMutation = sourcesVeilleResource.useCreate({
    onSuccess: () => {
      toast.success("Source ajoutée.");
      setCreateOpen(false);
    },
  });
  const updateMutation = sourcesVeilleResource.useUpdate({
    onSuccess: () => {
      toast.success("Source mise à jour.");
      setEditCible(null);
    },
  });
  const deleteMutation = sourcesVeilleResource.useDelete({
    onSuccess: () => toast.success("Source supprimée."),
  });
  const lancerMutation = useLancerVeilleManuelle();

  const handleDelete = (source: SourceVeille) => {
    if (!window.confirm(`Supprimer la source "${source.fournisseur} — ${source.nom_offre}" ?`)) return;
    deleteMutation.mutate(source.id);
  };

  const handleLancer = () => {
    lancerMutation.mutate(undefined, {
      onSuccess: (alertes) => toast.success(`Veille lancée : ${alertes.length} alerte(s) détectée(s).`),
    });
  };

  const columns = useMemo<ColumnDef<SourceVeille>[]>(
    () => [
      { accessorKey: "fournisseur", header: "Fournisseur" },
      { accessorKey: "nom_offre", header: "Offre" },
      { accessorKey: "univers", header: "Univers" },
      { accessorKey: "dernier_prix", header: "Dernier prix (€)" },
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
          <Button variant="outline" onClick={handleLancer} disabled={lancerMutation.isPending}>
            {lancerMutation.isPending ? "Lancement…" : "Lancer la veille maintenant"}
          </Button>
          <Button onClick={() => setCreateOpen(true)}>Nouvelle source</Button>
        </div>

        {sourcesQuery.isLoading ? (
          <Skeleton className="h-64 w-full" />
        ) : (
          <DataTable
            columns={columns}
            data={sourcesQuery.data ?? []}
            globalFilterPlaceholder="Rechercher une source…"
            emptyMessage="Aucune source surveillée pour le moment."
            rowActions={(source) => (
              <>
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
              <DialogTitle>Nouvelle source de veille</DialogTitle>
            </DialogHeader>
            <SourceVeilleForm
              mode="create"
              defaultValues={{ univers: "", categorie: "", fournisseur: "", nom_offre: "", url: "", selecteur_prix: "", actif: true } as SourceVeilleCreateInput}
              onSubmit={(values) => createMutation.mutate(values as SourceVeilleCreateInput)}
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
              <SourceVeilleForm
                mode="edit"
                defaultValues={sourceVeilleToFormValues(editCible)}
                onSubmit={(values) => updateMutation.mutate({ id: editCible.id, values: values as SourceVeilleUpdateInput })}
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

function HistoriqueTab() {
  const [sourceId, setSourceId] = useState<string>("");
  const sourcesQuery = sourcesVeilleResource.useList();
  const historiqueQuery = useVeilleHistorique(sourceId ? Number(sourceId) : undefined);

  const columns = useMemo<ColumnDef<VeilleHistoriquePrix>[]>(
    () => [
      { accessorKey: "prix", header: "Prix (€)" },
      { accessorKey: "date_releve", header: "Date de relevé" },
    ],
    []
  );

  return (
    <Card>
      <CardContent className="pt-6 space-y-4">
        <Select value={sourceId} onValueChange={setSourceId}>
          <SelectTrigger className="w-96">
            <SelectValue placeholder="Choisir une source…" />
          </SelectTrigger>
          <SelectContent>
            {(sourcesQuery.data ?? []).map((source) => (
              <SelectItem key={source.id} value={String(source.id)}>
                {source.fournisseur} — {source.nom_offre}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {sourceId && (
          historiqueQuery.isLoading ? (
            <Skeleton className="h-64 w-full" />
          ) : (
            <DataTable columns={columns} data={historiqueQuery.data ?? []} emptyMessage="Aucun relevé pour cette source." />
          )
        )}
      </CardContent>
    </Card>
  );
}

function AlertesTab() {
  const [statut, setStatut] = useState("en_attente");
  const alertesQuery = useVeilleAlertes(statut);
  const validerMutation = useValiderAlerteVeille();
  const rejeterMutation = useRejeterAlerteVeille();

  const columns = useMemo<ColumnDef<VeilleAlerte>[]>(
    () => [
      { accessorKey: "ancien_prix", header: "Ancien prix (€)" },
      { accessorKey: "nouveau_prix", header: "Nouveau prix (€)" },
      { accessorKey: "date_detection", header: "Détectée le" },
      {
        id: "statut",
        header: "Statut",
        cell: ({ row }) => <Badge variant="secondary">{row.original.statut}</Badge>,
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
            <SelectItem value="validee">Validées</SelectItem>
            <SelectItem value="rejetee">Rejetées</SelectItem>
          </SelectContent>
        </Select>

        {alertesQuery.isLoading ? (
          <Skeleton className="h-64 w-full" />
        ) : (
          <DataTable
            columns={columns}
            data={alertesQuery.data ?? []}
            emptyMessage="Aucune alerte."
            rowActions={
              statut === "en_attente"
                ? (alerte) => (
                    <>
                      <DropdownMenuItem onSelect={() => validerMutation.mutate(alerte.id, { onSuccess: () => toast.success("Alerte validée.") })}>
                        Valider
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onSelect={() => rejeterMutation.mutate(alerte.id, { onSuccess: () => toast.success("Alerte rejetée.") })}
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
