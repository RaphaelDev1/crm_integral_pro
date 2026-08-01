"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";

// Fallback unique pour toutes les routes du groupe (conseiller) : une erreur
// non gérée dans une page (rendu, effet…) atterrit ici plutôt que de casser
// tout le layout Sidebar/Header. Les erreurs réseau/API gérées par React
// Query passent par le toast global (app/providers.tsx), pas par ce fichier.
export default function ConseillerError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
      <h1 className="text-lg font-semibold text-slate-800">Une erreur est survenue</h1>
      <p className="text-sm text-slate-500">Merci de réessayer dans quelques instants.</p>
      <Button onClick={reset}>Réessayer</Button>
    </div>
  );
}
