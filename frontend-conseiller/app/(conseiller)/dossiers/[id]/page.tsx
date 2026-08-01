"use client";

import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { CheckCircle2, Circle, Clock } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useClientDocuments } from "@/lib/hooks/useClients";
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
  useTransitionDossier,
} from "@/lib/hooks/useDossiers";
import { useCreerMandatHonoraires, useMandatHonoraires, useMarquerSigneHonoraires } from "@/lib/hooks/useHonoraires";
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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-primary">
            Dossier #{dossier.id} — {dossier.univers}
          </h1>
          <p className="text-sm text-muted-foreground">
            Client : {clientQuery.data ? `${clientQuery.data.prenom ?? ""} ${clientQuery.data.nom ?? ""}` : "…"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className={statutDossierBadgeClass(dossier.statut)}>
            {LABELS_STATUT_DOSSIER[dossier.statut as StatutDossier] ?? dossier.statut}
          </Badge>
          <a href={`/api/backend/dossiers/${dossier.id}/pdf-restitution`} download>
            <Button variant="outline">Télécharger restitution</Button>
          </a>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <TimelineSection dossierId={dossierId} />
          <ActionsTransitionSection dossierId={dossierId} statut={dossier.statut as StatutDossier} />
          <DocumentsSection clientId={dossier.client_id} />
        </div>
        <div className="space-y-6">
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

function ActionsTransitionSection({ dossierId, statut }: { dossierId: number; statut: StatutDossier }) {
  const [cible, setCible] = useState<StatutDossier | null>(null);
  const [commentaire, setCommentaire] = useState("");
  const transitionMutation = useTransitionDossier();

  const transitionsPossibles = TRANSITIONS_AUTORISEES[statut] ?? [];

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
    return (
      <Card>
        <CardHeader>
          <CardTitle>Actions disponibles</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">Aucune transition possible depuis cet état.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Actions disponibles</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-2">
        {transitionsPossibles.map((statutCible) => (
          <Button key={statutCible} variant="outline" onClick={() => setCible(statutCible)}>
            {LABELS_STATUT_DOSSIER[statutCible]}
          </Button>
        ))}
      </CardContent>

      <Dialog open={cible !== null} onOpenChange={(open) => !open && setCible(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Passer le dossier à « {cible ? LABELS_STATUT_DOSSIER[cible] : ""} »</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
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
    </Card>
  );
}

function DocumentsSection({ clientId }: { clientId: number }) {
  const documentsQuery = useClientDocuments(clientId);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Documents</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {documentsQuery.isLoading ? (
          <Skeleton className="h-32 w-full" />
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

function MandatHonorairesSection({ dossierId }: { dossierId: number }) {
  const [creerOpen, setCreerOpen] = useState(false);
  const [montant, setMontant] = useState("0");
  const [taux, setTaux] = useState("0");
  const [signerOpen, setSignerOpen] = useState(false);
  const [signataire, setSignataire] = useState("");

  const mandatQuery = useMandatHonoraires(dossierId);
  const creerMutation = useCreerMandatHonoraires();
  const signerMutation = useMarquerSigneHonoraires();

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
            <Button onClick={() => setCreerOpen(true)}>Envoyer pour signature</Button>
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
            {mandatQuery.data.statut === "signe" ? (
              <p className="text-sm text-muted-foreground">
                Signé par {mandatQuery.data.signataire} le {mandatQuery.data.date_signature}
              </p>
            ) : (
              <Button onClick={() => setSignerOpen(true)}>Marquer signé</Button>
            )}
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
                <Input type="number" value={taux} onChange={(e) => setTaux(e.target.value)} />
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
      { onSuccess: () => toast.success("Génération du document lancée.") }
    );
  };

  const handleEnvoyer = (demarche: Demarche) => {
    envoyerMutation.mutate(
      { demarcheId: demarche.id, dossierId },
      { onSuccess: () => toast.success("Envoi LRE lancé.") }
    );
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Démarches</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
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
                    <Button size="sm" variant="outline" onClick={() => handleGenerer(demarche)}>
                      Générer
                    </Button>
                  )}
                  {demarche.statut === "generee" && (
                    <Button size="sm" variant="outline" onClick={() => handleEnvoyer(demarche)}>
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
