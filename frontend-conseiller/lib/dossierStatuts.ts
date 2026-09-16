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

// Statut KYC d'un document individuel (backend/models/document.py) — distinct
// du statut du dossier ci-dessus. "en_attente" (reçu, pas encore vérifié) doit
// se distinguer visuellement de "valide" pour que le conseiller voie d'un
// coup d'œil ce qui reste à vérifier.
export const LABELS_STATUT_KYC: Record<string, string> = {
  en_attente: "En attente de vérification",
  valide: "Validé",
  rejete: "Rejeté",
  erreur: "Erreur d'analyse",
};

export function statutKycBadgeClass(statut: string): string {
  switch (statut) {
    case "valide":
      return "bg-emerald-100 text-emerald-800 border border-emerald-300 hover:bg-emerald-100";
    case "rejete":
    case "erreur":
      return "bg-red-100 text-red-800 border border-red-300 hover:bg-red-100";
    default:
      return "bg-amber-100 text-amber-800 border border-amber-300 hover:bg-amber-100";
  }
}

// Statut du mandat de représentation (backend/models/mandat.py) :
// brouillon | envoye | recu | signe | refuse | erreur. Même logique de
// couleur progressive que la timeline dossier (dossier_engine.construire_timeline) :
// gris tant que rien n'est parti, orange dès l'envoi et pendant la
// vérification du retour, vert une fois validé.
export function statutMandatBadgeClass(statut: string): string {
  switch (statut) {
    case "signe":
      return "bg-emerald-100 text-emerald-800 border border-emerald-300 hover:bg-emerald-100";
    case "envoye":
    case "recu":
      return "bg-amber-100 text-amber-800 border border-amber-300 hover:bg-amber-100";
    case "refuse":
    case "erreur":
      return "bg-red-100 text-red-800 border border-red-300 hover:bg-red-100";
    default:
      return "bg-slate-100 text-slate-800 border border-slate-300 hover:bg-slate-100";
  }
}

export function statutDossierBadgeClass(statut: string): string {
  switch (statut) {
    case "actif":
    case "facture":
      return "bg-emerald-100 text-emerald-800 border border-emerald-300 hover:bg-emerald-100";
    case "echec":
      return "bg-red-100 text-red-800 border border-red-300 hover:bg-red-100";
    case "annule":
      return "bg-slate-200 text-slate-800 border border-slate-300 hover:bg-slate-200";
    case "mandat_a_signer":
    case "mandat_signe":
      return "bg-violet-100 text-violet-800 border border-violet-300 hover:bg-violet-100";
    case "soumis_fournisseur":
    case "en_activation":
      return "bg-amber-100 text-amber-800 border border-amber-300 hover:bg-amber-100";
    default:
      return "bg-blue-100 text-blue-800 border border-blue-300 hover:bg-blue-100";
  }
}
