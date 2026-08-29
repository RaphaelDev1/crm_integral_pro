"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useAdresseAutocomplete, type AdresseResultat } from "@/lib/hooks/useAdresseAutocomplete";
import type { Question } from "@/lib/types-ia-conseil";

interface AnswerInputProps {
  question: Question;
  onSubmit: (valeur: unknown) => void;
  isSubmitting?: boolean;
  // Pré-remplissage (ex. ville déjà connue via la fiche prospect/client
  // reprise à la création du client IA Conseil, voir app/(conseiller)/
  // ia-conseil/clients/[id]/trame/[sessionId]/page.tsx) — reste éditable.
  valeurParDefaut?: string;
}

// Un input typé par question.type — pas de react-hook-form ici : chaque
// question est indépendante et éphémère (une seule à l'écran à la fois, voir
// TrameLayout), un simple état local suffit. `key={question.id}` côté
// parent garantit un input neuf à chaque nouvelle question.
export function AnswerInput({ question, onSubmit, isSubmitting, valeurParDefaut }: AnswerInputProps) {
  if (question.type === "boolean") return <AnswerInputBoolean onSubmit={onSubmit} isSubmitting={isSubmitting} />;
  if (question.type === "select") return <AnswerInputSelect question={question} onSubmit={onSubmit} isSubmitting={isSubmitting} />;
  if (question.type === "adresse") return <AnswerInputAdresse onSubmit={onSubmit} isSubmitting={isSubmitting} />;
  return (
    <AnswerInputTexte question={question} onSubmit={onSubmit} isSubmitting={isSubmitting} valeurParDefaut={valeurParDefaut} />
  );
}

function AnswerInputBoolean({ onSubmit, isSubmitting }: Pick<AnswerInputProps, "onSubmit" | "isSubmitting">) {
  return (
    <div className="flex gap-3">
      <Button size="lg" disabled={isSubmitting} onClick={() => onSubmit(true)}>
        Oui
      </Button>
      <Button size="lg" variant="outline" disabled={isSubmitting} onClick={() => onSubmit(false)}>
        Non
      </Button>
    </div>
  );
}

function AnswerInputSelect({ question, onSubmit, isSubmitting }: AnswerInputProps) {
  const [valeur, setValeur] = useState<string>("");
  const options = question.options ?? [];

  // options_ref sans options résolues côté trame (ex. "operateurs_mobiles") :
  // pas de référentiel exposé par l'API pour l'instant — repli en saisie
  // libre plutôt que de bloquer le conseiller.
  if (options.length === 0) {
    return <AnswerInputTexte question={question} onSubmit={onSubmit} isSubmitting={isSubmitting} />;
  }

  return (
    <div className="flex flex-col gap-3 sm:flex-row">
      <Select value={valeur} onValueChange={setValeur}>
        <SelectTrigger className="h-11 text-base sm:w-72">
          <SelectValue placeholder="Choisir une réponse…" />
        </SelectTrigger>
        <SelectContent>
          {options.map((option) => (
            <SelectItem key={option} value={option}>
              {option}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Button size="lg" disabled={!valeur || isSubmitting} onClick={() => onSubmit(valeur)}>
        Suivant
      </Button>
    </div>
  );
}

function AnswerInputTexte({ question, onSubmit, isSubmitting, valeurParDefaut }: AnswerInputProps) {
  const [valeur, setValeur] = useState<string>(valeurParDefaut ?? "");
  const estNumerique = question.type === "number";

  const soumettre = () => {
    if (!valeur.trim()) return;
    onSubmit(estNumerique ? Number(valeur) : valeur);
  };

  return (
    <div className="flex flex-col gap-3 sm:flex-row">
      <div className="flex items-center gap-2 sm:w-72">
        <Input
          type={estNumerique ? "number" : "text"}
          inputMode={estNumerique ? "decimal" : undefined}
          min={question.min}
          max={question.max}
          className="h-11 text-base"
          value={valeur}
          autoFocus
          onChange={(e) => setValeur(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && soumettre()}
        />
        {question.unit && <span className="text-sm text-muted-foreground">{question.unit}</span>}
      </div>
      <Button size="lg" disabled={!valeur.trim() || isSubmitting} onClick={soumettre}>
        Suivant
      </Button>
    </div>
  );
}

function AnswerInputAdresse({ onSubmit, isSubmitting }: Pick<AnswerInputProps, "onSubmit" | "isSubmitting">) {
  const [recherche, setRecherche] = useState("");
  const { data, isFetching } = useAdresseAutocomplete(recherche);
  const resultats = data?.resultats ?? [];

  const choisir = (resultat: AdresseResultat) => onSubmit(resultat);

  return (
    <div className="relative sm:w-96">
      <Input
        className="h-11 text-base"
        placeholder="Commencez à taper l'adresse…"
        value={recherche}
        autoFocus
        onChange={(e) => setRecherche(e.target.value)}
        disabled={isSubmitting}
      />
      {isFetching && <p className="mt-1 text-xs text-muted-foreground">Recherche…</p>}
      {resultats.length > 0 && (
        <ul className="absolute z-10 mt-1 w-full rounded-md border bg-popover shadow-md">
          {resultats.map((resultat) => (
            <li key={resultat.label}>
              <button
                type="button"
                className="w-full px-3 py-2 text-left text-sm hover:bg-accent"
                onClick={() => choisir(resultat)}
              >
                {resultat.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
