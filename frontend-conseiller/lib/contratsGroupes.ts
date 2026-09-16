import type { Contrat } from "@/lib/types";

// Regroupe un contrat par univers — la colonne `categorie` mélange deux
// vocabulaires (celui du formulaire conseiller, ex. "Forfait mobile", et celui
// du moteur d'estimation /economiser, ex. "Box / Fibre"), donc on classe par
// mots-clés plutôt que par égalité stricte. Partagé entre ContratsTab.tsx
// (onglets Télécom/Énergie/Assurance) et EtapeSituation.tsx (préremplissage
// du diagnostic depuis les contrats existants).
export type GroupeContrat = "Télécom" | "Énergie" | "Assurance" | "Autres";

export function groupeContrat(contrat: Contrat): GroupeContrat {
  const texte = `${contrat.categorie ?? ""} ${contrat.univers ?? ""}`.toLowerCase();
  if (/mobile|box|fibre|telecom/.test(texte)) return "Télécom";
  if (/(é|e)nergie|(é|e)lectricit(é|e)|\bgaz\b/.test(texte)) return "Énergie";
  if (/assurance/.test(texte)) return "Assurance";
  return "Autres";
}
