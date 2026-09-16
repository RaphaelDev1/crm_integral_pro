import type { Contrat } from "@/lib/types";

// Miroir de src/constants.py — options métier du diagnostic. "Assurances" est
// gardé comme case cochable à l'étape 1 pour matcher le texte du plan de
// migration, mais aucune catégorie catalogue n'existe derrière (le comparateur
// /offres/comparer y renverra toujours une liste vide) : c'est volontaire,
// voir décision produit dans la session qui a créé ce module.
export const UNIVERS_DIAGNOSTIC = ["Télécom", "Énergie", "Abonnements", "Assurances"] as const;
export type UniversDiagnostic = (typeof UNIVERS_DIAGNOSTIC)[number];

// `value` reste "Box / Fibre uniquement" (comparé littéralement côté backend,
// voir backend/services/offres_engine.py) — seul `label` (affiché) utilise le
// vocabulaire "Box internet" demandé par le client.
export const SERVICE_PRINCIPAL_OPTIONS = [
  { value: "Mobile uniquement", label: "Mobile uniquement" },
  { value: "Box / Fibre uniquement", label: "Box internet uniquement" },
  { value: "Pack Box + Mobile", label: "Pack Box internet + Mobile" },
  { value: "Multi-lignes", label: "Multi-lignes" },
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
export const NIVEAUX_DEFAUT_TECHNIQUE = ["Aucun signalé", "Faible", "Moyen", "Critique"] as const;
export const VEUT_RESTER_OPTIONS = ["Oui", "Pas spécialement", "Non"] as const;
export const DEBITS_OPTIONS = ["100 Mbps", "400 Mbps", "1 Gbps", "2 Gbps", "5 Gbps", "8 Gbps"] as const;
export const GO_OPTIONS = ["1 Go", "5 Go", "10 Go", "20 Go", "30 Go", "50 Go", "80 Go", "100 Go", "Illimité"] as const;

// Tranches d'effectif pour les prospects/clients professionnels (étape Identité du diagnostic).
export const EFFECTIF_OPTIONS = ["1", "2-5", "6-9", "10-19", "20+"] as const;

// Objectif de la demande, posé sur la landing publique /economiser (socle S5
// — voir backend/schemas/lead_public.py::OBJECTIFS_PRINCIPAUX et
// frontend-portail/components/landing/EstimationForm.tsx, mêmes clés/libellés)
// — répond d'office à "raison financière ou juste un gain de temps ?" sans
// avoir à redemander au téléphone.
export const OBJECTIFS_PRINCIPAUX_OPTIONS = [
  { value: "economiser", label: "💰 Économiser" },
  { value: "simplifier", label: "✨ Simplifier" },
  { value: "ameliorer_qualite", label: "🚀 Améliorer la qualité" },
  { value: "regrouper", label: "📦 Tout regrouper" },
] as const;

export function labelObjectifPrincipal(valeur: string | null | undefined): string | undefined {
  return OBJECTIFS_PRINCIPAUX_OPTIONS.find((option) => option.value === valeur)?.label;
}

// Portabilité mobile (M-portabilité, docs/QUESTIONS_PAR_SECTEUR.md) — mêmes
// clés que frontend-portail/app/dossier/[token]/situation/page.tsx, pour un
// vocabulaire cohérent entre ce que le prospect répond et ce que le
// conseiller voit/édite.
export const CONSERVER_NUMERO_OPTIONS = [
  { value: "oui", label: "Oui, garde son numéro" },
  { value: "non", label: "Non, nouveau numéro" },
] as const;
export const TYPE_SIM_OPTIONS = [
  { value: "esim", label: "eSIM" },
  { value: "carte_sim", label: "Carte SIM" },
] as const;

// "Go minimal" est stocké en texte libre ("50 Go", "Illimité" — voir GO_OPTIONS
// ci-dessus) mais le comparateur d'offres attend un nombre (offres.py::data_go_min,
// exclut toute offre dont data_go < data_go_min). "Illimité" est mappé sur un seuil
// élevé pour ne retenir que les offres réellement très généreuses en data.
export function parseGoMinimal(valeur: string): number | undefined {
  if (!valeur) return undefined;
  if (valeur === "Illimité") return 1000;
  const nombre = Number(valeur.replace(/[^\d.]/g, ""));
  return Number.isFinite(nombre) && nombre > 0 ? nombre : undefined;
}

// `Contrat.fournisseur` est un champ texte libre (ContratForm.tsx) alors que
// le <Select> "Opérateur actuel" du diagnostic n'affiche une valeur que si
// elle correspond EXACTEMENT à une option de LISTE_OPERATEURS_TEL — sinon le
// select paraît vide même si l'état a bien été mis à jour. On normalise donc
// le fournisseur du contrat vers l'option la plus proche avant de préremplir.
const ALIAS_OPERATEURS: Record<string, (typeof LISTE_OPERATEURS_TEL)[number]> = {
  orange: "Orange",
  youprice: "YouPrice (Réseau Orange)",
  sfr: "SFR",
  bouygues: "Bouygues",
  btel: "Bouygues",
  free: "Free",
};

export function matchOperateur(fournisseur: string | null | undefined): string {
  const valeur = (fournisseur || "").trim();
  if (!valeur) return "";
  const normalisee = valeur.toLowerCase();
  const exact = (LISTE_OPERATEURS_TEL as readonly string[]).find((o) => o.toLowerCase() === normalisee);
  if (exact) return exact;
  const alias = Object.entries(ALIAS_OPERATEURS).find(([cle]) => normalisee.includes(cle));
  if (alias) return alias[1];
  return "Autre / Aucun";
}

// Même problème que matchOperateur, côté "Go minimal" : `Contrat.consommation`
// est du texte libre ("120 Go", "50Go", "illimité"…) alors que le <Select>
// attend une valeur exacte de GO_OPTIONS. On extrait le nombre de Go et on le
// fait correspondre au palier le plus proche (au-dessus).
export function matchGoOption(consommation: string | null | undefined): string {
  const valeur = (consommation || "").trim();
  if (!valeur) return "";
  if (/illimit/i.test(valeur)) return "Illimité";
  const match = valeur.match(/(\d+(?:[.,]\d+)?)\s*go/i);
  if (!match) return "";
  const nombre = Number(match[1].replace(",", "."));
  if (!Number.isFinite(nombre) || nombre <= 0) return "";
  const paliers = GO_OPTIONS.filter((o) => o !== "Illimité");
  const palier = paliers.find((o) => Number(o.replace(/[^\d.]/g, "")) >= nombre);
  return palier ?? "Illimité";
}

// Catégories reconnues par le catalogue (backend/models/offre.py::categorie) —
// utilisées pour appeler POST /offres/comparer avec une catégorie exacte,
// contrairement à src/offres_engine.py qui acceptait categorie=None pour les
// abonnements (le endpoint backend/routers/offres.py exige une catégorie).
export const CATEGORIES_ABONNEMENT = ["Streaming Vidéo", "Musique", "Salle de sport", "SaaS / Logiciel", "Assurance", "Autre"] as const;

export const CATEGORIES_ENERGIE = ["Électricité", "Gaz"] as const;

// Mêmes tranches que backend/services/estimation_publique.py::TRANCHES_AGE —
// on ne capture plus l'âge exact dans les formulaires, seulement la tranche,
// donc ces libellés doivent rester identiques des deux côtés.
export const TRANCHES_AGE_OPTIONS = ["18-25", "26-35", "36-45", "46-55", "56-65", "66+"] as const;

export const JOURS_RAPPEL_OPTIONS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Peu importe"] as const;
export const PLAGES_HORAIRES_RAPPEL_OPTIONS = ["Matin (9h-12h)", "Après-midi (12h-17h)", "Soir (17h-20h)"] as const;

const SEPARATEUR_CRENEAU_RAPPEL = " · ";

// Le créneau de rappel reste stocké comme une seule chaîne libre côté backend
// (`plage_horaire_rappel`) — ces deux menus déroulants (jour + plage) ne sont
// qu'une aide de saisie qui compose/décompose cette chaîne, sans migration.
export function combinerCreneauRappel(jour: string, plage: string): string {
  return [jour, plage].filter(Boolean).join(SEPARATEUR_CRENEAU_RAPPEL);
}

export function decomposerCreneauRappel(valeur: string | null | undefined): { jour: string; plage: string } {
  const [jour = "", plage = ""] = (valeur ?? "").split(SEPARATEUR_CRENEAU_RAPPEL);
  return {
    jour: (JOURS_RAPPEL_OPTIONS as readonly string[]).includes(jour) ? jour : "",
    plage: (PLAGES_HORAIRES_RAPPEL_OPTIONS as readonly string[]).includes(plage) ? plage : "",
  };
}

// Réponses de la trame envoyée au prospect sur son lien personnel
// (/dossier/[token]/situation, frontend-portail) qui peuvent influencer la
// meilleure offre à recommander — voir docs/QUESTIONS_PAR_SECTEUR.md et
// memory project-trame-prospect-2026-09 (Télécom seul exposé pour l'instant).
// Si le prospect n'a répondu qu'à une partie des questions envoyées, le
// conseiller doit lui poser les autres — avant de lancer le dossier
// (EtapeRecommandations.tsx) ET une fois le dossier déjà ouvert (dossiers/[id]/page.tsx),
// d'où le partage de cette logique entre les deux écrans.
export function champsTelecomManquants(contrat: Contrat): string[] {
  const manquants: string[] = [];
  if (!contrat.satisfaction_reseau) manquants.push("Satisfaction réseau");
  if (!contrat.veut_rester) manquants.push("Souhaite rester chez son opérateur actuel");
  if (!contrat.defaut_technique) manquants.push("Défaut technique éventuel");
  if (/mobile/i.test(contrat.categorie ?? "")) {
    if (!contrat.conserver_numero) {
      manquants.push("Conservation du numéro (portabilité)");
    } else if (contrat.conserver_numero === "oui") {
      if (!contrat.rio) manquants.push("RIO");
      if (!contrat.numero_ligne) manquants.push("Numéro de ligne à porter");
    }
    if (!contrat.type_sim) manquants.push("Type de SIM (eSIM ou carte SIM)");
  }
  return manquants;
}

// Domaines email les plus courants chez les prospects/clients (FAI + webmails
// grand public) — proposés en suggestions de saisie sur le champ email des
// fiches prospect/client pour éviter de retaper la fin de l'adresse à chaque
// fois (voir EmailField dans ProspectForm.tsx/ClientForm.tsx).
export const DOMAINES_EMAIL_COURANTS = [
  "gmail.com",
  "yahoo.fr",
  "hotmail.fr",
  "outlook.fr",
  "orange.fr",
  "free.fr",
  "sfr.fr",
  "laposte.net",
  "wanadoo.fr",
  "icloud.com",
] as const;

// Champs d'identité socle requis par la page "informations personnelles" du
// tunnel de souscription Free Mobile (voir souscription_engine.py) —
// communs à Prospect et Client (migration 0053).
export function champsIdentiteManquants(entite: {
  date_naissance: string | null;
  departement_naissance: string | null;
  ville_naissance: string | null;
} | null | undefined): string[] {
  if (!entite) return [];
  const manquants: string[] = [];
  if (!entite.date_naissance) manquants.push("Date de naissance");
  if (!entite.departement_naissance) manquants.push("Département de naissance");
  if (!entite.ville_naissance) manquants.push("Ville de naissance");
  return manquants;
}
