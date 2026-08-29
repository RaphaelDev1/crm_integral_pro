// Miroir de backend/schemas/ia_conseil.py — sous-système "IA Conseil"
// (PLAN_IMPLEMENTATION_4_PHASES.md), isolé du CRM existant (lib/types.ts).
// Préfixe /api/v1, pas de génération automatique (même convention que
// lib/types.ts) : à tenir à jour manuellement si les schémas backend évoluent.

export interface CategorieConseil {
  id: string;
  slug: string;
  nom: string;
  ordre: number | null;
  actif: boolean;
}

export interface FournisseurConseil {
  id: string;
  nom: string;
  categorie_slug: string | null;
  note_fiabilite: number | null;
  logo_url: string | null;
  site_url: string | null;
  affilie: boolean;
  taux_commission: number | null;
}

export interface OffreConseil {
  id: string;
  fournisseur_id: string | null;
  categorie_slug: string | null;
  nom: string;
  prix_mensuel: number | null;
  prix_apres_promo: number | null;
  duree_promo_mois: number | null;
  engagement_mois: number;
  frais_mise_en_service: number;
  caracteristiques: Record<string, unknown>;
  conditions: Record<string, unknown> | null;
  source: string | null;
  source_ref: string | null;
  valide: boolean;
  date_maj: string;
}

export type OffreConseilInput = Omit<OffreConseil, "id" | "date_maj">;

export interface ClientConseil {
  id: string;
  conseiller_id: number | null;
  prenom: string | null;
  nom: string | null;
  email: string | null;
  telephone: string | null;
  adresse: Record<string, unknown> | null;
  foyer: Record<string, unknown> | null;
  profil: Record<string, unknown> | null;
  cree_le: string;
}

export type ClientConseilInput = Omit<ClientConseil, "id" | "conseiller_id" | "cree_le">;

export type Canal = "visio" | "telephone" | "physique";

// Suggestion inter-catégories (§2.4) — renseignée uniquement dans la réponse
// de POST /sessions/{id}/finalize, vide ([]) partout ailleurs.
export interface CrossSellSuggestion {
  type: "convergence" | "conseil";
  categorie_source: string | null;
  message: string;
}

export interface SessionTrame {
  id: string;
  client_id: string | null;
  conseiller_id: number | null;
  categorie_slug: string | null;
  trame_template_id: string | null;
  reponses: Record<string, unknown>;
  etat: "en_cours" | "terminee" | "abandonnee";
  canal: Canal | null;
  demarree_le: string;
  terminee_le: string | null;
  suggestions_cross_sell: CrossSellSuggestion[];
}

export type QuestionType = "number" | "select" | "boolean" | "text" | "adresse";

export interface Question {
  id: string;
  label: string;
  type: QuestionType;
  unit?: string;
  help?: string;
  required?: boolean;
  min?: number;
  max?: number;
  options?: string[];
  options_ref?: string;
  [cle: string]: unknown;
}

export interface NextQuestionOut {
  question: Question | null;
  questions_restantes_estimees: number;
  terminee: boolean;
}

export interface AlerteOut {
  regle: string;
  severite: "info" | "attention" | "critique";
  message: string;
}

export interface RecommandationOut {
  id: string | null;
  offre_id: string;
  offre: OffreConseil | null;
  score: number;
  rang: number;
  justifications: string[];
  alertes: AlerteOut[];
  economie_mensuelle: number | null;
  economie_annuelle: number | null;
}

export interface AlerteOverride {
  id: string;
  session_id: string | null;
  offre_id: string | null;
  regle_nom: string;
  justification: string;
  conseiller_id: number | null;
  cree_le: string;
}

export type AlerteOverrideInput = {
  offre_id: string;
  regle_nom: string;
  justification: string;
};

// Corps de l'erreur 409 renvoyée par POST /api/v1/souscriptions quand la
// recommandation choisie porte une alerte critique non levée (voir
// backend/routers/ia_conseil_souscriptions.py::creer_souscription et
// ApiError.payload dans lib/api.ts).
export interface AlertesBloquantesPayload {
  message: string;
  alertes: AlerteOut[];
}

export interface SouscriptionConseil {
  id: string;
  client_id: string | null;
  offre_id: string | null;
  session_id: string | null;
  conseiller_id: number | null;
  date_souscription: string | null;
  date_activation: string | null;
  prix_mensuel_negocie: number | null;
  commission_prevue: number | null;
  commission_encaissee: number | null;
  statut: "en_attente" | "active" | "resiliee" | "annulee";
  fin_engagement: string | null;
}

export type SouscriptionConseilInput = {
  client_id: string;
  offre_id: string;
  session_id?: string | null;
  date_souscription?: string | null;
  prix_mensuel_negocie?: number | null;
  fin_engagement?: string | null;
};

// Vue lecture-seule exposée sans authentification (lien partageable §1.5.1),
// voir backend/schemas/ia_conseil.py::SessionPublicOut.
export interface SessionPublicOut {
  id: string;
  categorie_slug: string | null;
  etat: SessionTrame["etat"];
  demarree_le: string;
  terminee_le: string | null;
  next_question: NextQuestionOut;
  recommandations: RecommandationOut[];
}

// Résumé agrégé du dashboard conseiller (§2.5), voir
// backend/routers/ia_conseil_dashboard.py::resume_ia_conseil.
export interface EconomieParCategorie {
  categorie_slug: string | null;
  economie_annuelle_totale: number;
}

export interface PipelineSouscriptions {
  en_attente: number;
  active: number;
  resiliee: number;
  annulee: number;
}

export interface AlerteClient {
  id: string;
  type: string;
  date_prevue: string;
  client_id: string | null;
}

export interface CommissionMensuelle {
  mois: string;
  prevue: number;
  encaissee: number;
}

export interface DashboardIaConseil {
  economies_ytd_total: number;
  economies_ytd_par_categorie: EconomieParCategorie[];
  pipeline: PipelineSouscriptions;
  alertes_clients: AlerteClient[];
  commissions_mensuelles: CommissionMensuelle[];
}

export interface AntiBiaisConseiller {
  conseiller_id: number | null;
  nb_souscriptions_avec_session: number;
  nb_biais_possible: number;
  ratio: number;
  au_dela_du_seuil: boolean;
}

// §3.1 — facture téléversée pendant une session, analysée via Claude vision
// (voir backend/services/facture_analyzer.py, réutilisé tel quel) puis
// proposée pour auto-remplissage. `extraction.propositions_reponses` est la
// map question_id -> valeur suggérée (mapping partiel selon la catégorie,
// voir backend/services/ia_conseil_facture.py::MAPPING_PAR_CATEGORIE).
export interface SessionFacture {
  id: string;
  session_id: string | null;
  categorie_slug: string | null;
  nom_fichier: string | null;
  statut: "en_attente" | "analysee" | "echouee";
  extraction: (Record<string, unknown> & { propositions_reponses?: Record<string, unknown> }) | null;
  reponses_appliquees: Record<string, unknown> | null;
  erreur: string | null;
  cree_le: string;
  analysee_le: string | null;
}

// §3.4 — rapport hebdomadaire de l'agent de veille marché autonome.
export interface OffreDetecteeVeilleMarche {
  fournisseur: string;
  nom_offre: string;
  prix_mensuel?: number;
  caracteristiques?: string;
  url_source: string;
  confiance: "fiable" | "a_verifier";
}

export interface RapportVeilleMarche {
  id: string;
  categorie_slug: string | null;
  semaine_debut: string;
  offres_detectees: OffreDetecteeVeilleMarche[];
  statut: "en_attente" | "traite";
  cree_le: string;
}

// §3.5 — prévision de churn + scoring client.
export interface ScoreClient {
  client_id: string;
  proba_churn: number | null;
  proba_cross_sell: number | null;
  segment: string | null;
  source: "modele" | "heuristique";
}

// §3.2 — copilote conseiller (streaming SSE, voir app/api/ia-conseil-copilot).
export type CopilotMode = "suggestion" | "incoherence" | "reformulation";

// Message reçu sur le flux temps réel (voir app/api/ia-conseil-live/[sessionId]).
export type SessionTrameLiveMessage =
  | { type: "reponse"; question_id?: string; next_question: NextQuestionOut; recommandations: RecommandationOut[] }
  | { type: "finalisee" }
  | { type: "facture_analysee"; facture_id: string; statut: SessionFacture["statut"]; extraction: SessionFacture["extraction"] };
