"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import type { DiagnosticDispatch, DiagnosticState } from "@/lib/hooks/useDiagnosticWizard";
import { SERVICE_PRINCIPAL_OPTIONS, UNIVERS_DIAGNOSTIC } from "@/lib/diagnosticConstants";
import { cn } from "@/lib/utils";

interface EtapeUniversProps {
  state: DiagnosticState;
  dispatch: DiagnosticDispatch;
}

// Étape 1 du diagnostic (plan Phase 6.3) — sélection multiple des univers à
// analyser, puis service principal recherché si "Télécom" est coché.
export function EtapeUnivers({ state, dispatch }: EtapeUniversProps) {
  function toggleUnivers(univers: string) {
    const present = state.univers.includes(univers);
    const next = present ? state.univers.filter((u) => u !== univers) : [...state.univers, univers];
    dispatch({ type: "SET_UNIVERS", univers: next });
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Univers à analyser</h2>
        <p className="text-sm text-muted-foreground">
          Cochez les univers pour lesquels vous souhaitez comparer la situation actuelle du client au catalogue.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {UNIVERS_DIAGNOSTIC.map((univers) => {
          const checked = state.univers.includes(univers);
          const inerte = univers === "Assurances";
          return (
            <Card
              key={univers}
              className={cn("cursor-pointer transition-colors", checked && "border-primary bg-primary/5")}
              onClick={() => toggleUnivers(univers)}
            >
              <CardContent className="flex items-center gap-3 p-4">
                <Checkbox checked={checked} onCheckedChange={() => toggleUnivers(univers)} />
                <div>
                  <p className="text-sm font-medium">{univers}</p>
                  {inerte && <p className="text-xs text-muted-foreground">Catalogue à venir</p>}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {state.univers.includes("Télécom") && (
        <div className="space-y-2">
          <Label>Service principal recherché</Label>
          <div className="flex flex-wrap gap-2">
            {SERVICE_PRINCIPAL_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => dispatch({ type: "SET_SERVICE_PRINCIPAL", value: option.value })}
                className={cn(
                  "rounded-full border px-3 py-1.5 text-sm transition-colors",
                  state.servicePrincipal === option.value
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-input bg-background hover:bg-accent"
                )}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
