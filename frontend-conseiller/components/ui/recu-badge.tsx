import { CheckCircle2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";

// Pastille "✓ Reçu" — même langage visuel que le portail client
// (frontend-portail/app/dossier/[token]/page.tsx::StatutBadge) et que les
// autres pastilles emerald du conseiller (scoreBadgeClass, statutDossierBadgeClass).
export function RecuBadge({ label = "Reçu" }: { label?: string }) {
  return (
    <Badge variant="outline" className="bg-emerald-100 text-emerald-800 hover:bg-emerald-100">
      <CheckCircle2 className="mr-1 h-3 w-3" />
      {label}
    </Badge>
  );
}

export function AEnvoyerBadge({ label = "À envoyer" }: { label?: string }) {
  return (
    <Badge variant="outline" className="bg-orange-100 text-orange-700 hover:bg-orange-100">
      {label}
    </Badge>
  );
}
