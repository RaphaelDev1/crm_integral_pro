// Miroir de src/constants.py — options métier du diagnostic. "Assurances" est
// gardé comme case cochable à l'étape 1 pour matcher le texte du plan de
// migration, mais aucune catégorie catalogue n'existe derrière (le comparateur
// /offres/comparer y renverra toujours une liste vide) : c'est volontaire,
// voir décision produit dans la session qui a créé ce module.
export const UNIVERS_DIAGNOSTIC = ["Télécom", "Énergie", "Abonnements", "Assurances"] as const;
export type UniversDiagnostic = (typeof UNIVERS_DIAGNOSTIC)[number];

export const SERVICE_PRINCIPAL_OPTIONS = [
  "Mobile uniquement",
  "Box / Fibre uniquement",
  "Pack Box + Mobile",
  "Multi-lignes",
] as const;

export const LISTE_OPERATEURS_TEL = ["Orange", "YouPrice (Réseau Orange)", "SFR", "Bouygues", "Free", "Autre / Aucun"] as const;
export const LISTE_FOURNISSEURS_ENERGIE = [
  "EDF",
  "Engie",
  "TotalEnergies",
  "Eni",
  "Vattenfall",
  "Ekwateur",
  "OHM Énergie",
  "Autre / Aucun",
] as const;
export const LISTE_TECHNO = ["FIBRE", "ADSL", "5G", "4G"] as const;
export const LISTE_TECHNO_MOBILE = ["5G", "4G"] as const;
export const SATISFACTION_RESEAU = ["😀 Très content", "😐 Ça va", "😡 Pas du tout"] as const;
export const DEBITS_OPTIONS = ["100 Mbps", "400 Mbps", "1 Gbps", "2 Gbps", "5 Gbps", "8 Gbps"] as const;

// Catégories reconnues par le catalogue (backend/models/offre.py::categorie) —
// utilisées pour appeler POST /offres/comparer avec une catégorie exacte,
// contrairement à src/offres_engine.py qui acceptait categorie=None pour les
// abonnements (le endpoint backend/routers/offres.py exige une catégorie).
export const CATEGORIES_ABONNEMENT = ["Streaming Vidéo", "Musique", "Salle de sport", "SaaS / Logiciel", "Assurance", "Autre"] as const;

export const CATEGORIES_ENERGIE = ["Électricité", "Gaz"] as const;
