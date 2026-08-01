"use client";

import { Check } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface WizardStepDef {
  id: string;
  titre: string;
}

interface WizardProps {
  steps: readonly WizardStepDef[];
  currentIndex: number;
  onNext: () => void;
  onPrev: () => void;
  onGoToStep?: (index: number) => void;
  canGoNext: boolean;
  isSubmitting?: boolean;
  isLastStep?: boolean;
  hideNext?: boolean;
  nextLabel?: string;
  children: ReactNode;
}

// Composant wizard réutilisable — barre de progression + boutons
// Précédent/Suivant. La validation Zod par étape est faite en amont (page
// diagnostic) : ce composant ne fait que refléter `canGoNext` reçu en prop.
// Cliquer sur une étape déjà franchie permet d'y revenir sans perdre la
// saisie (cf. plan Phase 6.2 — "j'ai fini plus tôt").
export function Wizard({
  steps,
  currentIndex,
  onNext,
  onPrev,
  onGoToStep,
  canGoNext,
  isSubmitting,
  isLastStep,
  hideNext,
  nextLabel,
  children,
}: WizardProps) {
  const progress = ((currentIndex + 1) / steps.length) * 100;

  return (
    <div className="space-y-6">
      <div>
        <ol className="mb-2 flex items-center justify-between text-sm">
          {steps.map((step, index) => {
            const complete = index < currentIndex;
            const active = index === currentIndex;
            const clickable = complete && Boolean(onGoToStep);
            return (
              <li key={step.id} className="flex flex-1 items-center">
                <button
                  type="button"
                  disabled={!clickable}
                  onClick={() => clickable && onGoToStep?.(index)}
                  className={cn(
                    "flex items-center gap-2 rounded-md px-1 py-0.5",
                    clickable && "cursor-pointer hover:underline",
                    !clickable && "cursor-default"
                  )}
                >
                  <span
                    className={cn(
                      "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-semibold",
                      active && "border-primary bg-primary text-primary-foreground",
                      complete && "border-primary bg-primary/10 text-primary",
                      !active && !complete && "border-muted-foreground/30 text-muted-foreground"
                    )}
                  >
                    {complete ? <Check className="h-3.5 w-3.5" /> : index + 1}
                  </span>
                  <span
                    className={cn(
                      "hidden font-medium sm:inline",
                      active ? "text-foreground" : "text-muted-foreground"
                    )}
                  >
                    {step.titre}
                  </span>
                </button>
                {index < steps.length - 1 && <div className="mx-2 h-px flex-1 bg-border" />}
              </li>
            );
          })}
        </ol>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${progress}%` }} />
        </div>
      </div>

      <div>{children}</div>

      <div className="flex items-center justify-between border-t pt-4">
        <Button type="button" variant="outline" onClick={onPrev} disabled={currentIndex === 0 || isSubmitting}>
          Retour
        </Button>
        {!hideNext && (
          <Button type="button" onClick={onNext} disabled={!canGoNext || isSubmitting}>
            {isSubmitting ? "Veuillez patienter…" : nextLabel ?? (isLastStep ? "Terminer" : "Suivant")}
          </Button>
        )}
      </div>
    </div>
  );
}
