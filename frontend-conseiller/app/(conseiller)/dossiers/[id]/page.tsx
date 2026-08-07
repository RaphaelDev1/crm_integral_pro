"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { CheckCircle2, Circle, Clock } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useClientDocuments, useSupprimerDocumentClient, useValiderDocumentClient } from "@/lib/hooks/useClients";
import { clientsResource } from "@/lib/hooks/useClients";
import {
  useCreerDemarche,
  useDemarchesDossier,
  useEnvoyerDemarche,
  useGenererDemarche,
} from "@/lib/hooks/useDemarches";
import {
  dossiersResource,
  useAjouterNoteDossier,
  useDossierTimeline,
  useEnvoyerLienClientDossier,
  useGenererLienClientDossier,
  useTransitionDossier,
} from "@/lib/hooks/useDossiers";
import { useComparaisonDossier, useOffresComparees } from "@/lib/hooks/useOffres";
import {
  useCreerMandatHonoraires,
  useEnvoyerMandatHonoraires,
  useMandatHonoraires,
  useMarquerSigneHonoraires,
  useTauxHonorairesDefaut,
  useTelechargerMandatHonoraires,
} from "@/lib/hooks/useHonoraires";
import { useEnvoyerMandat, useMandat, useMarquerMandatSigne } from "@/lib/hooks/useMandat";
import { LABELS_STATUT_DOSSIER, TRANSITIONS_AUTORISEES, statutDossierBadgeClass, type StatutDossier } from "@/lib/dossierStatuts";
import type { Demarche } from "@/lib/types";

export default function DossierDetailPage() {
  const params = useParams<{ id: string }>();
  const dossierId = Number(params.id);

  const dossierQuery = dossiersResource.useOne(dossierId);
  const clientQuery = clientsResource.useOne(dossierQuery.data?.client_id);

  if (dossierQuery.isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (!dossierQuery.data) {
    return <p className="text-sm text-slate-500">Dossier introuvable.</p>;
  }

  const dossier = dossierQuery.data;

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-primary">
            Dossier #{dossier.id} — {dossier.univers}
          </h1>
          <p className="text-sm text-muted-foreground">
            Client : {clientQuery.data ? `${clientQuery.data.prenom ?? ""} ${clientQuery.data.nom ?? ""}` : "…"}
          </p>
          {(dossier.fournisseur_cible || dossier.offre_nom) && (
            <p className="text-sm font-medium text-primary mt-1">
              Offre visée : {[dossier.fournisseur_cible, dossier.offre_nom].filter(Boolean).join(" — ")}
            </p>
          )}
          {dossier.frais_annexes_cible > 0 ? (
            <p className="text-sm text-muted-foreground mt-1">
              Économie 1ère année (frais inclus : {dossier.frais_annexes_cible.toFixed(0)} € — SIM, résiliation,
              portabilité…) : {(dossier.economie_annuelle_estimee - dossier.frais_annexes_cible).toFixed(0)} € · à
              partir de l&apos;année 2 : {dossier.economie_annuelle_estimee.toFixed(0)} €/an
            </p>
          ) : (
            dossier.economie_annuelle_estimee > 0 && (
              <p className="text-sm text-muted-foreground mt-1">
                Économie estimée : {dossier.economie_annuelle_estimee.toFixed(0)} €/an
              </p>
            )
          )}
        </div>
        <div className="flex flex-col items-end gap-2">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className={statutDossierBadgeClass(dossier.statut)}>
              {LABELS_STATUT_DOSSIER[dossier.statut as StatutDossier] ?? dossier.statut}
            </Badge>
            <a href={`/api/backend/dossiers/${dossier.id}/pdf-restitution`} download>
              <Button variant="outline">Télécharger restitution</Button>
            </a>
          </div>
          <ActionsTransitionSection
            dossierId={dossierId}
            statut={dossier.statut as StatutDossier}
            clientId={dossier.client_id}
            documentsRequis={dossier.documents_requis}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <TimelineSection dossierId={dossierId} />
          <OffreCibleSection dossier={dossier} />
          <DocumentsSection dossierId={dossierId} clientId={dossier.client_id} documentsRequis={dossier.documents_requis} />
        </div>
        <div className="space-y-6">
          <MandatRepresentationSection dossierId={dossierId} />
          <MandatHonorairesSection dossierId={dossierId} />
          <DemarchesSection dossierId={dossierId} />
          <NotesSection dossierId={dossierId} notesWorkflow={dossier.notes_workflow} />
        </div>
      </div>
    </div>
  );
}

const ICONE_PAR_CLE = { check: CheckCircle2, clock: Clock, circle: Circle } as const;

function TimelineSection({ dossierId }: { dossierId: number }) {
  const timelineQuery = useDossierTimeline(dossierId);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Timeline</CardTitle>
      </CardHeader>
      <CardContent>
        {timelineQuery.isLoading ? (
          <Skeleton className="h-48 w-full" />
        ) : (
          <ol className="space-y-3">
            {(timelineQuery.data ?? []).map((etape) => {
              const Icone = ICONE_PAR_CLE[etape.icone] ?? Circle;
              const couleur =
                etape.statut === "termine"
                  ? "text-emerald-600"
                  : etape.statut === "en_cours"
                    ? "text-amber-600"
                    : "text-slate-300";
              return (
                <li key={etape.cle} className="flex items-start gap-3 text-sm">
                  <Icone className={`h-5 w-5 shrink-0 ${couleur}`} />
                  <div>
                    <p className="font-medium">{etape.label}</p>
                    {etape.date && <p className="text-muted-foreground">{etape.date}</p>}
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}

interface OffreChoisie {
  offre_id: number;
  nom?: string | null;
  fournisseur?: string | null;
  economie_mensuelle?: number | null;
  frais_annexes_total?: number | null;
}

// Permet de choisir l'offre visée du dossier parmi celles comparées lors du
// diagnostic (comparaison.offres_comparees), ou d'en chercher une autre dans
// le catalogue (même univers/catégorie) — PUT /dossiers/{id} accepte déjà
// offre_cible_id/fournisseur_cible, il manquait juste l'UI pour le déclencher.
function OffreCibleSection({ dossier }: { dossier: import("@/lib/types").Dossier }) {
  const comparaisonQuery = useComparaisonDossier(dossier.id);
  const updateMutation = dossiersResource.useUpdate();
  const [rechercheOuverte, setRechercheOuverte] = useState(false);

  const choisirOffre = (offre: OffreChoisie) => {
    updateMutation.mutate(
      {
        id: dossier.id,
        values: {
          offre_cible_id: offre.offre_id,
          fournisseur_cible: offre.fournisseur ?? undefined,
          economie_annuelle_estimee: offre.economie_mensuelle != null ? offre.economie_mensuelle * 12 : undefined,
          frais_annexes_cible: offre.frais_annexes_total ?? undefined,
        },
      },
      {
        onSuccess: () => {
          toast.success("Offre visée mise à jour.");
          setRechercheOuverte(false);
        },
      }
    );
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Offre visée</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {comparaisonQuery.isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : !comparaisonQuery.data?.offres_comparees?.length ? (
          <p className="text-sm text-muted-foreground">Aucune comparaison enregistrée pour ce dossier.</p>
        ) : (
          <ul className="space-y-2">
            {comparaisonQuery.data.offres_comparees.map((offre) => {
              const active = dossier.offre_cible_id === offre.offre_id;
              return (
                <li
                  key={offre.offre_id}
                  className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
                >
                  <div>
                    <p className="font-medium">{[offre.fournisseur, offre.nom].filter(Boolean).join(" — ")}</p>
                    {offre.prix_mensuel != null && (
                      <p className="text-muted-foreground">{offre.prix_mensuel.toFixed(2)} €/mois</p>
                    )}
                  </div>
                  <Button
                    size="sm"
                    variant={active ? "secondary" : "outline"}
                    disabled={active || updateMutation.isPending}
                    onClick={() => choisirOffre(offre)}
                  >
                    {active ? "Offre visée" : "Choisir"}
                  </Button>
                </li>
              );
            })}
          </ul>
        )}
        <Button variant="outline" size="sm" onClick={() => setRechercheOuverte((v) => !v)}>
          {rechercheOuverte ? "Fermer la recherche" : "Choisir une autre offre"}
        </Button>
        {rechercheOuverte && (
          <RechercheAutreOffre
            univers={comparaisonQuery.data?.univers ?? dossier.univers}
            categorie={comparaisonQuery.data?.categorie ?? ""}
            coutActuel={comparaisonQuery.data?.cout_actuel_mensuel ?? 0}
            onChoisir={choisirOffre}
            isPending={updateMutation.isPending}
          />
        )}
      </CardContent>
    </Card>
  );
}

function RechercheAutreOffre({
  univers,
  categorie,
  coutActuel,
  onChoisir,
  isPending,
}: {
  univers: string;
  categorie: string;
  coutActuel: number;
  onChoisir: (offre: OffreChoisie) => void;
  isPending: boolean;
}) {
  const query = useOffresComparees(
    { univers, categorie, cout_actuel_mensuel: coutActuel },
    !!univers && !!categorie
  );

  if (!categorie) {
    return <p className="text-sm text-muted-foreground">Catégorie inconnue pour ce dossier — recherche indisponible.</p>;
  }

  return (
    <div className="space-y-2 border-t pt-3">
      {query.isLoading ? (
        <Skeleton className="h-16 w-full" />
      ) : !query.data?.length ? (
        <p className="text-sm text-muted-foreground">Aucune autre offre trouvée dans le catalogue.</p>
      ) : (
        query.data.map((offre) => (
          <div key={offre.id} className="flex items-center justify-between text-sm">
            <span>
              {offre.fournisseur} — {offre.nom} ({offre.prix_mensuel.toFixed(2)} €/mois)
            </span>
            <Button
              size="sm"
              variant="outline"
              disabled={isPending}
              onClick={() =>
                onChoisir({
                  offre_id: offre.id,
                  nom: offre.nom,
                  fournisseur: offre.fournisseur,
                  economie_mensuelle: offre.economie_mensuelle,
                  frais_annexes_total: offre.frais_annexes_total,
                })
              }
            >
              Choisir
            </Button>
          </div>
        ))
      )}
    </div>
  );
}

const LABELS_TYPE_DOCUMENT: Record<string, string> = {
  cni: "Pièce d'identité",
  rib: "RIB",
  justificatif_domicile: "Justificatif de domicile",
};

function labelTypeDocument(type: string) {
  return LABELS_TYPE_DOCUMENT[type] ?? type;
}

function ActionsTransitionSection({
  dossierId,
  statut,
  clientId,
  documentsRequis,
}: {
  dossierId: number;
  statut: StatutDossier;
  clientId: number;
  documentsRequis: string[];
}) {
  const [cible, setCible] = useState<StatutDossier | null>(null);
  const [commentaire, setCommentaire] = useState("");
  const transitionMutation = useTransitionDossier();
  const documentsQuery = useClientDocuments(clientId);

  // "docs_demandes" est exclu des boutons manuels : cette transition se
  // déclenche déjà automatiquement à l'envoi du lien de collecte (voir
  // backend/routers/dossiers.py::_marquer_docs_demandes_si_besoin) — l'action
  // du conseiller ICI, c'est d'envoyer ce lien, pas de cliquer un bouton en plus.
  const transitionsPossibles = (TRANSITIONS_AUTORISEES[statut] ?? []).filter(
    (s) => !(statut === "initie" && s === "docs_demandes")
  );
  // Manquant = requis pour cet univers mais absent, ou présent avec un statut
  // différent de "valide" (à_fournir, en_attente, rejeté...). Comparer
  // uniquement les documents déjà reçus (comme avant) revenait à considérer
  // "tout est bon" dès que rien n'avait été envoyé (0 document non valide sur 0
  // document reçu) — c'est ce qui laissait passer un dossier sans aucune pièce.
  const documentsParType = new Map((documentsQuery.data ?? []).map((d) => [d.type_document, d]));
  const documentsManquants = documentsRequis.filter((type) => documentsParType.get(type)?.statut_kyc !== "valide");

  const handleTransition = () => {
    if (!cible) return;
    transitionMutation.mutate(
      { id: dossierId, nouveau_statut: cible, commentaire: commentaire || undefined },
      {
        onSuccess: () => {
          toast.success("Dossier mis à jour.");
          setCible(null);
          setCommentaire("");
        },
      }
    );
  };

  if (transitionsPossibles.length === 0) {
    return <p className="text-xs text-muted-foreground">Aucune action disponible.</p>;
  }

  return (
    <>
      <div className="flex flex-wrap justify-end gap-2">
        {transitionsPossibles.map((statutCible) => (
          <Button key={statutCible} variant="outline" size="sm" onClick={() => setCible(statutCible)}>
            {LABELS_STATUT_DOSSIER[statutCible]}
          </Button>
        ))}
      </div>

      <Dialog open={cible !== null} onOpenChange={(open) => !open && setCible(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Passer le dossier à « {cible ? LABELS_STATUT_DOSSIER[cible] : ""} »</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            {cible === "docs_recus" && documentsManquants.length > 0 && (
              <p className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                ⚠️ {documentsManquants.length} document(s) pas encore validé(s) : {documentsManquants.map(labelTypeDocument).join(", ")}{" "}
                (voir la section Documents) — confirmer quand même que les documents ont été reçus et vérifiés ?
              </p>
            )}
            <div className="space-y-2">
              <Label>Commentaire (optionnel)</Label>
              <Input value={commentaire} onChange={(e) => setCommentaire(e.target.value)} />
            </div>
            <div className="flex justify-end">
              <Button onClick={handleTransition} disabled={transitionMutation.isPending}>
                {transitionMutation.isPending ? "Enregistrement…" : "Confirmer"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

function DocumentsSection({
  dossierId,
  clientId,
  documentsRequis,
}: {
  dossierId: number;
  clientId: number;
  documentsRequis: string[];
}) {
  const documentsQuery = useClientDocuments(clientId);
  const [lienOpen, setLienOpen] = useState(false);
  const [lienUrl, setLienUrl] = useState<string | null>(null);
  const genererLienMutation = useGenererLienClientDossier();
  const envoyerLienMutation = useEnvoyerLienClientDossier();
  const supprimerMutation = useSupprimerDocumentClient(clientId);
  const validerMutation = useValiderDocumentClient(clientId);
  const [rejetCible, setRejetCible] = useState<{ id: number; label: string } | null>(null);
  const [motifRejet, setMotifRejet] = useState("");

  const handleSupprimer = (documentId: number, label: string) => {
    if (!window.confirm(`Supprimer le document "${label}" ? Le client devra le retransmettre.`)) return;
    supprimerMutation.mutate(documentId, { onSuccess: () => toast.success("Document supprimé.") });
  };

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

  const documentsParType = new Map((documentsQuery.data ?? []).map((d) => [d.type_document, d]));
  const manquants = documentsRequis.filter((type) => !documentsParType.has(type));

  const handleCopierLien = () => {
    genererLienMutation.mutate(dossierId, {
      onSuccess: (data) => {
        setLienUrl(data.url);
        setLienOpen(true);
      },
      onError: () => toast.error("Échec de la génération du lien."),
    });
  };

  const handleEnvoyerLien = (canal: "sms" | "email") => {
    envoyerLienMutation.mutate(
      { dossierId, canal },
      {
        onSuccess: (data) => {
          const ok = canal === "email" ? data.email_envoye : data.sms_envoye;
          toast[ok ? "success" : "error"](
            ok ? `Lien envoyé par ${canal === "email" ? "email" : "SMS"}.` : `Échec de l'envoi par ${canal === "email" ? "email" : "SMS"}.`
          );
        },
        onError: () => toast.error("Échec de l'envoi du lien."),
      }
    );
  };

  const handleCopierDansLePresseTexte = async () => {
    if (!lienUrl) return;
    await navigator.clipboard.writeText(lienUrl);
    toast.success("Lien copié.");
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Documents</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="flex flex-wrap gap-2 pb-2">
          <Button variant="outline" size="sm" onClick={handleCopierLien} disabled={genererLienMutation.isPending}>
            Copier le lien de collecte
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleEnvoyerLien("email")}
            disabled={envoyerLienMutation.isPending}
          >
            Envoyer par email
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleEnvoyerLien("sms")}
            disabled={envoyerLienMutation.isPending}
          >
            Envoyer par SMS
          </Button>
        </div>
        {documentsQuery.isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : (
          <>
            {manquants.length > 0 && (
              <ul className="divide-y">
                {manquants.map((type) => (
                  <li key={type} className="flex items-center justify-between py-2 text-sm">
                    <p className="font-medium text-muted-foreground">{labelTypeDocument(type)}</p>
                    <Badge variant="secondary">à fournir</Badge>
                  </li>
                ))}
              </ul>
            )}
            {!documentsQuery.data?.length && manquants.length === 0 && (
              <p className="text-sm text-muted-foreground">Aucun document transmis.</p>
            )}
            {!!documentsQuery.data?.length && (
              <ul className="divide-y">
                {documentsQuery.data.map((doc) => (
                  <li key={doc.id} className="flex items-center justify-between py-2 text-sm">
                    <div className="space-y-0.5">
                      <p className="font-medium">{doc.type_document ? labelTypeDocument(doc.type_document) : "Document"}</p>
                      <p className="text-muted-foreground">{doc.date_upload}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={doc.statut_kyc === "valide" ? "default" : "secondary"}>{doc.statut_kyc}</Badge>
                      {doc.url ? (
                        <Button variant="outline" size="sm" asChild>
                          <a href={doc.url} target="_blank" rel="noreferrer">
                            Voir
                          </a>
                        </Button>
                      ) : (
                        <Button variant="outline" size="sm" disabled title="Fichier indisponible sur le stockage">
                          Fichier indisponible
                        </Button>
                      )}
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
                        onClick={() =>
                          setRejetCible({
                            id: doc.id,
                            label: doc.type_document ? labelTypeDocument(doc.type_document) : "Document",
                          })
                        }
                      >
                        Rejeter
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        className="text-destructive"
                        disabled={supprimerMutation.isPending}
                        onClick={() =>
                          handleSupprimer(doc.id, doc.type_document ? labelTypeDocument(doc.type_document) : "Document")
                        }
                      >
                        Supprimer
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </>
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

      <Dialog open={lienOpen} onOpenChange={setLienOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Lien de collecte de documents</DialogTitle>
          </DialogHeader>
          <div className="flex gap-2">
            <Input readOnly value={lienUrl ?? ""} />
            <Button onClick={handleCopierDansLePresseTexte}>Copier</Button>
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

function MandatRepresentationSection({ dossierId }: { dossierId: number }) {
  const [signerOpen, setSignerOpen] = useState(false);
  const [signataire, setSignataire] = useState("");

  const mandatQuery = useMandat(dossierId);
  const envoyerMutation = useEnvoyerMandat();
  const signerMutation = useMarquerMandatSigne();

  const mandat = mandatQuery.data;

  const handleEnvoyer = () => {
    envoyerMutation.mutate(dossierId, {
      onSuccess: () => toast.success("Mandat envoyé en signature (Yousign)."),
    });
  };

  const handleSigner = () => {
    if (!mandat) return;
    signerMutation.mutate(
      { mandatId: mandat.id, signataire, dossierId },
      {
        onSuccess: () => {
          toast.success("Mandat marqué comme signé — conversion et suivi mis à jour.");
          setSignerOpen(false);
        },
      }
    );
  };

  // Raccourci de dev : crée puis signe immédiatement, sans passer par Yousign
  // ni la boîte de dialogue "signataire" — pour valider rapidement la suite
  // (progression du dossier, conversion prospect→client, relance programmée).
  const handleTestCreerEtSigner = () => {
    envoyerMutation.mutate(dossierId, {
      onSuccess: (nouveauMandat) => {
        signerMutation.mutate(
          { mandatId: nouveauMandat.id, signataire: "Test développement", dossierId },
          {
            onSuccess: () => toast.success("Mandat créé et marqué signé (test)."),
          }
        );
      },
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Mandat de représentation</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {mandatQuery.isLoading ? (
          <Skeleton className="h-16 w-full" />
        ) : (
          <>
            {!mandat ? (
              <p className="text-sm text-muted-foreground">Aucun mandat de représentation envoyé pour ce dossier.</p>
            ) : (
              <div className="flex items-center justify-between text-sm">
                <Badge variant={mandat.statut === "signe" ? "default" : "secondary"}>{mandat.statut}</Badge>
                {mandat.statut === "signe" && mandat.date_signature && (
                  <span className="text-muted-foreground">Signé le {mandat.date_signature}</span>
                )}
              </div>
            )}
            {mandat?.pdf_url && (
              <Button variant="outline" size="sm" asChild>
                <a href={mandat.pdf_url} target="_blank" rel="noreferrer">
                  Voir le PDF généré
                </a>
              </Button>
            )}
            {mandat?.statut === "erreur" && mandat.notes && (
              <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">
                {mandat.notes} — utilisez « Marquer signé manuellement » en attendant.
              </p>
            )}
            {mandat?.statut !== "signe" && (
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" onClick={handleEnvoyer} disabled={envoyerMutation.isPending}>
                  {envoyerMutation.isPending ? "Envoi…" : mandat ? "Renvoyer pour signature (Yousign)" : "Envoyer pour signature (Yousign)"}
                </Button>
                {mandat && (
                  <Button variant="outline" onClick={() => setSignerOpen(true)}>
                    Marquer signé manuellement
                  </Button>
                )}
                {!mandat && (
                  <Button
                    variant="outline"
                    onClick={handleTestCreerEtSigner}
                    disabled={envoyerMutation.isPending || signerMutation.isPending}
                  >
                    Créer + marquer signé (test)
                  </Button>
                )}
              </div>
            )}
          </>
        )}
      </CardContent>

      <Dialog open={signerOpen} onOpenChange={setSignerOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Marquer le mandat comme signé</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              À utiliser tant que la signature électronique Yousign n&apos;est pas configurée, ou pour une signature
              obtenue hors-ligne. Déclenche la même suite qu&apos;une signature Yousign : progression du dossier,
              conversion en client si nécessaire, et programmation d&apos;une relance de suivi.
            </p>
            <div className="space-y-2">
              <Label>Signataire</Label>
              <Input value={signataire} onChange={(e) => setSignataire(e.target.value)} />
            </div>
            <div className="flex justify-end">
              <Button onClick={handleSigner} disabled={signerMutation.isPending || !signataire}>
                {signerMutation.isPending ? "Enregistrement…" : "Confirmer"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

function MandatHonorairesSection({ dossierId }: { dossierId: number }) {
  const [creerOpen, setCreerOpen] = useState(false);
  const [montant, setMontant] = useState("0");
  const [taux, setTaux] = useState("20");
  const [tauxModifieManuellement, setTauxModifieManuellement] = useState(false);
  const [signerOpen, setSignerOpen] = useState(false);
  const [signataire, setSignataire] = useState("");

  const mandatQuery = useMandatHonoraires(dossierId);
  const tauxDefautQuery = useTauxHonorairesDefaut();
  const creerMutation = useCreerMandatHonoraires();
  const signerMutation = useMarquerSigneHonoraires();
  const telechargerMutation = useTelechargerMandatHonoraires();
  const envoyerMutation = useEnvoyerMandatHonoraires();

  // Pré-remplit avec le taux par défaut réglé par l'admin (panneau Admin >
  // Paramètres) dès qu'il est chargé — sauf si le conseiller a déjà modifié
  // le champ à la main, pour ne pas écraser sa saisie.
  useEffect(() => {
    if (!tauxModifieManuellement && tauxDefautQuery.data) {
      setTaux(String(tauxDefautQuery.data.taux));
    }
  }, [tauxDefautQuery.data, tauxModifieManuellement]);

  const handleTelecharger = () => {
    telechargerMutation.mutate(dossierId, {
      onError: () => toast.error("Échec du téléchargement du mandat."),
    });
  };

  const handleEnvoyer = (canal: "email" | "sms") => {
    envoyerMutation.mutate(
      { dossierId, canal },
      {
        onSuccess: (data) => {
          const ok = canal === "email" ? data.email_envoye : data.sms_envoye;
          toast[ok ? "success" : "error"](
            ok ? `Mandat envoyé par ${canal === "email" ? "email" : "SMS"}.` : `Échec de l'envoi par ${canal === "email" ? "email" : "SMS"}.`
          );
        },
      }
    );
  };

  const handleCreer = () => {
    creerMutation.mutate(
      { dossierId, montant: Number(montant), taux: Number(taux) },
      {
        onSuccess: () => {
          toast.success("Mandat d'honoraires envoyé.");
          setCreerOpen(false);
        },
      }
    );
  };

  const handleSigner = () => {
    signerMutation.mutate(
      { dossierId, signataire },
      {
        onSuccess: () => {
          toast.success("Mandat marqué comme signé.");
          setSignerOpen(false);
        },
      }
    );
  };

  // Raccourci de dev : crée puis signe immédiatement, sans passer par la
  // boîte de dialogue "signataire" — pour valider rapidement la suite.
  const handleTestCreerEtSigner = () => {
    creerMutation.mutate(
      { dossierId, montant: Number(montant), taux: Number(taux) },
      {
        onSuccess: () => {
          signerMutation.mutate(
            { dossierId, signataire: "Test développement" },
            { onSuccess: () => toast.success("Mandat créé et marqué signé (test).") }
          );
        },
      }
    );
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Mandat honoraires</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {mandatQuery.isLoading ? (
          <Skeleton className="h-16 w-full" />
        ) : !mandatQuery.data ? (
          <>
            <p className="text-sm text-muted-foreground">Aucun mandat d&apos;honoraires pour ce dossier.</p>
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => setCreerOpen(true)}>Envoyer pour signature</Button>
              <Button
                variant="outline"
                onClick={handleTestCreerEtSigner}
                disabled={creerMutation.isPending || signerMutation.isPending}
              >
                Créer + marquer signé (test)
              </Button>
            </div>
          </>
        ) : (
          <>
            <div className="flex items-center justify-between text-sm">
              <span>
                {mandatQuery.data.montant} € — {mandatQuery.data.taux} %
              </span>
              <Badge variant={mandatQuery.data.statut === "signe" ? "default" : "secondary"}>
                {mandatQuery.data.statut}
              </Badge>
            </div>
            {mandatQuery.data.date_creation && (
              <p className="text-xs text-muted-foreground">Créé le {mandatQuery.data.date_creation}</p>
            )}
            {mandatQuery.data.statut === "signe" ? (
              <p className="text-sm text-muted-foreground">
                Signé par {mandatQuery.data.signataire} le {mandatQuery.data.date_signature}
              </p>
            ) : (
              <Button onClick={() => setSignerOpen(true)}>Marquer signé</Button>
            )}
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={handleTelecharger} disabled={telechargerMutation.isPending}>
                {telechargerMutation.isPending ? "Téléchargement…" : "Télécharger PDF"}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleEnvoyer("email")}
                disabled={envoyerMutation.isPending}
              >
                Envoyer par email
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleEnvoyer("sms")}
                disabled={envoyerMutation.isPending}
              >
                Envoyer par SMS
              </Button>
            </div>
          </>
        )}
      </CardContent>

      <Dialog open={creerOpen} onOpenChange={setCreerOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Envoyer le mandat d&apos;honoraires</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Montant (€)</Label>
                <Input type="number" value={montant} onChange={(e) => setMontant(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Taux (%)</Label>
                <Input
                  type="number"
                  value={taux}
                  onChange={(e) => {
                    setTaux(e.target.value);
                    setTauxModifieManuellement(true);
                  }}
                />
              </div>
            </div>
            <div className="flex justify-end">
              <Button onClick={handleCreer} disabled={creerMutation.isPending}>
                {creerMutation.isPending ? "Envoi…" : "Envoyer"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={signerOpen} onOpenChange={setSignerOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Marquer le mandat comme signé</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Signataire</Label>
              <Input value={signataire} onChange={(e) => setSignataire(e.target.value)} />
            </div>
            <div className="flex justify-end">
              <Button onClick={handleSigner} disabled={signerMutation.isPending || !signataire}>
                {signerMutation.isPending ? "Enregistrement…" : "Confirmer"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

function DemarchesSection({ dossierId }: { dossierId: number }) {
  const demarchesQuery = useDemarchesDossier(dossierId);
  const creerMutation = useCreerDemarche();
  const genererMutation = useGenererDemarche();
  const envoyerMutation = useEnvoyerDemarche();

  const handleCreer = (type_demarche: string) => {
    creerMutation.mutate({ dossierId, type_demarche }, { onSuccess: () => toast.success("Démarche créée.") });
  };

  const handleGenerer = (demarche: Demarche) => {
    genererMutation.mutate(
      { demarcheId: demarche.id, dossierId },
      {
        onSuccess: () => toast.success("Génération du document lancée."),
        onError: (err) => toast.error(err instanceof Error ? err.message : "Échec de la génération."),
      }
    );
  };

  const handleEnvoyer = (demarche: Demarche) => {
    envoyerMutation.mutate(
      { demarcheId: demarche.id, dossierId },
      {
        onSuccess: () => toast.success("Envoi LRE lancé."),
        onError: (err) => toast.error(err instanceof Error ? err.message : "Échec de l'envoi."),
      }
    );
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Démarches</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground">
          <strong>Créer</strong> initialise une démarche à préparer (ex. portabilité mobile) et ouvre sa fiche pour
          renseigner les informations nécessaires. <strong>Générer</strong> produit ensuite le document officiel — cela
          nécessite que le mandat de représentation du client soit signé (voir ci-contre).
        </p>
        {demarchesQuery.isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : (
          <>
            {(demarchesQuery.data?.existantes ?? []).map((demarche) => (
              <div key={demarche.id} className="flex items-center justify-between text-sm">
                <div>
                  <p className="font-medium">{demarche.type_demarche}</p>
                  <Badge variant="secondary">{demarche.statut}</Badge>
                </div>
                <div className="flex gap-2">
                  {demarche.statut === "a_generer" && (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={genererMutation.isPending}
                      onClick={() => handleGenerer(demarche)}
                    >
                      Générer
                    </Button>
                  )}
                  {demarche.statut === "generee" && (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={envoyerMutation.isPending}
                      onClick={() => handleEnvoyer(demarche)}
                    >
                      Envoyer
                    </Button>
                  )}
                </div>
              </div>
            ))}
            {(demarchesQuery.data?.requises_non_creees ?? []).map((requise) => (
              <div key={requise.type_demarche} className="flex items-center justify-between text-sm">
                <p className="text-muted-foreground">{requise.label} (non créée)</p>
                <Button size="sm" variant="outline" onClick={() => handleCreer(requise.type_demarche)}>
                  Créer
                </Button>
              </div>
            ))}
            {!demarchesQuery.data?.existantes.length && !demarchesQuery.data?.requises_non_creees.length && (
              <p className="text-sm text-muted-foreground">Aucune démarche pour ce dossier.</p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function NotesSection({
  dossierId,
  notesWorkflow,
}: {
  dossierId: number;
  notesWorkflow: import("@/lib/types").NoteWorkflowEntry[] | null;
}) {
  const [texte, setTexte] = useState("");
  const noteMutation = useAjouterNoteDossier();

  const handleAjouter = () => {
    if (!texte.trim()) return;
    noteMutation.mutate(
      { id: dossierId, texte },
      {
        onSuccess: () => {
          toast.success("Note ajoutée.");
          setTexte("");
        },
      }
    );
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Notes internes</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex gap-2">
          <Input
            placeholder="Ajouter une note…"
            value={texte}
            onChange={(e) => setTexte(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAjouter()}
          />
          <Button onClick={handleAjouter} disabled={noteMutation.isPending || !texte.trim()}>
            Ajouter
          </Button>
        </div>
        {!notesWorkflow?.length ? (
          <p className="text-sm text-muted-foreground">Aucune entrée dans le journal.</p>
        ) : (
          <ul className="divide-y">
            {[...notesWorkflow].reverse().map((entry, index) => (
              <li key={index} className="py-2 text-sm">
                <div className="flex justify-between">
                  <span className="font-medium">
                    {entry.type === "transition" ? `${entry.de} → ${entry.vers}` : "Note"}
                  </span>
                  <span className="text-muted-foreground">{entry.date}</span>
                </div>
                {(entry.commentaire || entry.texte) && (
                  <p className="text-muted-foreground">{entry.commentaire || entry.texte}</p>
                )}
                <p className="text-xs text-muted-foreground">Par {entry.par}</p>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
