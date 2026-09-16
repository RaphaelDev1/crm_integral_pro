"use client";

import type { ReactNode } from "react";
import { Eye, EyeOff } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface TrameLayoutProps {
  presentation: boolean;
  onTogglePresentation: () => void;
  left: ReactNode;
  center: ReactNode;
}

// 2 colonnes responsive (§Vision du rendu final) : progression / question
// courante. La colonne recommandations live a été retirée de cette vue
// conseiller (elle prenait trop de place et gênait la lecture des
// questions) — les recommandations restent visibles à la clôture de chaque
// onglet et sur la vue partagée client (ia-conseil-partage/[sessionId]/page.tsx),
// qui garde LiveRecommandations. Seuls les éléments backoffice (commission,
// notes internes) sont masqués dans les enfants en mode présentation.
export function TrameLayout({ presentation, onTogglePresentation, left, center }: TrameLayoutProps) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-end">
        <Button variant="outline" size="sm" onClick={onTogglePresentation}>
          {presentation ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          {presentation ? "Quitter le mode présentation" : "Mode présentation"}
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[240px_1fr]">
        <aside className="order-2 lg:order-1">{left}</aside>
        <main className={cn("order-1 flex flex-col items-center justify-center gap-4 lg:order-2")}>{center}</main>
      </div>
    </div>
  );
}
