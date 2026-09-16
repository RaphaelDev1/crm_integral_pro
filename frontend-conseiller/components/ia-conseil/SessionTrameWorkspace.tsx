"use client";

import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertesBanner } from "@/components/ia-conseil/AlertesBanner";
import { CopilotSidebar } from "@/components/ia-conseil/CopilotSidebar";
import { FactureUploadPanel } from "@/components/ia-conseil/FactureUploadPanel";
import { ProgressTree, type HistoriqueEntree } from "@/components/ia-conseil/ProgressTree";
import { QuestionCard } from "@/components/ia-conseil/QuestionCard";
import { SyntheseModal } from "@/components/ia-conseil/SyntheseModal";
import { TrameLayout } from "@/components/ia-conseil/TrameLayout";
import { useSessionTrameLive } from "@/lib/hooks/useSessionTrameLive";
import {
  iaConseilClientsResource,
  useCreerLienPartage,
  useFinaliserSession,
  useNextQuestion,
  useRecommandations,
  useRepondre,
  useSessionTrame,
} from "@/lib/hooks/useIaConseil";
import type { CrossSellSuggestion, NextQuestionOut, Question, RecommandationOut, SessionFacture, SessionTrameLiveMessage } from "@/lib/types-ia-conseil";

interface SessionTrameWorkspaceProps {
  clientId: string;
  sessionId: string;
}

// Corps de la page /ia-conseil/clients/[id]/trame/[sessionId] (voir ce
// fichier, désormais un simple wrapper de route), extrait ici pour rester
// réutilisable ailleurs qu'à cette route. clientId/sessionId sont passés en
// props plutôt que lus via useParams() : aucune autre dépendance à la route.
export function SessionTrameWorkspace({ clientId, sessionId }: SessionTrameWorkspaceProps) {
  const queryClient = useQueryClient();

  const [presentation, setPresentation] = useState(false);
  const [historique, setHistorique] = useState<HistoriqueEntree[]>([]);
  const [syntheseOpen, setSyntheseOpen] = useState(false);
  const [suggestionsCrossSell, setSuggestionsCrossSell] = useState<CrossSellSuggestion[]>([]);

  const sessionQuery = useSessionTrame(sessionId);
  const clientQuery = iaConseilClientsResource.useOne(clientId);
  const nextQuestionQuery = useNextQuestion(sessionId);
  const recommandationsQuery = useRecommandations(sessionId);
  const repondreMutation = useRepondre(sessionId);
  const finaliserMutation = useFinaliserSession(sessionId);
  const creerLienPartage = useCreerLienPartage();

  const partagerAvecLeClient = () => {
    creerLienPartage.mutate(sessionId, {
      onSuccess: async ({ token }) => {
        const url = `${window.location.origin}/ia-conseil-partage/${sessionId}?token=${token}`;
        try {
          await navigator.clipboard.writeText(url);
          toast.success("Lien client copié dans le presse-papiers.");
        } catch {
          toast.success(url);
        }
      },
      onError: () => toast.error("Impossible de générer le lien de partage."),
    });
  };

  const onLiveMessage = useCallback(
    (message: SessionTrameLiveMessage) => {
      if (message.type === "reponse") {
        queryClient.setQueryData<NextQuestionOut>(["ia-conseil-sessions", sessionId, "next-question"], message.next_question);
        queryClient.setQueryData<RecommandationOut[]>(["ia-conseil-sessions", sessionId, "recommandations"], message.recommandations);
      }
      if (message.type === "finalisee") {
        setSyntheseOpen(true);
      }
      if (message.type === "facture_analysee") {
        queryClient.setQueryData<SessionFacture>(
          ["ia-conseil-sessions", sessionId, "facture", message.facture_id],
          (precedente) =>
            precedente
              ? { ...precedente, statut: message.statut, extraction: message.extraction }
              : precedente
        );
      }
    },
    [queryClient, sessionId]
  );
  useSessionTrameLive(sessionId, onLiveMessage);

  const questionActuelle = nextQuestionQuery.data?.question ?? null;
  const terminee = nextQuestionQuery.data?.terminee ?? false;
  const villeConnue = clientQuery.data?.adresse?.ville;
  const valeurParDefaut =
    questionActuelle?.id === "ville" && typeof villeConnue === "string" ? villeConnue : undefined;
  const recommandations = recommandationsQuery.data ?? [];
  const meilleureRecommandation = recommandations[0];

  const onRepondre = (valeur: unknown) => {
    if (!questionActuelle) return;
    const question = questionActuelle;
    repondreMutation.mutate(
      { question_id: question.id, valeur },
      {
        onSuccess: () => setHistorique((h) => [...h, { question, valeur }]),
        onError: () => toast.error("Impossible d'enregistrer la réponse."),
      }
    );
  };

  // "Retour arrière libre" (§1.2) : corriger une réponse déjà donnée. Le
  // backend accepte de réécrire question_id → nouvelle valeur ; les
  // questions déjà résolues qui en dépendaient ne sont pas rejouées
  // automatiquement (limitation connue, voir ProgressTree.tsx).
  const onCorriger = (question: Question, valeur: unknown) => {
    repondreMutation.mutate(
      { question_id: question.id, valeur },
      {
        onSuccess: () => setHistorique((h) => h.map((e) => (e.question.id === question.id ? { question, valeur } : e))),
        onError: () => toast.error("Impossible de corriger la réponse."),
      }
    );
  };

  const onTerminer = () => {
    finaliserMutation.mutate(undefined, {
      onSuccess: (session) => {
        setSuggestionsCrossSell(session.suggestions_cross_sell);
        setSyntheseOpen(true);
      },
      onError: () => toast.error("Impossible de finaliser la session."),
    });
  };

  if (sessionQuery.isLoading || nextQuestionQuery.isLoading) {
    return <Skeleton className="h-96 w-full" />;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-end gap-2">
        {!presentation && (
          <>
            <FactureUploadPanel sessionId={sessionId} />
            <CopilotSidebar sessionId={sessionId} />
          </>
        )}
        <Button variant="ghost" size="sm" onClick={partagerAvecLeClient} disabled={creerLienPartage.isPending}>
          {creerLienPartage.isPending ? "Génération du lien…" : "Partager avec le client"}
        </Button>
      </div>
      <TrameLayout
        presentation={presentation}
        onTogglePresentation={() => setPresentation((p) => !p)}
        left={
          <ProgressTree
            historique={historique}
            questionActuelle={questionActuelle?.label ?? null}
            terminee={terminee}
            onCorriger={onCorriger}
          />
        }
        center={
          <>
            {!presentation && meilleureRecommandation && <AlertesBanner alertes={meilleureRecommandation.alertes} />}
            {questionActuelle ? (
              <QuestionCard
                question={questionActuelle}
                questionsRestantesEstimees={nextQuestionQuery.data?.questions_restantes_estimees ?? 0}
                presentation={presentation}
                onRepondre={onRepondre}
                isSubmitting={repondreMutation.isPending}
                valeurParDefaut={valeurParDefaut}
              />
            ) : (
              <div className="mx-auto flex max-w-xl flex-col items-center gap-3 text-center">
                <h2 className="text-2xl font-semibold">Trame terminée</h2>
                <p className="text-sm text-muted-foreground">
                  Le moteur a assez d&apos;informations pour produire un audit complet.
                </p>
                <Button size="lg" onClick={onTerminer} disabled={finaliserMutation.isPending}>
                  {finaliserMutation.isPending ? "Finalisation…" : "Voir la synthèse"}
                </Button>
              </div>
            )}
          </>
        }
      />

      <SyntheseModal
        open={syntheseOpen}
        onOpenChange={setSyntheseOpen}
        sessionId={sessionId}
        clientId={clientId}
        recommandations={recommandations}
        suggestionsCrossSell={suggestionsCrossSell}
      />
    </div>
  );
}
