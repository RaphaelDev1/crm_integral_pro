"use client";

import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { AnswerInput } from "@/components/ia-conseil/AnswerInput";
import type { Question } from "@/lib/types-ia-conseil";

interface QuestionCardProps {
  question: Question;
  questionsRestantesEstimees: number;
  presentation: boolean;
  onRepondre: (valeur: unknown) => void;
  isSubmitting?: boolean;
  valeurParDefaut?: string;
}

// Centre de la vue Trame Live (§Vision du rendu final) : la question
// courante, en grand, une seule à la fois — le moteur "escargot" côté
// backend a déjà choisi que c'était la plus informative (voir
// rules_engine/question_selector.py).
export function QuestionCard({
  question,
  questionsRestantesEstimees,
  presentation,
  onRepondre,
  isSubmitting,
  valeurParDefaut,
}: QuestionCardProps) {
  return (
    <Card className="mx-auto w-full max-w-2xl">
      <CardHeader className="items-center text-center">
        {!presentation && (
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            ~{questionsRestantesEstimees} question{questionsRestantesEstimees > 1 ? "s" : ""} restante
            {questionsRestantesEstimees > 1 ? "s" : ""}
          </p>
        )}
        <h2 className={presentation ? "text-3xl font-bold" : "text-2xl font-semibold"}>{question.label}</h2>
        {question.help && <p className="text-sm text-muted-foreground">{question.help}</p>}
      </CardHeader>
      <CardContent className="flex flex-col items-center gap-4 pb-8">
        <AnswerInput
          key={question.id}
          question={question}
          onSubmit={onRepondre}
          isSubmitting={isSubmitting}
          valeurParDefaut={valeurParDefaut}
        />
      </CardContent>
    </Card>
  );
}
