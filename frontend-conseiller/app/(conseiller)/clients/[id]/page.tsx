"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useParams, useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { ClientForm, clientToFormValues } from "@/components/clients/ClientForm";
import { ContratForm, contratToFormValues } from "@/components/clients/ContratForm";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DataTable } from "@/components/ui/data-table";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  clientsResource,
  useClientAlertes,
  useClientDocuments,
  useClientHistorique,
  useEnvoyerRelance,
  useGenererLienPortail,
} from "@/lib/hooks/useClients";
import { contratsResource, useContratsClient } from "@/lib/hooks/useContrats";
import { useCreerDossier, useDossiersClient } from "@/lib/hooks/useDossiers";
import type { ClientUpdateInput } from "@/lib/schemas/client";
import type { ContratCreateInput, ContratUpdateInput } from "@/lib/schemas/contrat";
import type { Contrat, Dossier } from "@/lib/types";

const UNIVERS_OPTIONS = [
  { value: "telecom_mobile", label: "Télécom mobile" },
  { value: "telecom_box", label: "Télécom box" },
  { value: "energie", label: "Énergie" },
  { value: "energie_pro", label: "Énergie pro" },
  { value: "assurance_habitation", label: "Assurance habitation" },
];

const STATUTS_RELANCE = ["Aucune", "À relancer", "Relancé"];

export default function ClientDetailPage() {
  const params = useParams<{ id: string }>();
  const clientId = Number(params.id);
  const router = useRouter();

  const clientQuery = clientsResource.useOne(clientId);

  if (clientQuery.isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (!clientQuery.data) {
    return <p className="text-sm text-slate-500">Client introuvable.</p>;
  }

  const client = clientQuery.data;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-primary">
        {client.prenom} {client.nom}
      </h1>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Tabs defaultValue="infos">
            <TabsList>
              <TabsTrigger value="infos">Infos</TabsTrigger>
              <TabsTrigger value="contrats">Contrats</TabsTrigger>
              <TabsTrigger value="dossiers">Dossiers</TabsTrigger>
              <TabsTrigger value="documents">Documents</TabsTrigger>
              <TabsTrigger value="historique">Historique</TabsTrigger>
            </TabsList>
            <TabsContent value="infos">
              <InfosTab clientId={clientId} defaultValues={clientToFormValues(client)} />
            </TabsContent>
            <TabsContent value="contrats">
              <ContratsTab clientId={clientId} />
            </TabsContent>
            <TabsContent value="dossiers">
              <DossiersTab clientId={clientId} />
            </TabsContent>
            <TabsContent value="documents">
              <DocumentsTab clientId={clientId} />
            </TabsContent>
            <TabsContent value="historique">
              <HistoriqueTab clientId={clientId} />
            </TabsContent>
          </Tabs>
        </div>
        <div className="lg:col-span-1">
          <ActionsCard clientId={clientId} onSuppression={() => router.push("/clients")} />
        </div>
      </div>
    </div>
  );
}

function InfosTab({ clientId, defaultValues }: { clientId: number; defaultValues: ClientUpdateInput }) {
  const updateMutation = clientsResource.useUpdate({
    onSuccess: () => toast.success("Client mis à jour."),
  });

  return (
    <Card>
      <CardContent className="pt-6">
        <ClientForm
          mode="edit"
          defaultValues={defaultValues}
          onSubmit={(values) => updateMutation.mutate({ id: clientId, values: values as ClientUpdateInput })}
          submitError={updateMutation.error}
          submitLabel="Enregistrer"
          isSubmitting={updateMutation.isPending}
        />
      </CardContent>
    </Card>
  );
}

function ContratsTab({ clientId }: { clientId: number }) {
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
      { id: "type", header: "Type", accessorFn: (c) => c.categorie || c.univers || "—" },
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

function DossiersTab({ clientId }: { clientId: number }) {
  const dossiersQuery = useDossiersClient(clientId);

  const columns = useMemo<ColumnDef<Dossier>[]>(
    () => [
      { accessorKey: "univers", header: "Univers" },
      {
        id: "statut",
        header: "Statut",
        cell: ({ row }) => <Badge variant="secondary">{row.original.statut}</Badge>,
      },
      { accessorKey: "fournisseur_cible", header: "Fournisseur cible" },
      { accessorKey: "date_creation", header: "Date création" },
      {
        id: "economie",
        header: "Économie annuelle estimée",
        accessorFn: (d) => `${d.economie_annuelle_estimee ?? 0} €`,
      },
    ],
    []
  );

  return (
    <Card>
      <CardContent className="pt-6">
        {dossiersQuery.isLoading ? (
          <Skeleton className="h-48 w-full" />
        ) : (
          <DataTable columns={columns} data={dossiersQuery.data ?? []} emptyMessage="Aucun dossier en cours." />
        )}
      </CardContent>
    </Card>
  );
}

function DocumentsTab({ clientId }: { clientId: number }) {
  const documentsQuery = useClientDocuments(clientId);

  return (
    <Card>
      <CardContent className="space-y-2 pt-6">
        {documentsQuery.isLoading ? (
          <Skeleton className="h-48 w-full" />
        ) : !documentsQuery.data?.length ? (
          <p className="text-sm text-muted-foreground">Aucun document transmis.</p>
        ) : (
          <ul className="divide-y">
            {documentsQuery.data.map((doc) => (
              <li key={doc.id} className="flex items-center justify-between py-2 text-sm">
                <div className="space-y-0.5">
                  <p className="font-medium">{doc.type_document || "Document"}</p>
                  <p className="text-muted-foreground">{doc.date_upload}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={doc.statut_kyc === "valide" ? "default" : "secondary"}>{doc.statut_kyc}</Badge>
                  <a href={doc.url} target="_blank" rel="noreferrer" className="text-primary underline">
                    Voir
                  </a>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function HistoriqueTab({ clientId }: { clientId: number }) {
  const historiqueQuery = useClientHistorique(clientId);

  return (
    <Card>
      <CardContent className="pt-6">
        {historiqueQuery.isLoading ? (
          <Skeleton className="h-48 w-full" />
        ) : !historiqueQuery.data?.length ? (
          <p className="text-sm text-muted-foreground">Aucune action enregistrée.</p>
        ) : (
          <ul className="divide-y">
            {historiqueQuery.data.map((entry) => (
              <li key={entry.id} className="py-2 text-sm">
                <div className="flex justify-between">
                  <span className="font-medium">{entry.action}</span>
                  <span className="text-muted-foreground">{entry.date_action}</span>
                </div>
                {entry.details && <p className="text-muted-foreground">{entry.details}</p>}
                {entry.auteur && <p className="text-xs text-muted-foreground">Par {entry.auteur}</p>}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function ActionsCard({ clientId, onSuppression }: { clientId: number; onSuppression: () => void }) {
  const [lienOpen, setLienOpen] = useState(false);
  const [lienUrl, setLienUrl] = useState<string | null>(null);
  const [devisOpen, setDevisOpen] = useState(false);
  const [univers, setUnivers] = useState(UNIVERS_OPTIONS[0].value);
  const [relanceOpen, setRelanceOpen] = useState(false);
  const [dateRelance, setDateRelance] = useState("");
  const [statutRelance, setStatutRelance] = useState(STATUTS_RELANCE[1]);

  const lienMutation = useGenererLienPortail();
  const devisMutation = useCreerDossier();
  const relanceMutation = useEnvoyerRelance();
  const deleteMutation = clientsResource.useDelete();

  const handleEnvoyerLien = () => {
    lienMutation.mutate(clientId, {
      onSuccess: (data) => {
        setLienUrl(data.url);
        setLienOpen(true);
      },
    });
  };

  const handleGenererDevis = () => {
    devisMutation.mutate(
      { client_id: clientId, univers },
      {
        onSuccess: () => {
          toast.success("Dossier créé — voir l'onglet Dossiers.");
          setDevisOpen(false);
        },
      }
    );
  };

  const handleRelance = () => {
    relanceMutation.mutate(
      { id: clientId, values: { date_relance: dateRelance, statut_relance: statutRelance } },
      {
        onSuccess: () => {
          toast.success("Relance programmée.");
          setRelanceOpen(false);
        },
      }
    );
  };

  const handleSupprimer = () => {
    if (!window.confirm("Supprimer définitivement ce client ?")) return;
    deleteMutation.mutate(clientId, { onSuccess: onSuppression });
  };

  const handleCopier = async () => {
    if (!lienUrl) return;
    await navigator.clipboard.writeText(lienUrl);
    toast.success("Lien copié.");
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Actions</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <Button variant="outline" className="w-full" onClick={handleEnvoyerLien} disabled={lienMutation.isPending}>
          Envoyer lien portail
        </Button>
        <Button variant="outline" className="w-full" onClick={() => setDevisOpen(true)}>
          Générer un devis
        </Button>
        <Button variant="outline" className="w-full" onClick={() => setRelanceOpen(true)}>
          Nouvelle relance
        </Button>
        <Button variant="destructive" className="w-full" onClick={handleSupprimer} disabled={deleteMutation.isPending}>
          Supprimer
        </Button>
      </CardContent>

      <Dialog open={lienOpen} onOpenChange={setLienOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Lien portail client</DialogTitle>
          </DialogHeader>
          <div className="flex gap-2">
            <Input readOnly value={lienUrl ?? ""} />
            <Button onClick={handleCopier}>Copier</Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={devisOpen} onOpenChange={setDevisOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Générer un devis</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Univers</Label>
              <Select value={univers} onValueChange={setUnivers}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {UNIVERS_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex justify-end">
              <Button onClick={handleGenererDevis} disabled={devisMutation.isPending}>
                {devisMutation.isPending ? "Création…" : "Créer le dossier"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={relanceOpen} onOpenChange={setRelanceOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nouvelle relance</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Date de relance</Label>
              <Input type="date" value={dateRelance} onChange={(e) => setDateRelance(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Statut</Label>
              <Select value={statutRelance} onValueChange={setStatutRelance}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {STATUTS_RELANCE.map((statut) => (
                    <SelectItem key={statut} value={statut}>
                      {statut}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex justify-end">
              <Button onClick={handleRelance} disabled={relanceMutation.isPending}>
                {relanceMutation.isPending ? "Enregistrement…" : "Programmer"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
