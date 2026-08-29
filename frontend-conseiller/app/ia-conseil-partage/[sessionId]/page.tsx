"use client";

import { useParams, useSearchParams } from "next/navigation";

import { AlertesBanner } from "@/components/ia-conseil/AlertesBanner";
import { LiveRecommandations } from "@/components/ia-conseil/LiveRecommandations";
import { Skeleton } from "@/components/ui/skeleton";
import { usePublicSession } from "@/lib/hooks/useIaConseil";

// Vue lecture-seule envoyée au client (§1.5.1, multi-canal) — pas d'auth, pas
// de sidebar (route hors du groupe (conseiller), voir middleware.ts). Mode
// présentation forcé : aucune donnée backoffice, typo large, pas de saisie
// possible (c'est le conseiller qui pilote les réponses sur son écran).
export default function TramePartagePage() {
  const params = useParams<{ sessionId: string }>();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? undefined;

  const sessionQuery = usePublicSession(params.sessionId, token);

  if (!token) {
    return <ErreurPage message="Lien invalide : jeton manquant." />;
  }
  if (sessionQuery.isLoading) {
    return (
      <div className="mx-auto max-w-2xl space-y-4 p-8">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (sessionQuery.isError || !sessionQuery.data) {
    return <ErreurPage message="Ce lien est invalide ou a expiré." />;
  }

  const session = sessionQuery.data;
  const question = session.next_question.question;
  const meilleure = session.recommandations[0];

  return (
    <div className="mx-auto max-w-2xl space-y-8 p-8">
      {meilleure && <AlertesBanner alertes={meilleure.alertes} />}

      {session.etat === "terminee" || !question ? (
        <h1 className="text-center text-3xl font-bold">Votre audit est terminé — voici nos recommandations</h1>
      ) : (
        <h1 className="text-center text-3xl font-bold">{question.label}</h1>
      )}

      <LiveRecommandations recommandations={session.recommandations} presentation isLoading={false} />
    </div>
  );
}

function ErreurPage({ message }: { message: string }) {
  return (
    <div className="mx-auto flex min-h-screen max-w-md items-center justify-center p-8 text-center">
      <p className="text-muted-foreground">{message}</p>
    </div>
  );
}
