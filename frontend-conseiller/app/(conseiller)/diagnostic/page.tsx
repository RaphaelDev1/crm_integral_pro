"use client";

import { useState } from "react";
import { toast } from "sonner";

import { EtapeIdentite } from "@/components/diagnostic/EtapeIdentite";
import { EtapeRecommandations } from "@/components/diagnostic/EtapeRecommandations";
import { EtapeSituation } from "@/components/diagnostic/EtapeSituation";
import { EtapeUnivers } from "@/components/diagnostic/EtapeUnivers";
import { Wizard } from "@/components/wizard/Wizard";
import { ApiError } from "@/lib/api";
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
  }).success;
}

function situationComplete(state: DiagnosticState) {
  if (state.univers.includes("Télécom")) {
    const t = state.telecom;
    if (!t.operateurActuel || !t.satisfactionReseau || t.coutMensuelActuel <= 0) return false;
  }
  return true;
}

// Page /diagnostic (plan de migration Phase 6) — assemble le wizard 4 étapes
// autour de useDiagnosticWizard (état + autosave) et du composant <Wizard>.
export default function DiagnosticPage() {
  const { state, dispatch, clearDraft } = useDiagnosticWizard();
  const creerProspect = prospectsResource.useCreate();
  const [creationEnCours, setCreationEnCours] = useState(false);

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
          univers_interesse: state.univers.join(", "),
          service_principal: state.univers.includes("Télécom") ? state.servicePrincipal : undefined,
          origine: "Diagnostic conseiller",
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
      <div>
        <h1 className="text-xl font-bold text-primary">Nouveau diagnostic</h1>
        <p className="text-sm text-slate-500">
          Univers → identité → situation actuelle → recommandations. Le brouillon est sauvegardé automatiquement.
        </p>
      </div>

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
