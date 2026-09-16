"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { ContratForm, contratToFormValues, estForfaitBox } from "@/components/clients/ContratForm";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { DataTable } from "@/components/ui/data-table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { groupeContrat, type GroupeContrat } from "@/lib/contratsGroupes";
import { useClientAlertes } from "@/lib/hooks/useClients";
import {
  contratsResource,
  useContrats,
  useContratsEstimation,
  type LigneEstimationContrat,
} from "@/lib/hooks/useContrats";
import type { ContratCreateInput, ContratUpdateInput } from "@/lib/schemas/contrat";
import type { Contrat } from "@/lib/types";

// Contrats créés avant l'ajout du champ "Type" (categorie) au formulaire ne
// portent que l'ancien `univers` technique ("telecom_mobile") — on le
// retraduit ici pour rester lisible, sans migration de données.
const LABELS_UNIVERS_CONTRAT: Record<string, string> = {
  telecom_mobile: "Forfait mobile",
  telecom_box: "Box internet",
  energie: "Énergie",
  energie_pro: "Énergie pro",
  assurance_habitation: "Assurance habitation",
};

// `Contrat.categorie` mélange deux vocabulaires stockés tels quels (voir
// contratsGroupes.ts) — on ne renomme que l'affichage ("Box internet"), la
// valeur brute reste inchangée en base et dans les comparaisons backend.
const LABELS_CATEGORIE_CONTRAT: Record<string, string> = {
  "Forfait box": "Box internet",
  "Box / Fibre": "Box internet",
  "Pack Box + Mobile": "Pack Box internet + Mobile",
};

function labelTypeContrat(contrat: Contrat): string {
  if (contrat.categorie) return LABELS_CATEGORIE_CONTRAT[contrat.categorie] ?? contrat.categorie;
  if (contrat.univers) return LABELS_UNIVERS_CONTRAT[contrat.univers] ?? contrat.univers;
  return "—";
}

// Champs qu'un conseiller doit renseigner pour exploiter un contrat créé
// automatiquement depuis /economiser (souvent incomplet : pas de fournisseur
// pour l'énergie/assurance, pas de type choisi…).
function champsManquants(contrat: Contrat): string[] {
  const manquants: string[] = [];
  if (!contrat.categorie) manquants.push("Type");
  if (!contrat.fournisseur) manquants.push("Fournisseur");
  if (contrat.cout_mensuel == null) manquants.push("Prix mensuel");
  return manquants;
}

// Bandeau de fourchette d'économie annuelle — même moteur que la landing
// publique /economiser, appliqué aux contrats "Actuel" (situation avant nous)
// de l'entité (voir backend/routers/contrats.py::estimer_contrats).
function EstimationBanner({ clientId, prospectId }: { clientId?: number; prospectId?: number }) {
  const estimationQuery = useContratsEstimation({ clientId, prospectId });
  const estimation = estimationQuery.data;

  if (!estimation || estimation.economie_annuelle_totale_typique <= 0) return null;

  return (
    <div className="rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
      Économie totale estimée :{" "}
      <span className="font-bold">
        {estimation.economie_annuelle_totale_basse.toFixed(0)} € – {estimation.economie_annuelle_totale_haute.toFixed(0)} €/an
      </span>{" "}
      (typique {estimation.economie_annuelle_totale_typique.toFixed(0)} €/an), calculée à partir des contrats "Actuel".
    </div>
  );
}

interface ContratsTabProps {
  clientId?: number;
  prospectId?: number;
  // Prospect.nb_lignes_mobiles (M1, docs/QUESTIONS_PAR_SECTEUR.md) — quand
  // "2+" et qu'une seule ligne "Forfait mobile" (ou aucune) n'existe encore,
  // affiche un bandeau invitant le conseiller à préciser le détail obtenu au
  // téléphone (combien de lignes, même opérateur).
  nbLignesMobilesDeclare?: string | null;
}

// Onglet "Contrats en cours" — réutilisé par la fiche client (clients/[id]/page.tsx)
// et la fiche prospect (prospects/[id]/page.tsx) : un prospect a souvent déjà
// des contrats en cours chez un concurrent avant de devenir client.
export function ContratsTab({ clientId, prospectId, nbLignesMobilesDeclare }: ContratsTabProps) {
  const contratsQuery = useContrats({ clientId, prospectId });
  const estimationQuery = useContratsEstimation({ clientId, prospectId });
  const alertesQuery = useClientAlertes(clientId);
  const [createOpen, setCreateOpen] = useState(false);
  const [categoriePreselectionnee, setCategoriePreselectionnee] = useState<string | undefined>();
  const [editing, setEditing] = useState<Contrat | null>(null);
  const [viewing, setViewing] = useState<Contrat | null>(null);
  const [ongletActif, setOngletActif] = useState<GroupeContrat | "Tous">("Tous");

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

  const lignesEstimation = estimationQuery.data?.lignes;

  const columns = useMemo<ColumnDef<Contrat>[]>(
    () => [
      {
        id: "type",
        header: "Type",
        cell: ({ row }) => (
          <span className="inline-flex items-center gap-1.5">
            {labelTypeContrat(row.original)}
            {row.original.ligne_principale && (
              <Badge variant="outline" className="border-blue-300 bg-blue-50 text-blue-800">
                Ligne principale
              </Badge>
            )}
          </span>
        ),
      },
      { accessorKey: "fournisseur", header: "Fournisseur" },
      {
        id: "cout_mensuel",
        header: "Prix mensuel",
        accessorFn: (c) => (c.cout_mensuel != null ? `${c.cout_mensuel} €` : "—"),
      },
      {
        accessorKey: "consommation",
        header: "Consommation / Débit",
        cell: ({ row }) => row.original.consommation || "—",
      },
      {
        id: "chez_nous",
        header: "Chez nous",
        cell: ({ row }) =>
          row.original.chez_nous ? (
            <Badge className="bg-emerald-100 text-emerald-800 hover:bg-emerald-100">Chez nous</Badge>
          ) : (
            <Badge variant="outline">Concurrent</Badge>
          ),
      },
      {
        id: "statut_contrat",
        header: "Statut",
        cell: ({ row }) => <Badge variant="secondary">{row.original.statut_contrat || "—"}</Badge>,
      },
      { accessorKey: "date_fin_engagement", header: "Date fin engagement" },
      {
        id: "economie_estimee",
        header: "Économie estimée",
        cell: ({ row }) => {
          if (row.original.chez_nous) return null;
          const ligne = lignesEstimation?.find((l) => l.categorie === row.original.categorie);
          if (!ligne || ligne.economie_mensuelle_haute <= 0) return <span className="text-muted-foreground">—</span>;
          return (
            <span className="text-emerald-700 font-medium whitespace-nowrap">
              {ligne.economie_mensuelle_basse.toFixed(0)}–{ligne.economie_mensuelle_haute.toFixed(0)} €/mois
            </span>
          );
        },
      },
      {
        id: "a_completer",
        header: "",
        cell: ({ row }) => {
          const manquants = champsManquants(row.original);
          if (manquants.length === 0) return null;
          return (
            <Badge
              variant="outline"
              className="border-amber-300 bg-amber-50 text-amber-800"
              title={`À compléter : ${manquants.join(", ")}`}
            >
              À compléter
            </Badge>
          );
        },
      },
    ],
    [lignesEstimation]
  );

  const toutesLesDonnees = contratsQuery.data ?? [];
  const contratsParGroupe = useMemo(() => {
    const compte: Record<GroupeContrat, number> = { Télécom: 0, Énergie: 0, Assurance: 0, Autres: 0 };
    for (const contrat of toutesLesDonnees) compte[groupeContrat(contrat)] += 1;
    return compte;
  }, [toutesLesDonnees]);
  const nbACompleter = useMemo(
    () => toutesLesDonnees.filter((c) => champsManquants(c).length > 0).length,
    [toutesLesDonnees]
  );
  const donneesAffichees =
    ongletActif === "Tous" ? toutesLesDonnees : toutesLesDonnees.filter((c) => groupeContrat(c) === ongletActif);

  const alertesEconomie = (alertesQuery.data ?? []).reduce((total, a) => total + (a.economie_mensuelle ?? 0), 0);

  const handleDelete = (contrat: Contrat) => {
    if (!window.confirm(`Supprimer le contrat ${contrat.fournisseur ?? ""} ?`)) return;
    deleteMutation.mutate(contrat.id);
  };

  const rattachement = clientId != null ? { client_id: clientId } : { prospect_id: prospectId };
  const nbLignesMobiles = toutesLesDonnees.filter((c) => c.categorie === "Forfait mobile").length;
  const ouvrirCreationLigneMobile = () => {
    setCategoriePreselectionnee("Forfait mobile");
    setCreateOpen(true);
  };

  return (
    <Card>
      <CardContent className="space-y-4 pt-6">
        <EstimationBanner clientId={clientId} prospectId={prospectId} />
        {nbLignesMobilesDeclare === "2+" && nbLignesMobiles <= 1 && (
          <div className="flex items-center justify-between gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            <span>Le prospect a déclaré 2+ lignes mobiles — précisez le détail obtenu au téléphone.</span>
            <Button size="sm" variant="outline" onClick={ouvrirCreationLigneMobile}>
              Ajouter une ligne mobile
            </Button>
          </div>
        )}
        {!!alertesQuery.data?.length && (
          <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            {alertesQuery.data.length} offre(s) moins chère(s) détectée(s) — économie potentielle estimée à{" "}
            {alertesEconomie.toFixed(2)} €/mois.
          </div>
        )}
        {nbACompleter > 0 && (
          <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            {nbACompleter} contrat{nbACompleter > 1 ? "s" : ""} à compléter (type, fournisseur ou prix manquant).
          </div>
        )}
        <div className="flex items-center justify-between gap-2">
          <Tabs value={ongletActif} onValueChange={(v) => setOngletActif(v as GroupeContrat | "Tous")}>
            <TabsList>
              <TabsTrigger value="Tous">Tous ({toutesLesDonnees.length})</TabsTrigger>
              <TabsTrigger value="Télécom">Télécom ({contratsParGroupe.Télécom})</TabsTrigger>
              <TabsTrigger value="Énergie">Énergie ({contratsParGroupe.Énergie})</TabsTrigger>
              <TabsTrigger value="Assurance">Assurance ({contratsParGroupe.Assurance})</TabsTrigger>
              {contratsParGroupe.Autres > 0 && (
                <TabsTrigger value="Autres">Autres ({contratsParGroupe.Autres})</TabsTrigger>
              )}
            </TabsList>
          </Tabs>
          <Button onClick={() => setCreateOpen(true)}>Ajouter contrat</Button>
        </div>
        {contratsQuery.isLoading ? (
          <Skeleton className="h-48 w-full" />
        ) : (
          <DataTable
            columns={columns}
            data={donneesAffichees}
            emptyMessage="Aucun contrat rattaché."
            onRowClick={(contrat) => setViewing(contrat)}
            rowActions={(contrat) => (
              <>
                <DropdownMenuItem onSelect={() => setViewing(contrat)}>Voir</DropdownMenuItem>
                <DropdownMenuItem onSelect={() => setEditing(contrat)}>Modifier</DropdownMenuItem>
                <DropdownMenuItem onSelect={() => handleDelete(contrat)} className="text-destructive">
                  Supprimer
                </DropdownMenuItem>
              </>
            )}
          />
        )}
      </CardContent>

      <Dialog
        open={createOpen}
        onOpenChange={(open) => {
          setCreateOpen(open);
          if (!open) setCategoriePreselectionnee(undefined);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Ajouter un contrat</DialogTitle>
          </DialogHeader>
          <ContratForm
            mode="create"
            defaultValues={{ ...rattachement, fournisseur: "", categorie: categoriePreselectionnee } as ContratCreateInput}
            onSubmit={(values) => createMutation.mutate({ ...(values as ContratCreateInput), ...rattachement })}
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

      <Dialog open={viewing !== null} onOpenChange={(open) => !open && setViewing(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{viewing ? labelTypeContrat(viewing) : "Contrat"}</DialogTitle>
          </DialogHeader>
          {viewing && (
            <ContratDetailView
              contrat={viewing}
              ligneEstimation={estimationQuery.data?.lignes.find((l) => l.categorie === viewing.categorie)}
              onModifier={() => { setEditing(viewing); setViewing(null); }}
            />
          )}
        </DialogContent>
      </Dialog>
    </Card>
  );
}

function ContratDetailView({
  contrat,
  ligneEstimation,
  onModifier,
}: {
  contrat: Contrat;
  ligneEstimation?: LigneEstimationContrat;
  onModifier: () => void;
}) {
  const champs: Array<[string, string]> = [
    ["Type", labelTypeContrat(contrat)],
    ["Fournisseur", contrat.fournisseur || "—"],
    ["Offre", contrat.nom_offre || "—"],
    ["Prix mensuel", contrat.cout_mensuel != null ? `${contrat.cout_mensuel} €` : "—"],
    [estForfaitBox(contrat.categorie ?? undefined) ? "Débit" : "Consommation", contrat.consommation || "—"],
    ["Chez nous", contrat.chez_nous ? "Oui" : "Non"],
    ["Statut", contrat.statut_contrat || "—"],
    ["Date de souscription", contrat.date_souscription || "—"],
    ["Fin d'engagement", contrat.date_fin_engagement || "—"],
    ["Référence", contrat.reference_contrat || "—"],
  ];

  if (contrat.categorie === "Forfait mobile") {
    champs.push(["Ligne principale", contrat.ligne_principale ? "Oui" : "Non"]);
    if (contrat.meme_operateur_mobile != null) {
      champs.push(["Même opérateur (toutes lignes)", contrat.meme_operateur_mobile ? "Oui" : "Non"]);
    }
    if (contrat.conserver_numero) {
      champs.push(["Conserver le numéro", contrat.conserver_numero === "oui" ? "Oui" : "Non"]);
    }
    if (contrat.numero_ligne) champs.push(["Numéro de ligne", contrat.numero_ligne]);
    if (contrat.rio) champs.push(["RIO", contrat.rio]);
    if (contrat.type_sim) champs.push(["Type de SIM", contrat.type_sim === "esim" ? "eSIM" : "Carte SIM"]);
  }

  // Trame Box B3/B3b/B4/B5/B6/B7 (docs/QUESTIONS_PAR_SECTEUR.md), posée sur
  // /economiser ou le lien personnel du prospect — affichée ici pour que le
  // conseiller la voie sans redemander au téléphone.
  if (estForfaitBox(contrat.categorie ?? undefined)) {
    if (contrat.usage_tv) champs.push(["TV via la box", contrat.usage_tv]);
    if (contrat.abonnements_payants) champs.push(["Abonnements payants", contrat.abonnements_payants]);
    if (contrat.nb_utilisateurs_streaming) champs.push(["Utilisateurs simultanés streaming", contrat.nb_utilisateurs_streaming]);
    if (contrat.usage_4k != null) champs.push(["Vidéo 4K régulière", contrat.usage_4k ? "Oui" : "Non"]);
    if (contrat.teletravail) champs.push(["Télétravail", contrat.teletravail]);
    if (contrat.interet_box_4g5g) champs.push(["Intérêt box 4G/5G", contrat.interet_box_4g5g]);
    if (contrat.telephone_fixe_utilise) champs.push(["Téléphone fixe utilisé", contrat.telephone_fixe_utilise === "oui" ? "Oui" : "Non"]);
    if (contrat.appels_fixe_mensuels) champs.push(["Appels fixe / mois", contrat.appels_fixe_mensuels]);
  }

  // "Situation actuelle" utile aussi bien pour un contrat concurrent
  // (situation avant conversion) qu'un contrat chez nous (défaut technique à
  // vérifier sur une ligne déjà souscrite) — seul l'univers (mobile/box)
  // détermine si ces champs ont du sens, pas le fait qu'il soit chez nous.
  if (/mobile|box/i.test(contrat.categorie ?? "")) {
    if (contrat.satisfaction_reseau) champs.push(["Satisfaction réseau", contrat.satisfaction_reseau]);
    if (contrat.veut_rester) champs.push(["Souhaite rester", contrat.veut_rester]);
    if (contrat.defaut_technique) champs.push(["Défaut technique", contrat.defaut_technique]);
    if (contrat.speed_down || contrat.speed_up) {
      champs.push(["Débit mesuré", `${contrat.speed_down ?? "—"} Mbps ↓ / ${contrat.speed_up ?? "—"} Mbps ↑`]);
    }
  }
  champs.push(["Notes", contrat.notes || "—"]);

  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
        {champs.map(([label, valeur]) => (
          <div key={label}>
            <dt className="text-muted-foreground">{label}</dt>
            <dd className="font-medium">{valeur}</dd>
          </div>
        ))}
      </dl>
      {!contrat.chez_nous && ligneEstimation && ligneEstimation.economie_annuelle_typique > 0 && (
        <div className="rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
          Économie estimée :{" "}
          <span className="font-bold">
            {ligneEstimation.economie_mensuelle_basse.toFixed(0)} € – {ligneEstimation.economie_mensuelle_haute.toFixed(0)} €/mois
          </span>{" "}
          (soit {ligneEstimation.economie_annuelle_typique.toFixed(0)} €/an typique).
        </div>
      )}
      <Button onClick={onModifier}>Modifier</Button>
    </div>
  );
}
