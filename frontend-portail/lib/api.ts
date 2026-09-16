const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface DocumentRecu {
  document_id: number;
  nom_fichier?: string | null;
  date_upload?: string | null;
}

export interface DocumentDemande {
  type_document: string;
  label_affiche: string;
  statut: "a_fournir" | "en_attente" | "recu" | "valide" | "rejete" | "erreur";
  motif_rejet?: string | null;
  date_upload?: string | null;
  fichiers_recus: DocumentRecu[];
}

export interface OptionChampDemarche {
  valeur: string;
  label: string;
}

export interface ChampDemarche {
  cle: string;
  label: string;
  valeur: string | null;
  requis: boolean;
  type: "texte" | "choix";
  options?: OptionChampDemarche[] | null;
  aide?: string | null;
}

export interface DemarcheAFournir {
  demarche_id: number;
  type_demarche: string;
  statut: string;
  champs: ChampDemarche[];
}

export interface TokenContexte {
  prenom_client: string;
  nom_client: string;
  dossier_id: number | null;
  univers: string | null;
  fournisseur_cible: string | null;
  economie_annuelle_estimee: number;
  statut_dossier: string | null;
  conseiller_nom: string | null;
  conseiller_telephone?: string | null;
  documents_a_fournir: DocumentDemande[];
  mandat_statut: string | null;
  peut_uploader_docs: boolean;
  peut_signer_mandat: boolean;
  demarches_a_completer: DemarcheAFournir[];
  audit_complet: boolean;
  peut_renseigner_demarches: boolean;
  peut_transmettre_speedtest: boolean;
  speedtest_fait: boolean;
  peut_renseigner_situation: boolean;
  situation_renseignee: boolean;
  peut_voir_suivi: boolean;
  // Socle de la trame mobile (docs/QUESTIONS_PAR_SECTEUR.md), posé une seule
  // fois pour la personne (pas par ligne) — voir situation/page.tsx.
  objectif_principal?: string | null;
  nb_lignes_mobiles?: string | null;
  qualite_reseau_mobile?: string | null;
  date_naissance?: string | null;
  departement_naissance?: string | null;
  ville_naissance?: string | null;
  // True = le prospect répond seul sur /situation (questions confort B4-B7
  // masquées, redemandées plus tard) ; False = le conseiller répond avec lui
  // au téléphone (formulaire complet). Sans objet pour un token client.
  remplissage_autonome?: boolean;
  // "a_signer" / "signe" / None — même principe que mandat_statut, pour le
  // mandat d'honoraires (créé/envoyé après le mandat de représentation).
  mandat_honoraires_statut?: string | null;
  // Vrai dès que le dossier a atteint (ou dépassé) l'étape "soumis_fournisseur".
  dossier_soumis_fournisseur?: boolean;
}

export interface UploadResult {
  document_id: number;
  type_detecte: string | null;
  statut_kyc: string;
  motif_rejet?: string | null;
  message: string;
}

export async function getContexte(token: string): Promise<TokenContexte> {
  const res = await fetch(`${API_URL}/portail/${token}`, { cache: "no-store" });
  if (!res.ok) {
    if (res.status === 404) throw new Error("Lien invalide, expiré ou révoqué.");
    throw new Error(`Erreur ${res.status}`);
  }
  return res.json();
}

export async function uploadDocument(
  token: string,
  typeDocument: string,
  fichier: File
): Promise<UploadResult> {
  const formData = new FormData();
  formData.append("fichier", fichier);

  const res = await fetch(
    `${API_URL}/portail/${token}/documents?type_document=${encodeURIComponent(typeDocument)}`,
    { method: "POST", body: formData }
  );
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `Erreur ${res.status}`);
  }
  return res.json();
}

export interface SpeedtestResultat {
  speed_down?: number | null;
  speed_up?: number | null;
  document_id?: number | null;
  message: string;
}

export interface ContratTelecom {
  id: number;
  categorie: string | null;
  fournisseur: string | null;
  nom_offre: string | null;
  satisfaction_reseau?: string | null;
  veut_rester?: string | null;
  defaut_technique?: string | null;
  situation_renseignee?: boolean;
  consommation?: string | null;
  date_fin_engagement?: string | null;
  conserver_numero?: string | null;
  rio?: string | null;
  numero_ligne?: string | null;
  type_sim?: string | null;
  chauffage_principal?: string | null;
  puissance_kva?: string | null;
  option_tarifaire?: string | null;
  gros_equipement_electrique?: boolean | null;
  usage_tv?: string | null;
  abonnements_payants?: string | null;
  // Trame Box B4/B5/B6/B7 (docs/QUESTIONS_PAR_SECTEUR.md) — posées
  // uniquement sur /situation, jamais sur /economiser.
  nb_utilisateurs_streaming?: string | null;
  usage_4k?: boolean | null;
  teletravail?: string | null;
  interet_box_4g5g?: string | null;
  telephone_fixe_utilise?: string | null;
  appels_fixe_mensuels?: string | null;
  speed_down?: number | null;
  debit_declare?: number | null;
}

// Liste les forfaits concurrents du client/prospect, pour lui permettre de
// préciser à quel forfait un test de débit se rapporte (mobile/box par
// défaut) ou de répondre à la trame par secteur sur /situation
// (avecEnergie: true, élargit aussi à l'Énergie électricité/gaz).
export async function getContratsTelecom(token: string, options?: { avecEnergie?: boolean }): Promise<ContratTelecom[]> {
  const query = options?.avecEnergie ? "?avec_energie=true" : "";
  const res = await fetch(`${API_URL}/portail/${token}/contrats-telecom${query}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Erreur ${res.status}`);
  return res.json();
}

export async function soumettreSpeedtest(
  token: string,
  resultat: { download_mbps: number; upload_mbps: number; ping_ms?: number; contrat_id?: number }
): Promise<SpeedtestResultat> {
  const formData = new FormData();
  formData.append("download_mbps", String(resultat.download_mbps));
  formData.append("upload_mbps", String(resultat.upload_mbps));
  if (resultat.ping_ms !== undefined) formData.append("ping_ms", String(resultat.ping_ms));
  if (resultat.contrat_id !== undefined) formData.append("contrat_id", String(resultat.contrat_id));

  const res = await fetch(`${API_URL}/portail/${token}/speedtest`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `Erreur ${res.status}`);
  }
  return res.json();
}

export async function soumettreSpeedtestFichier(
  token: string,
  fichier: File
): Promise<SpeedtestResultat> {
  const formData = new FormData();
  formData.append("fichier", fichier);

  const res = await fetch(`${API_URL}/portail/${token}/speedtest`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `Erreur ${res.status}`);
  }
  return res.json();
}

export interface SituationActuelleValeurs {
  operateur_actuel?: string;
  satisfaction_reseau?: string;
  veut_rester?: string;
  defaut_technique?: string;
  cout_mensuel?: number;
  contrat_id?: number;
  categorie?: string;
  // Socle de la trame mobile (docs/QUESTIONS_PAR_SECTEUR.md) — posé une
  // seule fois, routé côté backend vers Prospect plutôt que le contrat ciblé.
  objectif_principal?: string;
  nb_lignes_mobiles?: string;
  qualite_reseau_mobile?: string;
  date_naissance?: string;
  departement_naissance?: string;
  ville_naissance?: string;
  // Par ligne — routés vers le Contrat ciblé par contrat_id/categorie.
  consommation?: string;
  date_fin_engagement?: string;
  conserver_numero?: string;
  rio?: string;
  numero_ligne?: string;
  type_sim?: string;
  chauffage_principal?: string;
  puissance_kva?: string;
  option_tarifaire?: string;
  gros_equipement_electrique?: boolean;
  usage_tv?: string;
  abonnements_payants?: string;
  nb_utilisateurs_streaming?: string;
  usage_4k?: boolean;
  teletravail?: string;
  interet_box_4g5g?: string;
  telephone_fixe_utilise?: string;
  appels_fixe_mensuels?: string;
}

export async function soumettreSituationActuelle(
  token: string,
  valeurs: SituationActuelleValeurs
): Promise<TokenContexte> {
  const res = await fetch(`${API_URL}/portail/${token}/situation`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(valeurs),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `Erreur ${res.status}`);
  }
  return res.json();
}

export interface SuiviEtape {
  cle: string;
  label: string;
  statut: "termine" | "en_cours" | "a_venir";
  date?: string | null;
  icone: string;
}

export interface SuiviDossier {
  dossier_id: number;
  statut_actuel: string;
  etapes: SuiviEtape[];
  prochaine_action?: string | null;
  delai_estime?: string | null;
}

export async function getSuivi(token: string): Promise<SuiviDossier> {
  const res = await fetch(`${API_URL}/portail/${token}/suivi`, { cache: "no-store" });
  if (!res.ok) {
    if (res.status === 403) throw new Error("Le suivi n'est pas disponible sur ce lien.");
    throw new Error(`Erreur ${res.status}`);
  }
  return res.json();
}

export async function soumettreChampsDemarche(
  token: string,
  demarcheId: number,
  valeurs: Record<string, string>
): Promise<DemarcheAFournir> {
  const res = await fetch(`${API_URL}/portail/${token}/demarches/${demarcheId}/champs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ valeurs }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `Erreur ${res.status}`);
  }
  return res.json();
}
