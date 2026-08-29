"use client";

import { useState } from "react";
import { Loader2, MessageCircleQuestion, Sparkles, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useCopilot } from "@/lib/hooks/useCopilot";
import type { CopilotMode } from "@/lib/types-ia-conseil";

const MODES: { mode: CopilotMode; label: string }[] = [
  { mode: "suggestion", label: "Prochaine question" },
  { mode: "incoherence", label: "Vérifier une incohérence" },
  { mode: "reformulation", label: "Aide à la reformulation" },
];

interface CopilotSidebarProps {
  sessionId: string;
}

// Sidebar rétractable "IA Assistante" (§3.2) — copilote conseiller en
// streaming SSE pendant la session. Backoffice pur : à monter uniquement
// hors mode présentation côté page (jamais visible côté client).
export function CopilotSidebar({ sessionId }: CopilotSidebarProps) {
  const [ouvert, setOuvert] = useState(false);
  const [message, setMessage] = useState("");
  const { streaming, texte, erreur, demander } = useCopilot(sessionId);

  if (!ouvert) {
    return (
      <Button variant="outline" size="sm" className="gap-1.5" onClick={() => setOuvert(true)}>
        <Sparkles className="h-4 w-4" />
        IA Assistante
      </Button>
    );
  }

  return (
    <div className="w-full space-y-3 rounded-md border bg-card p-3 shadow-sm lg:w-80">
      <div className="flex items-center justify-between">
        <p className="flex items-center gap-1.5 text-sm font-medium">
          <Sparkles className="h-4 w-4" />
          IA Assistante
        </p>
        <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => setOuvert(false)}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {MODES.map(({ mode, label }) => (
          <Button
            key={mode}
            variant="secondary"
            size="sm"
            disabled={streaming || (mode === "reformulation" && message.trim().length === 0)}
            onClick={() => demander(mode, message.trim() || undefined)}
          >
            {label}
          </Button>
        ))}
      </div>

      <Textarea
        placeholder="Objection ou situation à reformuler (pour « Aide à la reformulation »)…"
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        rows={2}
        className="text-sm"
      />

      <div className="min-h-16 rounded-md bg-muted/50 p-2.5 text-sm">
        {streaming && !texte && !erreur && (
          <span className="flex items-center gap-1.5 text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Réflexion…
          </span>
        )}
        {erreur && <span className="text-destructive">{erreur}</span>}
        {texte && <p className="whitespace-pre-wrap">{texte}</p>}
        {!streaming && !texte && !erreur && (
          <span className="flex items-center gap-1.5 text-muted-foreground">
            <MessageCircleQuestion className="h-3.5 w-3.5" />
            Choisissez une aide ci-dessus.
          </span>
        )}
      </div>
    </div>
  );
}
