export const LABELS_TYPE_DEMARCHE: Record<string, string> = {
  mandat: "Mandat de représentation",
  resiliation: "Résiliation",
  portabilite: "Portabilité mobile",
  souscription: "Souscription",
  changement_fournisseur: "Changement de fournisseur",
  audit_mobile: "Votre situation mobile",
  audit_box: "Votre situation box / TV",
  audit_energie: "Votre situation énergie",
};

// Démarches qui constituent la trame adaptative par secteur (voir
// docs/QUESTIONS_PAR_SECTEUR.md et backend/services/demarches_engine.py::
// TYPES_QUESTIONNAIRE_SECTEUR) — affichées sur /dossier/[token]/questionnaire
// plutôt que sur /dossier/[token]/demarches, et bloquantes pour l'upload de
// documents (voir TokenContexte.audit_complet).
//
// Ce module ne porte pas "use client" volontairement : il est importé à la
// fois par des Server Components (ex. app/dossier/[token]/page.tsx) et des
// Client Components. Le définir dans un fichier "use client" empêche les
// Server Components d'utiliser les valeurs exportées (Next.js les remplace
// par une référence client, d'où l'erreur "Attempted to call has() from the
// server but has is on the client").
export const TYPES_QUESTIONNAIRE_SECTEUR = new Set([
  "audit_mobile",
  "audit_box",
  "audit_energie",
  "portabilite",
]);
