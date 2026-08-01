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
import { clientsResource } from "@/lib/hooks/useClients";
import { contratsResource } from "@/lib/hooks/useContrats";
import type { ClientCreateInput } from "@/lib/schemas/client";
import type { Client } from "@/lib/types";

export default function ClientsPage() {
  const router = useRouter();
  const [createOpen, setCreateOpen] = useState(false);

  const clientsQuery = clientsResource.useList();
  const contratsQuery = contratsResource.useList();
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

  const nbContratsParClient = useMemo(() => {
    const map = new Map<number, number>();
    for (const contrat of contratsQuery.data ?? []) {
      if (contrat.client_id == null) continue;
      map.set(contrat.client_id, (map.get(contrat.client_id) ?? 0) + 1);
    }
    return map;
  }, [contratsQuery.data]);

  const columns = useMemo<ColumnDef<Client>[]>(
    () => [
      {
        id: "nom",
        header: "Nom",
        accessorFn: (client) => `${client.prenom ?? ""} ${client.nom ?? ""}`.trim(),
      },
      { accessorKey: "email", header: "Email" },
      { accessorKey: "telephone", header: "Téléphone" },
      { accessorKey: "ville", header: "Ville" },
      {
        id: "nb_contrats",
        header: "Nb contrats",
        accessorFn: (client) => nbContratsParClient.get(client.id) ?? 0,
      },
      { accessorKey: "date_creation", header: "Date création" },
    ],
    [nbContratsParClient]
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
