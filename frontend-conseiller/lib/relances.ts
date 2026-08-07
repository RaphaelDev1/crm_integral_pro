// Classement des relances clients/prospects par fenêtre temporelle — miroir en
// TS de backend/routers/dashboard.py::_classer_relance/_parse_date_relance
// (format ISO YYYY-MM-DD, produit nativement par les <input type="date"> du
// frontend). Utilisé côté front pour obtenir les items cliquables (le endpoint
// /dashboard/summary ne renvoie que des compteurs, pas les items).
export type FenetreRelance = "retard" | "jour" | "venir";

export interface RelanceItem {
  id: number;
  type: "client" | "prospect";
  label: string;
  ref: string | null;
  theme: string | null;
  score: number | null;
  economieEstimeeAn: number | null;
  dateRelance: string;
  statutRelance: string | null;
}

function parseDateRelance(valeur: string | null | undefined): Date | null {
  if (!valeur) return null;
  const [annee, mois, jour] = valeur.split("-").map(Number);
  if (!jour || !mois || !annee) return null;
  const date = new Date(annee, mois - 1, jour);
  return Number.isNaN(date.getTime()) ? null : date;
}

function debutJournee(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

export function classerRelance(dateRelance: string | null | undefined, aujourdhui: Date): FenetreRelance | null {
  const parsee = parseDateRelance(dateRelance);
  if (parsee === null) return null;
  const jourParsee = debutJournee(parsee);
  const jourAujourdhui = debutJournee(aujourdhui);
  if (jourParsee < jourAujourdhui) return "retard";
  if (jourParsee === jourAujourdhui) return "jour";
  return "venir";
}

// "À venir" limité à 7 jours pour la carte dashboard (au-delà, ce n'est plus
// une échéance imminente pour le conseiller).
export function dansLesSeptProchainsJours(dateRelance: string | null | undefined, aujourdhui: Date): boolean {
  const parsee = parseDateRelance(dateRelance);
  if (parsee === null) return false;
  const diffJours = (debutJournee(parsee) - debutJournee(aujourdhui)) / 86_400_000;
  return diffJours > 0 && diffJours <= 7;
}
