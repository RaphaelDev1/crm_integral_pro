"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useParams, useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { ClientForm, clientToFormValues } from "@/components/clients/ClientForm";
import { ContratsTab } from "@/components/clients/ContratsTab";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DataTable } from "@/components/ui/data-table";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/contexts/AuthContext";
import { ApiError } from "@/lib/api";
import { formatDateRelance } from "@/lib/dateRelance";
import { labelObjectifPrincipal } from "@/lib/diagnosticConstants";
import { LABELS_STATUT_KYC, statutKycBadgeClass } from "@/lib/dossierStatuts";
import {
  clientsResource,
  useClientDocuments,
  useClientHistorique,
  useEnvoyerRelance,
  useGenererLienPortail,
  useValiderDocumentClient,
} from "@/lib/hooks/useClients";
import { useContrats } from "@/lib/hooks/useContrats";
import { useCreerDossier, useDossiersClient } from "@/lib/hooks/useDossiers";
import type { ClientUpdateInput } from "@/lib/schemas/client";
import type { Dossier } from "@/lib/types";
import { cn } from "@/lib/utils";

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
    const accesRefuse = clientQuery.error instanceof ApiError && clientQuery.error.status === 403;
    return (
      <p className="text-sm text-slate-500">
        {accesRefuse
          ? "Accès refusé — cette fiche appartient à un autre conseiller. Un responsable peut vous en donner l'accès."
          : "Client introuvable."}
      </p>
    );
  }

  const client = clientQuery.data;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-primary">
        {client.prenom} {client.nom}
      </h1>

      <TableauBordClient clientId={clientId} client={client} />

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
              <InfosTab client={client} defaultValues={clientToFormValues(client)} />
            </TabsContent>
            <TabsContent value="contrats" className="space-y-4">
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
          <ActionsCard clientId={clientId} client={client} onSuppression={() => router.push("/clients")} />
        </div>
      </div>
    </div>
  );
}

// Bandeau "dashboard" en tête de fiche — même principe que TableauBordProspect
// (prospects/[id]/page.tsx) : les indicateurs à voir d'un coup d'œil pour
// prioriser. Réutilise uniquement des champs déjà en base (pas de migration) :
// pas de score/motif dédié côté Client, le statut de relance sert d'indicateur
// de priorité, complété par le nombre de dossiers en cours (non actif/échec/annulé).
function TableauBordClient({ clientId, client }: { clientId: number; client: import("@/lib/types").Client }) {
  const dossiersQuery = useDossiersClient(clientId);
  const dossiersEnCours = (dossiersQuery.data ?? []).filter(
    (d) => !["actif", "echec", "annule"].includes(d.statut)
  ).length;

  // Économies réellement faites : différence entre le coût mensuel des
  // contrats "Actuel" (situation d'avant, capturée au diagnostic) et celui
  // des contrats "Actif" (nouveaux contrats souscrits), annualisée — plus
  // fiable qu'une estimation figée, ça bouge avec les contrats du client.
  const contratsQuery = useContrats({ clientId });
  const contrats = contratsQuery.data ?? [];
  const contratsActifs = contrats.filter((c) => c.statut_contrat === "Actif");
  const totalActuelMensuel = contrats
    .filter((c) => c.statut_contrat === "Actuel")
    .reduce((sum, c) => sum + (c.cout_mensuel ?? 0), 0);
  const totalActifMensuel = contratsActifs.reduce((sum, c) => sum + (c.cout_mensuel ?? 0), 0);
  const gainAnnuel = contratsActifs.length > 0 ? Math.max(0, (totalActuelMensuel - totalActifMensuel) * 12) : null;

  const tuiles = [
    {
      label: "Économies faites",
      valeur: gainAnnuel != null ? `${gainAnnuel.toFixed(0)} €/an` : "—",
    },
    { label: "Prochaine relance", valeur: client.date_relance ? formatDateRelance(client.date_relance) : "Non planifiée" },
    { label: "Statut de relance", valeur: client.statut_relance || "Aucune" },
    { label: "Dossiers en cours", valeur: String(dossiersEnCours) },
    { label: "Objectif de la demande", valeur: labelObjectifPrincipal(client.objectif_principal) || "—" },
    {
      label: "Opérateur actuel",
      valeur: client.operateur_actuel || "—",
      sousTitre: [
        client.satisfaction_reseau,
        client.veut_rester ? `Rester : ${client.veut_rester}` : null,
        client.defaut_technique ? `Défaut technique : ${client.defaut_technique}` : null,
      ]
        .filter(Boolean)
        .join(" · ") || undefined,
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-6">
      {tuiles.map((tuile) => (
        <Card key={tuile.label}>
          <CardContent className="pt-4 pb-3">
            <p className="text-xs text-muted-foreground">{tuile.label}</p>
            <p className="text-lg font-bold text-primary">{tuile.valeur}</p>
            {tuile.sousTitre && <p className="text-xs text-muted-foreground">{tuile.sousTitre}</p>}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function InfosTab({
  client,
  defaultValues,
}: {
  client: import("@/lib/types").Client;
  defaultValues: ClientUpdateInput;
}) {
  const clientId = client.id;
  const { estAdmin } = useAuth();
  const verrouille = !estAdmin();
  const updateMutation = clientsResource.useUpdate({
    onSuccess: () => toast.success("Client mis à jour."),
  });

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="pt-6 space-y-3">
          {verrouille && (
            <p className="rounded-md border bg-muted px-3 py-2 text-sm text-muted-foreground">
              Fiche verrouillée — une fois enregistrée, seule un responsable peut modifier les informations du client.
            </p>
          )}
          <fieldset disabled={verrouille} className={cn(verrouille && "opacity-60")}>
            <ClientForm
              mode="edit"
              defaultValues={defaultValues}
              onSubmit={(values) => updateMutation.mutate({ id: clientId, values: values as ClientUpdateInput })}
              submitError={updateMutation.error}
              submitLabel="Enregistrer"
              isSubmitting={updateMutation.isPending}
            />
          </fieldset>
        </CardContent>
      </Card>
    </div>
  );
}

function DossiersTab({ clientId }: { clientId: number }) {
  const router = useRouter();
  const dossiersQuery = useDossiersClient(clientId);

  const columns = useMemo<ColumnDef<Dossier>[]>(
    () => [
      { id: "numero", header: "N° dossier", accessorFn: (d) => `#${d.id}` },
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
          <DataTable
            columns={columns}
            data={dossiersQuery.data ?? []}
            emptyMessage="Aucun dossier en cours."
            onRowClick={(dossier) => router.push(`/dossiers/${dossier.id}`)}
          />
        )}
      </CardContent>
    </Card>
  );
}

function DocumentsTab({ clientId }: { clientId: number }) {
  const documentsQuery = useClientDocuments(clientId);
  const validerMutation = useValiderDocumentClient(clientId);
  const [rejetCible, setRejetCible] = useState<{ id: number; label: string } | null>(null);
  const [motifRejet, setMotifRejet] = useState("");

  const handleValider = (documentId: number) => {
    validerMutation.mutate(
      { documentId, statutKyc: "valide" },
      { onSuccess: () => toast.success("Document validé.") }
    );
  };

  const handleConfirmerRejet = () => {
    if (!rejetCible) return;
    validerMutation.mutate(
      { documentId: rejetCible.id, statutKyc: "rejete", motifRejet },
      {
        onSuccess: () => {
          toast.success("Document rejeté, un signalement a été créé.");
          setRejetCible(null);
          setMotifRejet("");
        },
      }
    );
  };

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
                  <Badge variant="outline" className={statutKycBadgeClass(doc.statut_kyc)}>
                    {LABELS_STATUT_KYC[doc.statut_kyc] ?? doc.statut_kyc}
                  </Badge>
                  <a href={doc.url} target="_blank" rel="noreferrer" className="text-primary underline">
                    Voir
                  </a>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={doc.statut_kyc === "valide" || validerMutation.isPending}
                    onClick={() => handleValider(doc.id)}
                  >
                    Valider
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-destructive"
                    disabled={validerMutation.isPending}
                    onClick={() => setRejetCible({ id: doc.id, label: doc.type_document || "Document" })}
                  >
                    Rejeter
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>

      <Dialog open={rejetCible !== null} onOpenChange={(open) => !open && setRejetCible(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rejeter « {rejetCible?.label} »</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Motif du rejet</Label>
              <Input value={motifRejet} onChange={(e) => setMotifRejet(e.target.value)} placeholder="Document illisible, information manquante…" />
            </div>
            <div className="flex justify-end">
              <Button variant="destructive" onClick={handleConfirmerRejet} disabled={validerMutation.isPending}>
                {validerMutation.isPending ? "Enregistrement…" : "Confirmer le rejet"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
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

// Champs sans lesquels un nouveau diagnostic ne doit pas être lancé (identité
// minimale requise dès l'étape 2 du wizard, voir etapeIdentiteSchema côté
// /diagnostic) — vérifiés ici en amont pour bloquer le bouton plutôt que de
// laisser le conseiller découvrir le blocage une fois dans le wizard.
function champsObligatoiresDiagnosticManquants(client: import("@/lib/types").Client): string[] {
  const manquants: string[] = [];
  if (!client.prenom) manquants.push("Prénom");
  if (!client.nom) manquants.push("Nom");
  if (!client.telephone) manquants.push("Téléphone");
  if (!client.code_postal) manquants.push("Code postal");
  if (!client.ville) manquants.push("Ville");
  return manquants;
}

function ActionsCard({
  clientId,
  client,
  onSuppression,
}: {
  clientId: number;
  client: import("@/lib/types").Client;
  onSuppression: () => void;
}) {
  const router = useRouter();
  const manquantsDiagnostic = champsObligatoiresDiagnosticManquants(client);
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
    deleteMutation.mutate(clientId, {
      onSuccess: onSuppression,
      onError: (err) => {
        if (err instanceof ApiError && err.status === 409) {
          toast.error(err.message || "Ce client a encore des données liées — suppression bloquée.");
        } else if (err instanceof ApiError && err.status === 403) {
          toast.error("Cette fiche appartient à un autre conseiller — seul un Admin peut la supprimer.");
        } else {
          toast.error("Échec de la suppression du client.");
        }
      },
    });
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
        <Button
          variant="outline"
          className="w-full"
          disabled={manquantsDiagnostic.length > 0}
          title={
            manquantsDiagnostic.length > 0
              ? `Complétez d'abord la fiche (${manquantsDiagnostic.join(", ")}) avant de lancer un diagnostic.`
              : undefined
          }
          onClick={() => router.push(`/diagnostic?entiteType=client&entiteId=${clientId}`)}
        >
          Nouveau diagnostic
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
