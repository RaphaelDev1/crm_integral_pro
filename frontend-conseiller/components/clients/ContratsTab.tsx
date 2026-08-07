"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { ContratForm, contratToFormValues } from "@/components/clients/ContratForm";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { DataTable } from "@/components/ui/data-table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { useClientAlertes } from "@/lib/hooks/useClients";
import { contratsResource, useContratsClient } from "@/lib/hooks/useContrats";
import type { ContratCreateInput, ContratUpdateInput } from "@/lib/schemas/contrat";
import type { Contrat } from "@/lib/types";

// Contrats créés avant l'ajout du champ "Type" (categorie) au formulaire ne
// portent que l'ancien `univers` technique ("telecom_mobile") — on le
// retraduit ici pour rester lisible, sans migration de données.
const LABELS_UNIVERS_CONTRAT: Record<string, string> = {
  telecom_mobile: "Forfait mobile",
  telecom_box: "Forfait box",
  energie: "Énergie",
  energie_pro: "Énergie pro",
  assurance_habitation: "Assurance habitation",
};

function labelTypeContrat(contrat: Contrat): string {
  if (contrat.categorie) return contrat.categorie;
  if (contrat.univers) return LABELS_UNIVERS_CONTRAT[contrat.univers] ?? contrat.univers;
  return "—";
}

// Onglet "Contrats en cours" — réutilisé par la fiche client (clients/[id]/page.tsx)
// et la fiche prospect (prospects/[id]/page.tsx, une fois la fiche client miroir
// créée) pour donner un suivi complet des contrats rattachés au client.
export function ContratsTab({ clientId }: { clientId: number }) {
  const contratsQuery = useContratsClient(clientId);
  const alertesQuery = useClientAlertes(clientId);
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<Contrat | null>(null);

  const createMutation = contratsResource.useCreate({
    onSuccess: () => {
      toast.success("Contrat ajouté.");
      setCreateOpen(false);
    },
  });
  const updateMutation = contratsResource.useUpdate({
    onSuccess: () => {
      toast.success("Contrat mis à jour.");
      setEditing(null);
    },
  });
  const deleteMutation = contratsResource.useDelete({
    onSuccess: () => toast.success("Contrat supprimé."),
  });

  const columns = useMemo<ColumnDef<Contrat>[]>(
    () => [
      { id: "type", header: "Type", accessorFn: labelTypeContrat },
      { accessorKey: "fournisseur", header: "Fournisseur" },
      {
        id: "cout_mensuel",
        header: "Prix mensuel",
        accessorFn: (c) => (c.cout_mensuel != null ? `${c.cout_mensuel} €` : "—"),
      },
      {
        id: "statut_contrat",
        header: "Statut",
        cell: ({ row }) => <Badge variant="secondary">{row.original.statut_contrat || "—"}</Badge>,
      },
      { accessorKey: "date_fin_engagement", header: "Date fin engagement" },
    ],
    []
  );

  const alertesEconomie = (alertesQuery.data ?? []).reduce((total, a) => total + (a.economie_mensuelle ?? 0), 0);

  const handleDelete = (contrat: Contrat) => {
    if (!window.confirm(`Supprimer le contrat ${contrat.fournisseur ?? ""} ?`)) return;
    deleteMutation.mutate(contrat.id);
  };

  return (
    <Card>
      <CardContent className="space-y-4 pt-6">
        {!!alertesQuery.data?.length && (
          <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            {alertesQuery.data.length} offre(s) moins chère(s) détectée(s) — économie potentielle estimée à{" "}
            {alertesEconomie.toFixed(2)} €/mois.
          </div>
        )}
        <div className="flex justify-end">
          <Button onClick={() => setCreateOpen(true)}>Ajouter contrat</Button>
        </div>
        {contratsQuery.isLoading ? (
          <Skeleton className="h-48 w-full" />
        ) : (
          <DataTable
            columns={columns}
            data={contratsQuery.data ?? []}
            emptyMessage="Aucun contrat rattaché."
            rowActions={(contrat) => (
              <>
                <DropdownMenuItem onSelect={() => setEditing(contrat)}>Modifier</DropdownMenuItem>
                <DropdownMenuItem onSelect={() => handleDelete(contrat)} className="text-destructive">
                  Supprimer
                </DropdownMenuItem>
              </>
            )}
          />
        )}
      </CardContent>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Ajouter un contrat</DialogTitle>
          </DialogHeader>
          <ContratForm
            mode="create"
            defaultValues={{ client_id: clientId, fournisseur: "" } as ContratCreateInput}
            onSubmit={(values) => createMutation.mutate({ ...(values as ContratCreateInput), client_id: clientId })}
            submitError={createMutation.error}
            submitLabel="Ajouter"
            isSubmitting={createMutation.isPending}
          />
        </DialogContent>
      </Dialog>

      <Dialog open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Modifier le contrat</DialogTitle>
          </DialogHeader>
          {editing && (
            <ContratForm
              mode="edit"
              defaultValues={contratToFormValues(editing)}
              onSubmit={(values) => updateMutation.mutate({ id: editing.id, values: values as ContratUpdateInput })}
              submitError={updateMutation.error}
              submitLabel="Enregistrer"
              isSubmitting={updateMutation.isPending}
            />
          )}
        </DialogContent>
      </Dialog>
    </Card>
  );
}
