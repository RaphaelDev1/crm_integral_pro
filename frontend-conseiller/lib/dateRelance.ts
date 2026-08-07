import type { Row } from "@tanstack/react-table";

// Utilitaires partagés entre prospects/page.tsx et clients/page.tsx pour la
// colonne "Prochaine relance" (stockée en ISO YYYY-MM-DD côté backend).
export function formatDateRelance(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [annee, mois, jour] = iso.split("-");
  if (!annee || !mois || !jour) return iso;
  return `${jour}/${mois}/${annee}`;
}

// Tri explicite par date de relance (au lieu de compter sur le tri implicite
// de la valeur d'accessorFn, potentiellement concaténée à d'autres champs
// pour la recherche globale) — place les relances non planifiées (null) en
// fin de liste, quel que soit le sens du tri.
export function sortingFnDateRelance<T extends { date_relance: string | null }>(
  rowA: Row<T>,
  rowB: Row<T>
): number {
  const a = rowA.original.date_relance;
  const b = rowB.original.date_relance;
  if (!a && !b) return 0;
  if (!a) return 1;
  if (!b) return -1;
  return a < b ? -1 : a > b ? 1 : 0;
}
