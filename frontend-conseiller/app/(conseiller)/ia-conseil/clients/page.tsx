"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { DataTable } from "@/components/ui/data-table";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { clientsResource } from "@/lib/hooks/useClients";
import { iaConseilClientsResource } from "@/lib/hooks/useIaConseil";
import { prospectsResource } from "@/lib/hooks/useProspects";
import type { Client, Prospect } from "@/lib/types";
import type { ClientConseil, ClientConseilInput } from "@/lib/types-ia-conseil";

const VALEURS_INITIALES: ClientConseilInput = { prenom: "", nom: "", email: "", telephone: "", adresse: null, foyer: null, profil: null };

function nomAffiche(entite: { prenom: string | null; nom: string | null }) {
  return `${entite.prenom ?? ""} ${entite.nom ?? ""}`.trim() || "(sans nom)";
}

function villeDepuisAdresse(adresse: ClientConseilInput["adresse"]): string {
  const v = adresse?.ville;
  return typeof v === "string" ? v : "";
}

export default function IaConseilClientsPage() {
  const router = useRouter();
  const [createOpen, setCreateOpen] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [valeurs, setValeurs] = useState<ClientConseilInput>(VALEURS_INITIALES);

  const clientsQuery = iaConseilClientsResource.useList();
  const prospectsCrmQuery = prospectsResource.useList();
  const clientsCrmQuery = clientsResource.useList();

  function choisirExistant(entite: Prospect | Client) {
    setValeurs({
      prenom: entite.prenom ?? "",
      nom: entite.nom ?? "",
      email: entite.email ?? "",
      telephone: entite.telephone ?? "",
      adresse: entite.ville || entite.code_postal ? { ville: entite.ville ?? "", code_postal: entite.code_postal ?? "" } : null,
      foyer: null,
      profil: null,
    });
    setPickerOpen(false);
  }

  const createMutation = iaConseilClientsResource.useCreate({
    onSuccess: (client) => {
      toast.success("Client créé.");
      setCreateOpen(false);
      setValeurs(VALEURS_INITIALES);
      router.push(`/ia-conseil/clients/${client.id}`);
    },
  });

  const columns = useMemo<ColumnDef<ClientConseil>[]>(
    () => [
      {
        id: "nom",
        header: "Nom",
        accessorFn: (client) => `${client.prenom ?? ""} ${client.nom ?? ""}`.trim() || "—",
      },
      { id: "email", header: "E-mail", accessorFn: (client) => client.email ?? "—" },
      { id: "telephone", header: "Téléphone", accessorFn: (client) => client.telephone ?? "—" },
      {
        id: "cree_le",
        header: "Créé le",
        accessorFn: (client) => client.cree_le,
        cell: ({ row }) => new Date(row.original.cree_le).toLocaleDateString("fr-FR"),
      },
    ],
    []
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-primary">IA Conseil — Clients</h1>
          <p className="text-sm text-muted-foreground">Audit express mobile / box / énergie, trame adaptative.</p>
        </div>
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
          emptyMessage="Aucun client IA Conseil pour le moment."
          onRowClick={(client) => router.push(`/ia-conseil/clients/${client.id}`)}
        />
      )}

      <Dialog
        open={createOpen}
        onOpenChange={(open) => {
          setCreateOpen(open);
          if (!open) setValeurs(VALEURS_INITIALES);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nouveau client</DialogTitle>
          </DialogHeader>
          <Button type="button" variant="outline" size="sm" onClick={() => setPickerOpen(true)}>
            Reprendre un prospect/client existant…
          </Button>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Prénom</Label>
              <Input value={valeurs.prenom ?? ""} onChange={(e) => setValeurs((v) => ({ ...v, prenom: e.target.value }))} />
            </div>
            <div className="space-y-1.5">
              <Label>Nom</Label>
              <Input value={valeurs.nom ?? ""} onChange={(e) => setValeurs((v) => ({ ...v, nom: e.target.value }))} />
            </div>
            <div className="space-y-1.5">
              <Label>E-mail</Label>
              <Input type="email" value={valeurs.email ?? ""} onChange={(e) => setValeurs((v) => ({ ...v, email: e.target.value }))} />
            </div>
            <div className="space-y-1.5">
              <Label>Téléphone</Label>
              <Input value={valeurs.telephone ?? ""} onChange={(e) => setValeurs((v) => ({ ...v, telephone: e.target.value }))} />
            </div>
            <div className="space-y-1.5 col-span-2">
              <Label>Ville</Label>
              <Input
                value={villeDepuisAdresse(valeurs.adresse)}
                onChange={(e) =>
                  setValeurs((v) => ({ ...v, adresse: { ...(v.adresse ?? {}), ville: e.target.value } }))
                }
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>
              Annuler
            </Button>
            <Button onClick={() => createMutation.mutate(valeurs)} disabled={createMutation.isPending}>
              {createMutation.isPending ? "Création…" : "Créer"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <CommandDialog open={pickerOpen} onOpenChange={setPickerOpen}>
        <CommandInput placeholder="Rechercher un prospect ou client…" />
        <CommandList>
          <CommandEmpty>Aucun résultat.</CommandEmpty>
          <CommandGroup heading="Prospects">
            {(prospectsCrmQuery.data ?? []).map((prospect) => (
              <CommandItem
                key={`prospect-${prospect.id}`}
                value={`${prospect.ref ?? ""} ${nomAffiche(prospect)} ${prospect.telephone ?? ""} ${prospect.email ?? ""}`}
                onSelect={() => choisirExistant(prospect)}
              >
                {prospect.ref ? `${prospect.ref} · ` : ""}
                {nomAffiche(prospect)} — {prospect.telephone || prospect.email || `#${prospect.id}`}
              </CommandItem>
            ))}
          </CommandGroup>
          <CommandGroup heading="Clients">
            {(clientsCrmQuery.data ?? []).map((client) => (
              <CommandItem
                key={`client-${client.id}`}
                value={`${client.ref ?? ""} ${nomAffiche(client)} ${client.telephone ?? ""} ${client.email ?? ""}`}
                onSelect={() => choisirExistant(client)}
              >
                {client.ref ? `${client.ref} · ` : ""}
                {nomAffiche(client)} — {client.telephone || client.email || `#${client.id}`}
              </CommandItem>
            ))}
          </CommandGroup>
        </CommandList>
      </CommandDialog>
    </div>
  );
}
