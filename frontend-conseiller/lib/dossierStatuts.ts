// Miroir statique de backend/services/dossier_engine.py (STATUTS_DOSSIER,
// TRANSITIONS_AUTORISEES). Pure donnée de graphe d'états qui ne change pas
// souvent et n'est pas exposée en HTTP (peut_transiter n'est qu'une fonction
// Python interne) — la dupliquer ici évite un aller-retour réseau par écran.

export const STATUTS_DOSSIER = [
  "initie",
  "docs_demandes",
  "docs_recus",
  "mandat_a_signer",
  "mandat_signe",
  "soumis_fournisseur",
  "en_activation",
  "actif",
  "facture",
  "echec",
  "annule",
] as const;

export type StatutDossier = (typeof STATUTS_DOSSIER)[number];

export const LABELS_STATUT_DOSSIER: Record<StatutDossier, string> = {
  initie: "Initié",
  docs_demandes: "Documents demandés",
  docs_recus: "Documents reçus",
  mandat_a_signer: "Mandat à signer",
  mandat_signe: "Mandat signé",
  soumis_fournisseur: "Soumis au fournisseur",
  en_activation: "En activation",
  actif: "Actif",
  facture: "Facturé",
  echec: "Échec",
  annule: "Annulé",
};

export const TRANSITIONS_AUTORISEES: Record<StatutDossier, StatutDossier[]> = {
  initie: ["docs_demandes", "annule"],
  docs_demandes: ["docs_recus", "annule", "echec"],
  docs_recus: ["mandat_a_signer", "annule", "echec"],
  mandat_a_signer: ["mandat_signe", "annule", "echec"],
  mandat_signe: ["soumis_fournisseur", "annule", "echec"],
  soumis_fournisseur: ["en_activation", "echec"],
  en_activation: ["actif", "echec"],
  actif: ["facture"],
  facture: [],
  echec: [],
  annule: [],
};

export function statutDossierBadgeClass(statut: string): string {
  switch (statut) {
    case "actif":
    case "facture":
      return "bg-emerald-100 text-emerald-800 hover:bg-emerald-100";
    case "echec":
      return "bg-red-100 text-red-800 hover:bg-red-100";
    case "annule":
      return "bg-slate-200 text-slate-700 hover:bg-slate-200";
    case "mandat_a_signer":
    case "mandat_signe":
      return "bg-violet-100 text-violet-800 hover:bg-violet-100";
    case "soumis_fournisseur":
    case "en_activation":
      return "bg-amber-100 text-amber-800 hover:bg-amber-100";
    default:
      return "bg-blue-100 text-blue-800 hover:bg-blue-100";
  }
}
