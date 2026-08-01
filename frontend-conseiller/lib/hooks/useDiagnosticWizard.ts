"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";

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

export interface SituationTelecomState {
  operateurActuel: string;
  techno: string;
  offreActuelle: string;
  coutMensuelActuel: number;
  dataGoMin: string;
  debitSouhaite: string;
  satisfactionReseau: string;
  veutRester: boolean;
  speedDown: number;
  speedUp: number;
}

export interface SituationEnergieState {
  fournisseurEnergie: string;
  coutElec: number;
  coutGaz: number;
}

export interface PanierItem {
  id: string;
  univers: string;
  categorie: string;
  coutActuelMensuel: number;
  offre: OffreComparee;
}

export interface DiagnosticState {
  etape: number;
  univers: string[];
  servicePrincipal: string;
  identite: IdentiteState;
  telecom: SituationTelecomState;
  energie: SituationEnergieState;
  abonnements: AbonnementDraft[];
  panier: PanierItem[];
}

export const ETAPES_DIAGNOSTIC = [
  { id: "univers", titre: "Univers" },
  { id: "identite", titre: "Identité" },
  { id: "situation", titre: "Situation actuelle" },
  { id: "recommandations", titre: "Recommandations" },
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
  },
  telecom: {
    operateurActuel: "",
    techno: "FIBRE",
    offreActuelle: "",
    coutMensuelActuel: 0,
    dataGoMin: "",
    debitSouhaite: "",
    satisfactionReseau: "",
    veutRester: false,
    speedDown: 0,
    speedUp: 0,
  },
  energie: { fournisseurEnergie: "Autre / Aucun", coutElec: 0, coutGaz: 0 },
  abonnements: [],
  panier: [],
};

type Action =
  | { type: "GO_TO_STEP"; step: number }
  | { type: "SET_UNIVERS"; univers: string[] }
  | { type: "SET_SERVICE_PRINCIPAL"; value: string }
  | { type: "SET_IDENTITE"; values: Partial<IdentiteState> }
  | { type: "SET_TELECOM"; values: Partial<SituationTelecomState> }
  | { type: "SET_ENERGIE"; values: Partial<SituationEnergieState> }
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
    case "SET_TELECOM":
      return { ...state, telecom: { ...state.telecom, ...action.values } };
    case "SET_ENERGIE":
      return { ...state, energie: { ...state.energie, ...action.values } };
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

  // Reprise du brouillon localStorage au montage — au cas où le conseiller
  // ferme l'onglet en plein rendez-vous (plan Phase 6.1).
  useEffect(() => {
    if (hydrated.current) return;
    hydrated.current = true;
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {
        dispatch({ type: "HYDRATE", state: JSON.parse(raw) as DiagnosticState });
        lastSaved.current = raw;
      }
    } catch {
      // Brouillon corrompu : on repart d'un wizard vierge sans bloquer le conseiller.
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
    dispatch({ type: "RESET" });
  }, []);

  return { state, dispatch, clearDraft };
}

export type DiagnosticDispatch = ReturnType<typeof useDiagnosticWizard>["dispatch"];
