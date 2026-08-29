"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import type { EtapeIdentiteValues } from "@/lib/schemas/diagnostic";
import type { OffreComparee } from "@/lib/types";

// Machine d'état du wizard Diagnostic (plan de migration, Phase 6.1). Un seul
// useReducer + persistance localStorage périodique — pas de dépendance
// externe (Zustand) : le state reste local à la page /diagnostic, inutile
// ailleurs dans l'app.

export interface IdentiteState extends EtapeIdentiteValues {
  mode: "nouveau" | "existant";
  entiteType: "prospect" | "client" | null;
  entiteId: number | null;
}

export interface AbonnementDraft {
  id: string;
  nom: string;
  categorie: string;
  cout: number;
}

// Sessions de trame IA Conseil lancées pour ce diagnostic — une par catégorie
// requise (mobile/box/energie_elec/energie_gaz), voir EtapeTrame.tsx pour le
// calcul des catégories requises à partir de univers/servicePrincipal.
export interface TrameState {
  clientConseilId: string | null;
  sessions: Record<string, string>;
}

export interface PanierItem {
  id: string;
  univers: string;
  categorie: string;
  coutActuelMensuel: number;
  offre: OffreComparee;
  // Faux uniquement pour une offre "cross-sell" (ex. Box proposée alors que le
  // client a un forfait Mobile) : son économie n'est pas comparable au coût
  // actuel du client (autre type de service) et ne doit ni s'afficher ni
  // entrer dans le calcul de l'économie totale — voir EtapeRecommandations.tsx.
  comparable?: boolean;
}

export interface DiagnosticState {
  etape: number;
  univers: string[];
  servicePrincipal: string;
  identite: IdentiteState;
  trame: TrameState;
  abonnements: AbonnementDraft[];
  panier: PanierItem[];
}

export const ETAPES_DIAGNOSTIC = [
  { id: "univers", titre: "Univers" },
  { id: "identite", titre: "Identité" },
  { id: "trame", titre: "Situation & recommandations" },
] as const;

const ETAT_INITIAL: DiagnosticState = {
  etape: 1,
  univers: [],
  servicePrincipal: "Mobile uniquement",
  identite: {
    mode: "nouveau",
    entiteType: null,
    entiteId: null,
    typeClient: "Particulier",
    prenom: "",
    nom: "",
    telephone: "",
    email: "",
    codePostal: "",
    ville: "",
    adresse: "",
    raisonSociale: "",
    effectif: "",
  },
  trame: { clientConseilId: null, sessions: {} },
  abonnements: [],
  panier: [],
};

type Action =
  | { type: "GO_TO_STEP"; step: number }
  | { type: "SET_UNIVERS"; univers: string[] }
  | { type: "SET_SERVICE_PRINCIPAL"; value: string }
  | { type: "SET_IDENTITE"; values: Partial<IdentiteState> }
  | { type: "SET_CLIENT_CONSEIL_ID"; id: string }
  | { type: "SET_SESSION_ID"; categorieSlug: string; sessionId: string }
  | { type: "ADD_ABONNEMENT"; item: AbonnementDraft }
  | { type: "REMOVE_ABONNEMENT"; id: string }
  | { type: "ADD_PANIER"; item: PanierItem }
  | { type: "REMOVE_PANIER"; id: string }
  | { type: "HYDRATE"; state: DiagnosticState }
  | { type: "RESET" };

function reducer(state: DiagnosticState, action: Action): DiagnosticState {
  switch (action.type) {
    case "GO_TO_STEP":
      return { ...state, etape: action.step };
    case "SET_UNIVERS":
      return { ...state, univers: action.univers };
    case "SET_SERVICE_PRINCIPAL":
      return { ...state, servicePrincipal: action.value };
    case "SET_IDENTITE":
      return { ...state, identite: { ...state.identite, ...action.values } };
    case "SET_CLIENT_CONSEIL_ID":
      return { ...state, trame: { ...state.trame, clientConseilId: action.id } };
    case "SET_SESSION_ID":
      return { ...state, trame: { ...state.trame, sessions: { ...state.trame.sessions, [action.categorieSlug]: action.sessionId } } };
    case "ADD_ABONNEMENT":
      return { ...state, abonnements: [...state.abonnements, action.item] };
    case "REMOVE_ABONNEMENT":
      return { ...state, abonnements: state.abonnements.filter((a) => a.id !== action.id) };
    case "ADD_PANIER":
      return { ...state, panier: [...state.panier.filter((p) => p.id !== action.item.id), action.item] };
    case "REMOVE_PANIER":
      return { ...state, panier: state.panier.filter((p) => p.id !== action.id) };
    case "HYDRATE":
      return action.state;
    case "RESET":
      return ETAT_INITIAL;
    default:
      return state;
  }
}

const STORAGE_KEY = "diagnostic_wizard_draft_v1";
const AUTOSAVE_INTERVAL_MS = 5000;

export function useDiagnosticWizard() {
  const [state, dispatch] = useReducer(reducer, ETAT_INITIAL);
  const hydrated = useRef(false);
  const lastSaved = useRef<string>("");
  const draftEnAttenteRef = useRef<DiagnosticState | null>(null);
  const [draftDisponible, setDraftDisponible] = useState(false);

  // Un brouillon existant au montage n'est plus repris automatiquement (le
  // conseiller pourrait démarrer un diagnostic pour quelqu'un d'autre sans
  // s'en rendre compte) : on signale juste sa présence via `draftDisponible`,
  // à charge de la page d'afficher une boîte de dialogue "reprendre / recommencer".
  useEffect(() => {
    if (hydrated.current) return;
    hydrated.current = true;
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {
        draftEnAttenteRef.current = JSON.parse(raw) as DiagnosticState;
        lastSaved.current = raw;
        setDraftDisponible(true);
      }
    } catch {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  // Sauvegarde toutes les 5 sec, seulement si l'état a changé depuis la
  // dernière écriture.
  useEffect(() => {
    const interval = window.setInterval(() => {
      const serialized = JSON.stringify(state);
      if (serialized !== lastSaved.current) {
        window.localStorage.setItem(STORAGE_KEY, serialized);
        lastSaved.current = serialized;
      }
    }, AUTOSAVE_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [state]);

  const clearDraft = useCallback(() => {
    window.localStorage.removeItem(STORAGE_KEY);
    lastSaved.current = "";
    draftEnAttenteRef.current = null;
    setDraftDisponible(false);
    dispatch({ type: "RESET" });
  }, []);

  const reprendreDraft = useCallback(() => {
    if (draftEnAttenteRef.current) {
      dispatch({ type: "HYDRATE", state: draftEnAttenteRef.current });
    }
    draftEnAttenteRef.current = null;
    setDraftDisponible(false);
  }, []);

  return { state, dispatch, clearDraft, draftDisponible, reprendreDraft };
}

export type DiagnosticDispatch = ReturnType<typeof useDiagnosticWizard>["dispatch"];
