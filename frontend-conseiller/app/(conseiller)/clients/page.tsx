"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { ClientForm } from "@/components/clients/ClientForm";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDateRelance, sortingFnDateRelance } from "@/lib/dateRelance";
import { clientsResource } from "@/lib/hooks/useClients";
import type { ClientCreateInput } from "@/lib/schemas/client";
import type { Client } from "@/lib/types";

export default function ClientsPage() {
  const router = useRouter();
  const [createOpen, setCreateOpen] = useState(false);

  const clientsQuery = clientsResource.useList();
  const createMutation = clientsResource.useCreate({
    onSuccess: (client) => {
      toast.success("Client créé.");
      setCreateOpen(false);
      router.push(`/clients/${client.id}`);
    },
  });
  const deleteMutation = clientsResource.useDelete({
    onSuccess: () => toast.success("Client supprimé."),
  });

  const columns = useMemo<ColumnDef<Client>[]>(
    () => [
      { accessorKey: "ref", header: "Référence" },
      {
        id: "nom",
        header: "Nom",
        accessorFn: (client) => `${client.prenom ?? ""} ${client.nom ?? ""}`.trim(),
      },
      { accessorKey: "email", header: "Email" },
      { accessorKey: "telephone", header: "Téléphone" },
      { accessorKey: "ville", header: "Ville" },
      {
        id: "prochaine_relance",
        header: "Prochaine relance",
        accessorFn: (client) => `${client.date_relance ?? ""} ${client.statut_relance ?? ""}`.trim(),
        sortingFn: sortingFnDateRelance,
        cell: ({ row }) => (
          <div className="space-y-0.5">
            <div>{formatDateRelance(row.original.date_relance)}</div>
            {row.original.statut_relance && (
              <div className="text-xs text-muted-foreground">{row.original.statut_relance}</div>
            )}
          </div>
        ),
      },
    ],
    []
  );

  const handleDelete = (client: Client) => {
    if (!window.confirm(`Supprimer ${client.prenom ?? ""} ${client.nom ?? ""} ?`)) return;
    deleteMutation.mutate(client.id);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-primary">Clients &amp; contrats</h1>
        <Button onClick={() => setCreateOpen(true)}>Nouveau client</Button>
      </div>

      {clientsQuery.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : (
        <DataTable
          columns={columns}
          data={clientsQuery.data ?? []}
          globalFilterPlaceholder="Rechercher un client…"
          emptyMessage="Aucun client pour le moment."
          defaultSorting={[{ id: "prochaine_relance", desc: false }]}
          onRowClick={(client) => router.push(`/clients/${client.id}`)}
          rowActions={(client) => (
            <>
              <DropdownMenuItem onSelect={() => router.push(`/clients/${client.id}`)}>
                Voir la fiche
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => handleDelete(client)} className="text-destructive">
                Supprimer
              </DropdownMenuItem>
            </>
          )}
        />
      )}

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nouveau client</DialogTitle>
          </DialogHeader>
          <ClientForm
            mode="create"
            defaultValues={{ prenom: "", nom: "", telephone: "", email: "", code_postal: "", ville: "", adresse: "" } as ClientCreateInput}
            onSubmit={(values) => createMutation.mutate(values as ClientCreateInput)}
            submitError={createMutation.error}
            submitLabel="Créer"
            isSubmitting={createMutation.isPending}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}
