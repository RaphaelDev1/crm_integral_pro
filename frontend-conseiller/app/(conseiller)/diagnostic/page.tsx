"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { EtapeIdentite, valeursIdentiteDepuisEntite } from "@/components/diagnostic/EtapeIdentite";
import { EtapeRecommandations } from "@/components/diagnostic/EtapeRecommandations";
import { EtapeSituation } from "@/components/diagnostic/EtapeSituation";
import { EtapeUnivers } from "@/components/diagnostic/EtapeUnivers";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Wizard } from "@/components/wizard/Wizard";
import { ApiError } from "@/lib/api";
import { clientsResource } from "@/lib/hooks/useClients";
import { ETAPES_DIAGNOSTIC, useDiagnosticWizard, type DiagnosticState } from "@/lib/hooks/useDiagnosticWizard";
import { prospectsResource } from "@/lib/hooks/useProspects";
import { etapeIdentiteSchema, etapeUniversSchema } from "@/lib/schemas/diagnostic";

function universComplet(state: DiagnosticState) {
  return etapeUniversSchema.safeParse({ univers: state.univers, servicePrincipal: state.servicePrincipal }).success;
}

function identiteComplete(state: DiagnosticState) {
  return etapeIdentiteSchema.safeParse({
    typeClient: state.identite.typeClient,
    prenom: state.identite.prenom,
    nom: state.identite.nom,
    telephone: state.identite.telephone,
    email: state.identite.email,
    codePostal: state.identite.codePostal,
    ville: state.identite.ville,
    adresse: state.identite.adresse,
    raisonSociale: state.identite.raisonSociale,
    effectif: state.identite.effectif,
  }).success;
}

function situationComplete(state: DiagnosticState) {
  if (state.univers.includes("Télécom")) {
    const t = state.telecom;
    if (!t.operateurActuel || !t.satisfactionReseau || !t.defautTechnique || !t.veutRester || t.coutMensuelActuel <= 0)
      return false;
  }
  return true;
}

// Page /diagnostic (plan de migration Phase 6) — assemble le wizard 4 étapes
// autour de useDiagnosticWizard (état + autosave) et du composant <Wizard>.
// useSearchParams() exige une frontière Suspense en rendu statique (voir
// app/login/page.tsx) — utilisé ici pour le pré-remplissage depuis les
// boutons "Nouveau diagnostic" des fiches prospect/client.
export default function DiagnosticPage() {
  return (
    <Suspense>
      <DiagnosticWizardPage />
    </Suspense>
  );
}

function DiagnosticWizardPage() {
  const { state, dispatch, clearDraft, draftDisponible, reprendreDraft } = useDiagnosticWizard();
  const creerProspect = prospectsResource.useCreate();
  const [creationEnCours, setCreationEnCours] = useState(false);

  // Pré-remplissage depuis "Nouveau diagnostic" (fiche prospect/client,
  // ?entiteType=prospect|client&entiteId=123) — l'intention est explicite,
  // donc on ignore un éventuel brouillon en cours plutôt que de proposer de
  // le reprendre.
  const searchParams = useSearchParams();
  const entiteTypeParam = searchParams.get("entiteType");
  const prefillType = entiteTypeParam === "prospect" || entiteTypeParam === "client" ? entiteTypeParam : null;
  const prefillId = prefillType ? Number(searchParams.get("entiteId")) : null;

  const prospectPrefillQuery = prospectsResource.useOne(
    prefillType === "prospect" && prefillId ? prefillId : undefined
  );
  const clientPrefillQuery = clientsResource.useOne(prefillType === "client" && prefillId ? prefillId : undefined);

  const prefillApplique = useRef(false);
  useEffect(() => {
    if (!prefillType || !prefillId || prefillApplique.current) return;
    const entite = prefillType === "prospect" ? prospectPrefillQuery.data : clientPrefillQuery.data;
    if (!entite) return;
    prefillApplique.current = true;
    clearDraft();
    dispatch({ type: "SET_IDENTITE", values: valeursIdentiteDepuisEntite(prefillType, entite) });
    toast.success(`Diagnostic pré-rempli pour ${entite.prenom ?? ""} ${entite.nom ?? ""}`.trim());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefillType, prefillId, prospectPrefillQuery.data, clientPrefillQuery.data]);

  // Reprise après fermeture inopinée du logiciel (Phase 6.1) : on ne propose
  // de reprendre que si aucun pré-remplissage explicite n'est en cours.
  const [dialogueReprise, setDialogueReprise] = useState(false);
  useEffect(() => {
    if (prefillType) return;
    if (draftDisponible) setDialogueReprise(true);
  }, [draftDisponible, prefillType]);

  function handleReprendre() {
    reprendreDraft();
    setDialogueReprise(false);
  }

  function handleRecommencerDepuisReprise() {
    clearDraft();
    setDialogueReprise(false);
  }

  function handleReinitialiser() {
    if (!window.confirm("Réinitialiser le diagnostic en cours ? Les informations saisies seront perdues.")) return;
    clearDraft();
    toast.success("Diagnostic réinitialisé.");
  }

  const currentIndex = state.etape - 1;

  const canGoNext =
    currentIndex === 0 ? universComplet(state) : currentIndex === 1 ? identiteComplete(state) : currentIndex === 2 ? situationComplete(state) : true;

  async function handleNext() {
    if (!canGoNext) return;

    // À la sortie de l'étape Identité : si c'est une nouvelle fiche, on crée
    // le prospect tout de suite (POST /prospects, plan Phase 6.4) pour que
    // l'étape 4 dispose toujours d'un entiteId/entiteType résolu.
    if (currentIndex === 1 && state.identite.mode === "nouveau") {
      setCreationEnCours(true);
      try {
        const prospect = await creerProspect.mutateAsync({
          prenom: state.identite.prenom,
          nom: state.identite.nom,
          telephone: state.identite.telephone || undefined,
          email: state.identite.email || undefined,
          code_postal: state.identite.codePostal || undefined,
          ville: state.identite.ville || undefined,
          adresse: state.identite.adresse || undefined,
          type_client: state.identite.typeClient,
          raison_sociale: state.identite.raisonSociale || undefined,
          effectif: state.identite.effectif || undefined,
          univers_interesse: state.univers.join(", "),
          service_principal: state.univers.includes("Télécom") ? state.servicePrincipal : undefined,
          origine: "Diagnostic conseiller",
          // On vient techniquement d'échanger avec ce prospect (diagnostic en
          // cours) — programme une relance à J+7 d'office plutôt que de le
          // laisser sans échéance de suivi.
          date_relance: new Date(Date.now() + 7 * 86_400_000).toISOString().slice(0, 10),
        });
        dispatch({
          type: "SET_IDENTITE",
          values: { mode: "existant", entiteType: "prospect", entiteId: prospect.id },
        });
      } catch (error) {
        toast.error(error instanceof ApiError ? error.detail : "Échec de la création du prospect.");
        return;
      } finally {
        setCreationEnCours(false);
      }
    }

    dispatch({ type: "GO_TO_STEP", step: Math.min(state.etape + 1, ETAPES_DIAGNOSTIC.length) });
  }

  function handlePrev() {
    dispatch({ type: "GO_TO_STEP", step: Math.max(state.etape - 1, 1) });
  }

  function handleGoToStep(index: number) {
    dispatch({ type: "GO_TO_STEP", step: index + 1 });
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-primary">Nouveau diagnostic</h1>
          <p className="text-sm text-slate-500">
            Univers → identité → situation actuelle → recommandations. Le brouillon est sauvegardé automatiquement.
          </p>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={handleReinitialiser}>
          Réinitialiser le diagnostic
        </Button>
      </div>

      <Dialog open={dialogueReprise} onOpenChange={setDialogueReprise}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Diagnostic en cours retrouvé</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Le logiciel a été fermé pendant un diagnostic en cours. Voulez-vous le reprendre ?
          </p>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={handleRecommencerDepuisReprise}>
              Recommencer
            </Button>
            <Button type="button" onClick={handleReprendre}>
              Reprendre
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Wizard
        steps={ETAPES_DIAGNOSTIC}
        currentIndex={currentIndex}
        onNext={handleNext}
        onPrev={handlePrev}
        onGoToStep={handleGoToStep}
        canGoNext={canGoNext}
        isSubmitting={creationEnCours}
        isLastStep={currentIndex === ETAPES_DIAGNOSTIC.length - 1}
        hideNext={currentIndex === ETAPES_DIAGNOSTIC.length - 1}
      >
        {currentIndex === 0 && <EtapeUnivers state={state} dispatch={dispatch} />}
        {currentIndex === 1 && <EtapeIdentite state={state} dispatch={dispatch} />}
        {currentIndex === 2 && <EtapeSituation state={state} dispatch={dispatch} />}
        {currentIndex === 3 && <EtapeRecommandations state={state} dispatch={dispatch} onTermine={clearDraft} />}
      </Wizard>
    </div>
  );
}
