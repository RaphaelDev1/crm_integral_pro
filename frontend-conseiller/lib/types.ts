// Miroir des schémas Pydantic *Out consommés par le frontend-conseiller
// (backend/schemas/*.py). Pas de génération automatique pour l'instant : à
// tenir à jour manuellement en cas d'évolution des schémas backend.

export interface Client {
  id: number;
  ref: string | null;
  prenom: string | null;
  nom: string | null;
  telephone: string | null;
  email: string | null;
  code_postal: string | null;
  ville: string | null;
  adresse: string | null;
  type_client: string | null;
  raison_sociale: string | null;
  effectif: string | null;
  operateur_actuel: string | null;
  techno: string | null;
  data_go: string | null;
  offre_actuelle: string | null;
  cout_mensuel_actuel: number | null;
  satisfaction_reseau: string | null;
  veut_rester: string | null;
  defaut_technique: string | null;
  speed_down: number | null;
  speed_up: number | null;
  fournisseur_energie: string | null;
  cout_elec: number | null;
  cout_gaz: number | null;
  economie_estimee_an: number | null;
  notes: string | null;
  date_creation: string | null;
  cree_par: string | null;
  date_relance: string | null;
  statut_relance: string | null;
  conseiller_id: number | null;
}

export interface Contrat {
  id: number;
  client_id: number | null;
  univers: string | null;
  categorie: string | null;
  fournisseur: string | null;
  nom_offre: string | null;
  cout_mensuel: number | null;
  economie_mensuelle: number | null;
  reference_contrat: string | null;
  statut_contrat: string | null;
  date_souscription: string | null;
  date_fin_engagement: string | null;
  notes: string | null;
  cree_par: string | null;
}

export interface NoteWorkflowEntry {
  date: string;
  type: "transition" | "note";
  par: string;
  // Présents seulement pour type === "transition"
  de?: string;
  vers?: string;
  commentaire?: string;
  // Présent seulement pour type === "note"
  texte?: string;
}

export interface Dossier {
  id: number;
  client_id: number;
  univers: string;
  statut: string;
  est_prospect: boolean;
  fournisseur_cible: string | null;
  reference_fournisseur: string | null;
  offre_cible_id: number | null;
  economie_annuelle_estimee: number;
  frais_annexes_cible: number;
  commission_attendue: number;
  commission_recue: number;
  date_creation: string | null;
  date_soumission: string | null;
  date_activation_prevue: string | null;
  date_activation_reelle: string | null;
  date_derniere_transition: string | null;
  conseiller_responsable: string | null;
  notes_workflow: NoteWorkflowEntry[] | null;
  documents_requis: string[];
  offre_nom: string | null;
}

export interface Notification {
  id: number;
  dossier_id: number | null;
  message: string;
  // Route relative à suivre pour une notification hors CRM (IA Conseil,
  // voir backend/models/notification.py) — prioritaire sur dossier_id quand
  // les deux sont possibles.
  lien: string | null;
  lu: boolean;
  date_creation: string | null;
}

export interface EtapeTimeline {
  cle: string;
  label: string;
  statut: "termine" | "en_cours" | "a_venir";
  date: string | null;
  icone: "check" | "clock" | "circle";
}

export interface MandatHonoraires {
  id: number;
  dossier_id: number;
  montant: number;
  taux: number;
  statut: string;
  signataire: string | null;
  date_signature: string | null;
  date_creation: string | null;
}

export interface ChampDonneeDemarche {
  valeur: string | null;
  requis: boolean;
  label: string;
}

export interface Demarche {
  id: number;
  dossier_id: number;
  mandat_id: number | null;
  univers: string;
  type_demarche: string;
  statut: string;
  canal: string;
  document_url: string | null;
  preuve_envoi: string | null;
  preuve_url: string | null;
  donnees_requises: Record<string, ChampDonneeDemarche> | null;
  notes: string | null;
  date_creation: string | null;
  date_generation: string | null;
  date_envoi: string | null;
  date_accuse: string | null;
}

export interface DemarcheRequise {
  type_demarche: string;
  label: string;
}

export interface DemarchesDossier {
  existantes: Demarche[];
  requises_non_creees: DemarcheRequise[];
}

export interface FactureAnalyse {
  operateur: string;
  prix_ht: number;
  prix_ttc: number;
  data_conso_go: number;
  options: string[];
  engagement_mois: number;
  date_fin_engagement: string;
  iban_prelevement: string;
  type_couverture: string;
  bonus_malus: string;
}

// Version persistée (table `factures_analysees`) — voir GET
// /prospects/{id}/factures-analysees, alimentée automatiquement à l'upload
// d'une facture par un prospect via son lien de collecte de documents.
export interface FactureAnalysePersistee {
  id: number;
  client_id: number | null;
  prospect_id: number | null;
  dossier_id: number | null;
  operateur: string | null;
  prix_ht: number;
  prix_ttc: number;
  data_conso_go: number;
  options: string[] | null;
  engagement_mois: number;
  date_fin_engagement: string | null;
  iban_prelevement: string | null;
  type_couverture: string | null;
  bonus_malus: string | null;
  date_analyse: string | null;
  analyse_par: string | null;
}

export interface ClientDocument {
  id: number;
  type_document: string | null;
  statut_kyc: string;
  motif_rejet: string | null;
  date_upload: string | null;
  url: string;
}

export interface HistoriqueAction {
  id: number;
  action: string;
  details: string | null;
  auteur: string | null;
  date_action: string | null;
}

export interface Prospect {
  id: number;
  ref: string | null;
  prenom: string | null;
  nom: string | null;
  telephone: string | null;
  email: string | null;
  code_postal: string | null;
  ville: string | null;
  adresse: string | null;
  type_client: string | null;
  raison_sociale: string | null;
  effectif: string | null;
  univers_interesse: string | null;
  service_principal: string | null;
  operateur_actuel: string | null;
  techno: string | null;
  data_go: string | null;
  cout_mensuel_actuel: number | null;
  offre_actuelle: string | null;
  satisfaction_reseau: string | null;
  veut_rester: string | null;
  defaut_technique: string | null;
  speed_down: number | null;
  speed_up: number | null;
  cout_elec: number | null;
  cout_gaz: number | null;
  fournisseur_energie: string | null;
  abonnements: string | null;
  lignes_multi: string | null;
  economie_estimee_an: number | null;
  notes: string | null;
  statut: string | null;
  date_relance: string | null;
  offres_interet: string | null;
  score: number | null;
  origine: string | null;
  date_creation: string | null;
  cree_par: string | null;
  client_id: number | null;
  converti_at: string | null;
  dernier_contact: string | null;
  code_insee: string | null;
  latitude: number | null;
  longitude: number | null;
  fibre_disponible: boolean | null;
  fibre_taux_couverture: number | null;
  telephone_verifie: boolean | null;
  telephone_type_ligne: string | null;
  operateur_detecte_ip: string | null;
  bonus_malus_auto: string | null;
  plage_horaire_rappel: string | null;
  motif_refus: string | null;
}

export interface DetailScoreProspect {
  facteur: string;
  poids: number;
  valeur: string;
}

export interface ScoreProspect {
  score: number;
  indicateur: string;
  details: DetailScoreProspect[];
}

export interface DocumentProspect {
  id: number;
  prospect_id: number;
  type_document: string | null;
  nom_fichier: string | null;
  mime: string | null;
  date_upload: string | null;
  url: string;
}

export interface OffreComparee {
  id: number;
  nom: string | null;
  fournisseur: string | null;
  categorie: string | null;
  univers: string | null;
  prix_mensuel: number;
  frais_activation: number;
  frais_sim: number;
  frais_resiliation: number;
  frais_portabilite: number;
  frais_annexes_total: number;
  engagement: number;
  caracteristiques: string;
  commission: number;
  data_go: number;
  economie_mensuelle: number;
  economie_annuelle: number;
  economie_annee_1: number;
  cout_1_an: number;
  url_souscription: string;
  code_affiliation: string;
}

export interface BlocRecommandation {
  titre: string;
  categorie: string;
  offres: OffreComparee[];
}

export interface Recommandations {
  principal: BlocRecommandation;
  cross_sell: BlocRecommandation[];
}

export interface OffreCompareeItem {
  // number pour une offre issue de l'ancien catalogue (backend/models/offre.py),
  // string (UUID) pour une offre IA Conseil (backend/models/ia_conseil.py::OffreConseil)
  // — voir EtapeTrame.tsx, qui alimente offres_comparees depuis une session de
  // trame. Dossier.offre_cible_id (Integer) n'est renseigné que dans le premier cas,
  // voir OffreCibleSection dans app/(conseiller)/dossiers/[id]/page.tsx.
  offre_id: number | string;
  nom: string | null;
  fournisseur: string | null;
  prix_mensuel: number | null;
  economie_mensuelle: number | null;
  frais_annexes_total?: number | null;
  comparable?: boolean;
}

export interface ComparaisonOffre {
  id: number;
  prospect_id: number | null;
  client_id: number | null;
  univers: string | null;
  categorie: string | null;
  cout_actuel_mensuel: number | null;
  offre_recommandee_id: number | null;
  offres_comparees: OffreCompareeItem[] | null;
  economie_mensuelle_estimee: number;
  economie_annuelle_estimee: number;
  contexte: string | null;
  date_comparaison: string | null;
  cree_par: string | null;
}

export interface AlerteOffre {
  id: number;
  client_id: number | null;
  contrat_id: number | null;
  offre_id: number | null;
  cout_actuel: number | null;
  cout_propose: number | null;
  economie_mensuelle: number | null;
  economie_annuelle: number | null;
  statut: string;
  date_detection: string | null;
  date_traitement: string | null;
}

export interface Kpis {
  total_clients: number;
  total_prospects: number;
  prospects_chauds: number;
  prospects_tiedes: number;
  prospects_froids: number;
  dossiers_en_cours: number;
}

export interface DashboardSummary {
  relances_retard: number;
  relances_jour: number;
  relances_venir: number;
  kpis: Kpis;
}

export interface User {
  id: number;
  username: string;
  nom_complet: string;
  role: string;
  telephone: string | null;
  actif: boolean;
  doit_changer_mdp: boolean;
}

export interface SourceVeille {
  id: number;
  univers: string | null;
  categorie: string | null;
  fournisseur: string | null;
  nom_offre: string | null;
  offre_id: number | null;
  url: string | null;
  selecteur_prix: string | null;
  actif: boolean;
  dernier_prix: number | null;
  date_derniere_verif: string | null;
  date_creation: string | null;
}

export interface VeilleHistoriquePrix {
  id: number;
  source_id: number | null;
  prix: number | null;
  date_releve: string | null;
}

export interface VeilleAlerte {
  id: number;
  source_id: number | null;
  ancien_prix: number | null;
  nouveau_prix: number | null;
  statut: string;
  date_detection: string | null;
  date_traitement: string | null;
}

export interface Parametre {
  cle: string;
  valeur: string | null;
}

export interface CatalogueSource {
  id: number;
  univers: string | null;
  categorie: string | null;
  fournisseur: string | null;
  url: string | null;
  type_source: string;
  methode: string;
  actif: boolean;
  robots_ok: boolean;
  frequence_h: number;
  date_derniere_ingestion: string | null;
  date_creation: string | null;
}

export interface OffreStaging {
  id: number;
  source_id: number | null;
  univers: string | null;
  categorie: string | null;
  fournisseur: string | null;
  nom_offre: string | null;
  prix_mensuel: number | null;
  frais_activation: number | null;
  engagement_mois: number | null;
  data_go: number | null;
  caracteristiques: string | null;
  commission_affiliation: number | null;
  url_souscription: string | null;
  code_affiliation: string | null;
  statut: string;
  confiance_llm: number | null;
  champs_incertains: string[] | null;
  offre_existante_id: number | null;
  date_detection: string | null;
  date_traitement: string | null;
}

export interface IngestionResume {
  detectees: number;
  doublons: number;
  a_verifier: number;
  changements: number;
}

export interface AbonnementSituationAudit {
  nom?: string;
  categorie?: string;
  cout?: number;
}

export interface OffreRecommandee {
  offre: OffreComparee;
  economie_an: number;
  pourquoi: string;
  source: string;
}

export interface AuditResult {
  situation_detectee: string;
  offres_recommandees: OffreRecommandee[];
  economie_totale_an: number;
  points_attention: string[];
  niveau_confiance: number;
  tracabilite: Record<string, unknown>[];
}

// P4.1 — dashboard tunnel de conversion par UTM (backend/routers/dashboard_utm.py).
export interface CampagneStats {
  utm_source: string;
  utm_campaign: string | null;
  leads: number;
  rappels_effectues: number;
  conversions: number;
  taux_conversion: number;
  ca_genere: number;
  cout_pub: number | null;
  cac: number | null;
}

export interface DashboardUtm {
  periode_debut: string | null;
  periode_fin: string | null;
  campagnes: CampagneStats[];
  totaux: CampagneStats;
}

// P4.3 — attribution multi-touch "légère" (premier vs dernier contact).
export interface ParcoursAttribution {
  premier_touch_source: string;
  dernier_touch_source: string;
  nb_prospects: number;
  nb_conversions: number;
}

export interface RepartitionSource {
  utm_source: string;
  nb_prospects: number;
  nb_conversions: number;
}

export interface DashboardAttribution {
  periode_debut: string | null;
  periode_fin: string | null;
  parcours: ParcoursAttribution[];
  par_source_premier_touch: RepartitionSource[];
  par_source_dernier_touch: RepartitionSource[];
}

// Liste nominative des inscrits (leads) sur la période — réservée aux Admin
// ("Responsable"), voir backend/routers/dashboard_utm.py::inscrits_utm.
export interface InscritUtm {
  id: number;
  prenom: string | null;
  nom: string | null;
  email: string | null;
  telephone: string | null;
  ville: string | null;
  utm_source: string;
  utm_campaign: string | null;
  date_creation: string | null;
  statut: string | null;
}

export interface DashboardUtmInscrits {
  periode_debut: string | null;
  periode_fin: string | null;
  total: number;
  inscrits: InscritUtm[];
}

// Dépense publicitaire saisie manuellement (pas d'intégration live Meta/TikTok/
// Google Ads) — c'est elle qui rend le CAC calculable dans DashboardUtm ci-dessus.
export interface CampagneCout {
  id: number;
  utm_source: string;
  utm_campaign: string | null;
  mois: string;
  cout: number;
  notes: string | null;
  cree_par: string | null;
  date_creation: string | null;
}
