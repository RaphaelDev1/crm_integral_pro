"use client";

import { useState } from "react";
import { CheckCircle2, Circle, HelpCircle, Pencil } from "lucide-react";

import { AnswerInput } from "@/components/ia-conseil/AnswerInput";
import { cn } from "@/lib/utils";
import type { Question } from "@/lib/types-ia-conseil";

export interface HistoriqueEntree {
  question: Question;
  valeur: unknown;
}

interface ProgressTreeProps {
  historique: HistoriqueEntree[];
  questionActuelle: string | null;
  terminee: boolean;
  onCorriger?: (question: Question, valeur: unknown) => void;
}

function formaterValeur(valeur: unknown): string {
  if (typeof valeur === "boolean") return valeur ? "Oui" : "Non";
  if (valeur && typeof valeur === "object" && "label" in (valeur as Record<string, unknown>)) {
    return String((valeur as Record<string, unknown>).label ?? "");
  }
  return String(valeur);
}

// Colonne gauche de la vue Trame Live (§Vision du rendu final) : arbre de
// progression visuel. Comme l'API ne renvoie qu'une question à la fois (pas
// la liste complète, principe escargot), cet historique n'est que celui de
// la navigation en cours dans ce navigateur — pas une reconstruction depuis
// session.reponses (les labels des questions déjà répondues avant un
// rechargement de page ne sont pas récupérables via l'API actuelle).
//
// "Retour arrière libre" (§1.2) : cliquer une réponse déjà donnée permet de
// la corriger (POST /answer accepte de réécrire une réponse existante). Les
// questions qui en dépendaient (branches/show_if déjà résolues) ne sont pas
// automatiquement redemandées — limitation connue, acceptable pour le MVP.
export function ProgressTree({ historique, questionActuelle, terminee, onCorriger }: ProgressTreeProps) {
  const [enEdition, setEnEdition] = useState<string | null>(null);

  return (
    <nav aria-label="Progression de la trame" className="space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Progression</p>
      <ol className="space-y-1.5">
        {historique.map((entree) => (
          <li key={entree.question.id} className="text-sm">
            {enEdition === entree.question.id ? (
              <div className="space-y-2 rounded-md border p-2">
                <p className="text-xs text-muted-foreground">{entree.question.label}</p>
                <AnswerInput
                  key={entree.question.id}
                  question={entree.question}
                  onSubmit={(valeur) => {
                    onCorriger?.(entree.question, valeur);
                    setEnEdition(null);
                  }}
                />
              </div>
            ) : (
              <button
                type="button"
                className="flex w-full items-start gap-2 rounded-md p-1 text-left hover:bg-accent disabled:cursor-default disabled:hover:bg-transparent"
                onClick={() => setEnEdition(entree.question.id)}
                disabled={!onCorriger}
              >
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-muted-foreground">{entree.question.label}</p>
                  <p className="font-medium">{formaterValeur(entree.valeur)}</p>
                </div>
                {onCorriger && <Pencil className="mt-0.5 h-3 w-3 shrink-0 text-muted-foreground" />}
              </button>
            )}
          </li>
        ))}
        {questionActuelle && !terminee && (
          <li className="flex items-center gap-2 text-sm font-medium text-primary">
            <Circle className="h-4 w-4 shrink-0 animate-pulse" />
            {questionActuelle}
          </li>
        )}
        {terminee && (
          <li className="flex items-center gap-2 text-sm font-medium text-emerald-700">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            Trame terminée
          </li>
        )}
        {historique.length === 0 && !questionActuelle && (
          <li className="flex items-center gap-2 text-sm text-muted-foreground">
            <HelpCircle className={cn("h-4 w-4 shrink-0")} />
            Aucune réponse pour l&apos;instant
          </li>
        )}
      </ol>
    </nav>
  );
}
