"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { AlertTriangle } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { ContratsTab } from "@/components/clients/ContratsTab";
import { ProspectForm, prospectToFormValues } from "@/components/prospects/ProspectForm";
import { ScoringPanel } from "@/components/prospects/ScoringPanel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTable } from "@/components/ui/data-table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { AEnvoyerBadge, RecuBadge } from "@/components/ui/recu-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatDateRelance } from "@/lib/dateRelance";
import { labelObjectifPrincipal } from "@/lib/diagnosticConstants";
import { useContrats } from "@/lib/hooks/useContrats";
import { useDossiersClient } from "@/lib/hooks/useDossiers";
import { useProspectFacturesAnalysees } from "@/lib/hooks/useFactures";
import {
  prospectsResource,
  useContacterTelephone,
  useConvertirProspect,
  useEnvoyerLienDocumentsProspect,
  useGenererLienDocumentsProspect,
  useProspectDocuments,
  useProspectHistorique,
  useRelanceEffectuee,
  useSupprimerDocumentProspect,
} from "@/lib/hooks/useProspects";
import type { ProspectUpdateInput } from "@/lib/schemas/prospect";
import type { Dossier } from "@/lib/types";

// Champs obligatoires pour lancer un nouveau diagnostic (identité minimale
// requise dès l'étape 2 du wizard, voir etapeIdentiteSchema côté /diagnostic)
// — base commune du bandeau d'alerte et du blocage du bouton, pour ne plus
// risquer de divergence entre les deux.
const CHAMPS_BLOQUANT_DIAGNOSTIC: { champ: keyof import("@/lib/types").Prospect; label: string }[] = [
  { champ: "prenom", label: "Prénom" },
  { champ: "nom", label: "Nom" },
  { champ: "telephone", label: "Téléphone" },
  { champ: "code_postal", label: "Code postal" },
  { champ: "ville", label: "Ville" },
];

// Champs affichés dans le bandeau d'alerte mais qui ne bloquent pas le
// diagnostic (redemandés plus tard si besoin) — Email en fait partie : jamais
// requis pour diagnostiquer, mais indispensable pour la suite (envoi des
// mandats, du lien personnel...), donc signalé au conseiller au plus vite.
const CHAMPS_IMPORTANTS_NON_BLOQUANTS: { champ: keyof import("@/lib/types").Prospect; label: string }[] = [
  { champ: "email", label: "Email" },
  { champ: "adresse", label: "Adresse" },
];

function champsManquantsProspect(prospect: import("@/lib/types").Prospect): string[] {
  return [...CHAMPS_BLOQUANT_DIAGNOSTIC, ...CHAMPS_IMPORTANTS_NON_BLOQUANTS]
    .filter(({ champ }) => !prospect[champ])
    .map(({ label }) => label);
}

function champsObligatoiresDiagnosticManquants(prospect: import("@/lib/types").Prospect): string[] {
  return CHAMPS_BLOQUANT_DIAGNOSTIC.filter(({ champ }) => !prospect[champ]).map(({ label }) => label);
}

export default function ProspectDetailPage() {
  const params = useParams<{ id: string }>();
  const prospectId = Number(params.id);
  const router = useRouter();

  const prospectQuery = prospectsResource.useOne(prospectId);

  if (prospectQuery.isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (!prospectQuery.data) {
    return <p className="text-sm text-slate-500">Prospect introuvable.</p>;
  }

  const prospect = prospectQuery.data;
  const manquants = champsManquantsProspect(prospect);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-primary">
          {prospect.prenom} {prospect.nom}
        </h1>
        {prospect.converti_at != null && <Badge variant="secondary">Converti en client</Badge>}
      </div>

      {manquants.length > 0 && (
        <div className="flex items-start gap-2 rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <p>
            <span className="font-semibold">Informations manquantes à compléter au plus vite :</span>{" "}
            {manquants.join(", ")}.
          </p>
        </div>
      )}

      <TableauBordProspect prospect={prospect} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Tabs defaultValue="infos">
            <TabsList>
              <TabsTrigger value="infos">Infos</TabsTrigger>
              <TabsTrigger value="scoring">Scoring</TabsTrigger>
              {prospect.client_id != null && <TabsTrigger value="dossiers">Dossiers</TabsTrigger>}
              <TabsTrigger value="contrats">Contrats</TabsTrigger>
              <TabsTrigger value="documents">Documents</TabsTrigger>
              <TabsTrigger value="historique">Historique</TabsTrigger>
            </TabsList>
            <TabsContent value="infos">
              <InfosTab prospect={prospect} defaultValues={prospectToFormValues(prospect)} />
            </TabsContent>
            <TabsContent value="scoring">
              <ScoringPanel prospectId={prospectId} />
            </TabsContent>
            {prospect.client_id != null && (
              <TabsContent value="dossiers">
                <DossiersTab clientId={prospect.client_id} />
              </TabsContent>
            )}
            <TabsContent value="contrats" className="space-y-4">
              {prospect.client_id != null ? (
                <ContratsTab clientId={prospect.client_id} nbLignesMobilesDeclare={prospect.nb_lignes_mobiles} />
              ) : (
                <ContratsTab prospectId={prospectId} nbLignesMobilesDeclare={prospect.nb_lignes_mobiles} />
              )}
            </TabsContent>
            <TabsContent value="documents">
              <DocumentsTab prospectId={prospectId} speedDown={prospect.speed_down} speedUp={prospect.speed_up} />
            </TabsContent>
            <TabsContent value="historique">
              <HistoriqueTab prospectId={prospectId} />
            </TabsContent>
          </Tabs>
        </div>
        <div className="lg:col-span-1">
          <ActionsCard
            prospect={prospect}
            prospectId={prospectId}
            dejaConverti={prospect.converti_at != null}
            clientId={prospect.client_id}
            convertiLe={prospect.converti_at}
            manquantsDiagnostic={champsObligatoiresDiagnosticManquants(prospect)}
            onSuppression={() => router.push("/prospects")}
          />
        </div>
      </div>
    </div>
  );
}

// Bandeau "dashboard" en tête de fiche — les indicateurs que le conseiller
// veut voir d'un coup d'œil pour prioriser : économie estimée, prochaine
// relance programmée, dernier contact enregistré, température du score.
function TableauBordProspect({ prospect }: { prospect: import("@/lib/types").Prospect }) {
  const tuiles = [
    { label: "Économie estimée", valeur: prospect.economie_estimee_an != null ? `${prospect.economie_estimee_an.toFixed(0)} €/an` : "—" },
    {
      label: "Prochaine relance",
      valeur: prospect.date_relance ? formatDateRelance(prospect.date_relance) : "Non planifiée",
      sousTitre: prospect.statut || undefined,
    },
    { label: "Dernier contact", valeur: prospect.dernier_contact || "Jamais" },
    { label: "Créneau de rappel souhaité", valeur: prospect.plage_horaire_rappel || "—" },
    { label: "Objectif de la demande", valeur: labelObjectifPrincipal(prospect.objectif_principal) || "—" },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
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
  prospect,
  defaultValues,
}: {
  prospect: import("@/lib/types").Prospect;
  defaultValues: ProspectUpdateInput;
}) {
  const prospectId = prospect.id;
  const updateMutation = prospectsResource.useUpdate({
    onSuccess: () => toast.success("Prospect mis à jour."),
  });

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="pt-6">
          <ProspectForm
            mode="edit"
            defaultValues={defaultValues}
            onSubmit={(values) => updateMutation.mutate({ id: prospectId, values: values as ProspectUpdateInput })}
            submitError={updateMutation.error}
            submitLabel="Enregistrer"
            isSubmitting={updateMutation.isPending}
          />
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
      {
        id: "pdf",
        header: "",
        cell: ({ row }) => (
          <a
            href={`/api/backend/dossiers/${row.original.id}/pdf-restitution`}
            download
            onClick={(e) => e.stopPropagation()}
          >
            <Button variant="outline" size="sm">
              Télécharger le PDF
            </Button>
          </a>
        ),
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

const LABELS_TYPE_DOCUMENT_PROSPECT: Record<string, string> = {
  facture: "Facture actuelle (opérateur / fournisseur)",
  speedtest: "Test de débit",
};

function DocumentsTab({
  prospectId,
  speedDown,
  speedUp,
}: {
  prospectId: number;
  speedDown: number | null;
  speedUp: number | null;
}) {
  const documentsQuery = useProspectDocuments(prospectId);
  const supprimerMutation = useSupprimerDocumentProspect(prospectId);
  const facturesQuery = useProspectFacturesAnalysees(prospectId);
  const typesRecus = new Set((documentsQuery.data ?? []).map((doc) => doc.type_document));

  const handleSupprimer = (documentId: number, label: string) => {
    if (!window.confirm(`Supprimer le document "${label}" ? Le prospect devra le retransmettre.`)) return;
    supprimerMutation.mutate(documentId, { onSuccess: () => toast.success("Document supprimé.") });
  };

  return (
    <Card>
      <CardContent className="space-y-2 pt-6">
        <ul className="divide-y mb-2">
          {Object.entries(LABELS_TYPE_DOCUMENT_PROSPECT).map(([type, label]) => {
            const mesure = type === "speedtest" && (speedDown != null || speedUp != null);
            return (
              <li key={type} className="flex items-center justify-between py-2 text-sm">
                <span className="font-medium">{label}</span>
                {mesure ? (
                  <div className="flex items-center gap-2">
                    <span className="text-emerald-900">
                      ↓ {speedDown != null ? `${speedDown.toFixed(1)} Mbit/s` : "—"} · ↑{" "}
                      {speedUp != null ? `${speedUp.toFixed(1)} Mbit/s` : "—"}
                    </span>
                    <RecuBadge label="Mesuré" />
                  </div>
                ) : typesRecus.has(type) ? (
                  <RecuBadge />
                ) : (
                  <AEnvoyerBadge />
                )}
              </li>
            );
          })}
        </ul>
        {documentsQuery.isLoading ? (
          <Skeleton className="h-48 w-full" />
        ) : !documentsQuery.data?.length ? (
          <p className="text-sm text-muted-foreground">Aucun document transmis.</p>
        ) : (
          <ul className="divide-y">
            {documentsQuery.data.map((doc) => (
              <li key={doc.id} className="flex items-center justify-between py-2 text-sm">
                <div className="space-y-0.5">
                  <p className="font-medium">{doc.type_document || doc.nom_fichier || "Document"}</p>
                  <p className="text-muted-foreground">{doc.date_upload}</p>
                </div>
                <div className="flex items-center gap-3">
                  <a href={doc.url} target="_blank" rel="noreferrer" className="text-primary underline">
                    Voir
                  </a>
                  <button
                    type="button"
                    className="text-destructive underline disabled:opacity-50"
                    disabled={supprimerMutation.isPending}
                    onClick={() => handleSupprimer(doc.id, doc.type_document || doc.nom_fichier || "Document")}
                  >
                    Supprimer
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
        {facturesQuery.data && facturesQuery.data.length > 0 && (
          <div className="mt-4 space-y-2 border-t pt-4">
            <p className="text-sm font-medium">Analyse automatique de la facture</p>
            {facturesQuery.data.map((facture) => (
              <div key={facture.id} className="rounded-md border p-3 text-sm">
                <dl className="grid grid-cols-2 gap-x-4 gap-y-1">
                  <dt className="text-muted-foreground">Opérateur</dt>
                  <dd>{facture.operateur || "—"}</dd>
                  <dt className="text-muted-foreground">Prix TTC</dt>
                  <dd>{facture.prix_ttc} €</dd>
                  {facture.data_conso_go > 0 && (
                    <>
                      <dt className="text-muted-foreground">Data</dt>
                      <dd>{facture.data_conso_go} Go</dd>
                    </>
                  )}
                  {facture.engagement_mois > 0 && (
                    <>
                      <dt className="text-muted-foreground">Engagement</dt>
                      <dd>{facture.engagement_mois} mois{facture.date_fin_engagement ? ` (jusqu'au ${facture.date_fin_engagement})` : ""}</dd>
                    </>
                  )}
                  {facture.type_couverture && (
                    <>
                      <dt className="text-muted-foreground">Formule assurance</dt>
                      <dd>{facture.type_couverture}</dd>
                    </>
                  )}
                  {facture.bonus_malus && (
                    <>
                      <dt className="text-muted-foreground">Bonus/malus</dt>
                      <dd>{facture.bonus_malus}</dd>
                    </>
                  )}
                  {facture.options && facture.options.length > 0 && (
                    <>
                      <dt className="text-muted-foreground">Options</dt>
                      <dd>{facture.options.join(", ")}</dd>
                    </>
                  )}
                </dl>
                <p className="mt-2 text-xs text-muted-foreground">Analysée le {facture.date_analyse}</p>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function HistoriqueTab({ prospectId }: { prospectId: number }) {
  const historiqueQuery = useProspectHistorique(prospectId);

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

function ActionsCard({
  prospect,
  prospectId,
  dejaConverti,
  clientId,
  convertiLe,
  manquantsDiagnostic,
  onSuppression,
}: {
  prospect: import("@/lib/types").Prospect;
  prospectId: number;
  dejaConverti: boolean;
  clientId: number | null;
  convertiLe: string | null;
  manquantsDiagnostic: string[];
  onSuppression: () => void;
}) {
  const router = useRouter();
  const [lienOpen, setLienOpen] = useState(false);
  const [lienUrl, setLienUrl] = useState<string | null>(null);
  const [appelOpen, setAppelOpen] = useState(false);
  const [modeLienOpen, setModeLienOpen] = useState(false);

  const lienMutation = useGenererLienDocumentsProspect();
  const envoyerLienMutation = useEnvoyerLienDocumentsProspect();
  const deleteMutation = prospectsResource.useDelete();
  const relanceMutation = useRelanceEffectuee();
  const convertirMutation = useConvertirProspect();
  const appelMutation = useContacterTelephone();
  const contratsQuery = useContrats({ prospectId });

  const handleConvertir = () => {
    convertirMutation.mutate(prospectId, {
      onSuccess: () => toast.success("Prospect converti en client."),
      onError: () => toast.error("Échec de la conversion — vérifiez que les documents requis sont validés."),
    });
  };

  const handleRelanceEffectuee = () => {
    relanceMutation.mutate(prospectId, {
      onSuccess: () => toast.success("Relance enregistrée — prochaine relance programmée dans 7 jours."),
    });
  };

  const handleContacterTelephone = (repondu: boolean) => {
    appelMutation.mutate(
      { prospectId, repondu },
      {
        onSuccess: () => {
          setAppelOpen(false);
          toast.success(
            repondu
              ? "Appel enregistré — prochaine relance programmée dans 7 jours."
              : "Appel sans réponse enregistré — SMS/email envoyé, relance programmée dans 7 jours."
          );
        },
      }
    );
  };

  const handleChoisirModeLien = (remplissageAutonome: boolean) => {
    setModeLienOpen(false);
    if (remplissageAutonome) {
      lienMutation.mutate(
        { prospectId, remplissageAutonome: true },
        {
          onSuccess: (data) => {
            setLienUrl(data.url);
            setLienOpen(true);
          },
        }
      );
      return;
    }
    // Mode "au téléphone" : le conseiller remplit lui-même le lien avec le
    // client — ouverture synchrone (avant tout await) pour ne pas être
    // bloquée par le navigateur, même principe que handlePreRemplir côté
    // dossiers/[id]/page.tsx.
    const fenetre = window.open("", "_blank");
    lienMutation.mutate(
      { prospectId, remplissageAutonome: false },
      {
        onSuccess: (data) => {
          if (fenetre) fenetre.location.href = data.url;
          else toast.warning("Autorisez les fenêtres popup pour ouvrir le lien directement.");
        },
      }
    );
  };

  const handleEnvoyerParEmail = () => {
    envoyerLienMutation.mutate(
      { prospectId, canal: "email" },
      {
        onSuccess: (data) => {
          toast.success(data.email_envoye ? "Lien envoyé par email." : "Échec de l'envoi de l'email.");
        },
      }
    );
  };

  const handleCopier = async () => {
    if (!lienUrl) return;
    await navigator.clipboard.writeText(lienUrl);
    toast.success("Lien copié.");
  };

  const handleAideMemoire = () => {
    const lignesMobiles = contratsQuery.data?.filter((c) => c.categorie === "Forfait mobile" || c.categorie === "Mobile");
    const ligneMobile = lignesMobiles?.find((c) => c.ligne_principale) ?? lignesMobiles?.[0];
    const params = new URLSearchParams({
      prenom: prospect.prenom ?? "",
      nom: prospect.nom ?? "",
      telephone: prospect.telephone ?? "",
      email: prospect.email ?? "",
      adresse: prospect.adresse ?? "",
      code_postal: prospect.code_postal ?? "",
      ville: prospect.ville ?? "",
      conserver_numero: ligneMobile?.conserver_numero ?? "",
      rio: ligneMobile?.rio ?? "",
      numero_ligne: ligneMobile?.numero_ligne ?? "",
      type_sim: ligneMobile?.type_sim ?? "",
    });
    const fenetre = window.open(`/souscription-reference?${params.toString()}`, "cmr-reference-souscription");
    if (!fenetre) toast.warning("Autorisez les fenêtres popup pour ce site afin d'ouvrir l'aide-mémoire.");
  };

  const handleSupprimer = () => {
    if (!window.confirm("Supprimer définitivement ce prospect ?")) return;
    deleteMutation.mutate(prospectId, { onSuccess: onSuppression });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Actions</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {dejaConverti ? (
          <div className="rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
            <p className="font-medium">Converti en client{convertiLe ? ` le ${convertiLe}` : ""}</p>
            {clientId != null && (
              <button type="button" className="underline" onClick={() => router.push(`/clients/${clientId}`)}>
                Voir la fiche client →
              </button>
            )}
          </div>
        ) : (
          <div className="space-y-2 rounded-md border px-3 py-2 text-sm text-muted-foreground">
            <p>
              Sera converti automatiquement en client à la signature de son mandat de représentation, une fois tous
              les documents requis validés (voir le dossier associé).
            </p>
            {clientId != null && (
              <Button
                variant="outline"
                size="sm"
                className="w-full"
                onClick={handleConvertir}
                disabled={convertirMutation.isPending}
              >
                {convertirMutation.isPending ? "Conversion…" : "Convertir en client maintenant"}
              </Button>
            )}
          </div>
        )}
        <Button variant="outline" className="w-full" onClick={() => setAppelOpen(true)}>
          Contacter par téléphone
        </Button>
        <Button variant="outline" className="w-full" onClick={() => setModeLienOpen(true)} disabled={lienMutation.isPending}>
          Envoyer lien collecte docs
        </Button>
        <Button variant="outline" className="w-full" onClick={handleAideMemoire}>
          Aide-mémoire souscription
        </Button>
        <Button variant="outline" className="w-full" onClick={handleRelanceEffectuee} disabled={relanceMutation.isPending}>
          Relance effectuée ce jour
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
          onClick={() => router.push(`/diagnostic?entiteType=prospect&entiteId=${prospectId}`)}
        >
          Nouveau diagnostic
        </Button>
        <Button variant="destructive" className="w-full" onClick={handleSupprimer} disabled={deleteMutation.isPending}>
          Supprimer
        </Button>
      </CardContent>

      <Dialog open={modeLienOpen} onOpenChange={setModeLienOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Comment le client va-t-il répondre ?</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <Button
              className="w-full justify-start"
              onClick={() => handleChoisirModeLien(true)}
              disabled={lienMutation.isPending}
            >
              Le client répond seul
            </Button>
            <p className="text-xs text-muted-foreground px-1">
              Formulaire allégé (questions importantes uniquement) — le reste sera redemandé à la signature des mandats.
            </p>
            <Button
              variant="outline"
              className="w-full justify-start"
              onClick={() => handleChoisirModeLien(false)}
              disabled={lienMutation.isPending}
            >
              Je réponds avec lui au téléphone
            </Button>
            <p className="text-xs text-muted-foreground px-1">
              Ouvre directement le lien complet dans un nouvel onglet pour le remplir en direct avec le client.
            </p>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={lienOpen} onOpenChange={setLienOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Lien de collecte de documents</DialogTitle>
          </DialogHeader>
          <div className="flex gap-2">
            <Input readOnly value={lienUrl ?? ""} />
            <Button onClick={handleCopier}>Copier</Button>
          </div>
          <Button variant="outline" onClick={handleEnvoyerParEmail} disabled={envoyerLienMutation.isPending}>
            {envoyerLienMutation.isPending ? "Envoi…" : "Envoyer par email"}
          </Button>
        </DialogContent>
      </Dialog>

      <Dialog open={appelOpen} onOpenChange={setAppelOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Le client a-t-il répondu ?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            La prochaine relance sera programmée dans 7 jours. En cas d'absence de réponse, un
            SMS et un email sont envoyés au client pour l'informer de votre appel.
          </p>
          <div className="flex gap-2">
            <Button className="flex-1" onClick={() => handleContacterTelephone(true)} disabled={appelMutation.isPending}>
              Oui, il a répondu
            </Button>
            <Button
              variant="outline"
              className="flex-1"
              onClick={() => handleContacterTelephone(false)}
              disabled={appelMutation.isPending}
            >
              Non, pas de réponse
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
