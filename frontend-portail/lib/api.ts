const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface DocumentDemande {
  type_document: string;
  label_affiche: string;
  statut: "a_fournir" | "en_attente" | "valide" | "rejete";
  motif_rejet?: string | null;
  date_upload?: string | null;
}

export interface ChampDemarche {
  cle: string;
  label: string;
  valeur: string | null;
  requis: boolean;
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
  peut_renseigner_demarches: boolean;
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
