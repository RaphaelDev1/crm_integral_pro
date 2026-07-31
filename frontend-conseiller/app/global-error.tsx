"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

export default function GlobalError({ error }: { error: Error & { digest?: string } }) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html lang="fr">
      <body className="font-sans text-slate-900 antialiased">
        <div className="max-w-2xl mx-auto px-4 py-16 text-center">
          <h1 className="text-xl font-bold text-primary mb-2">Une erreur est survenue</h1>
          <p className="text-sm text-slate-500">Merci de réessayer dans quelques instants.</p>
        </div>
      </body>
    </html>
  );
}
