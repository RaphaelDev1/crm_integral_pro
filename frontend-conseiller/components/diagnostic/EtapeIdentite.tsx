"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Label } from "@/components/ui/label";
import { Champ } from "@/components/diagnostic/champs";
import { clientsResource } from "@/lib/hooks/useClients";
import type { DiagnosticDispatch, DiagnosticState } from "@/lib/hooks/useDiagnosticWizard";
import { prospectsResource } from "@/lib/hooks/useProspects";
import type { Client, Prospect } from "@/lib/types";
import { cn } from "@/lib/utils";

interface EtapeIdentiteProps {
  state: DiagnosticState;
  dispatch: DiagnosticDispatch;
}

function nomAffiche(entite: { prenom: string | null; nom: string | null; telephone?: string | null }) {
  return `${entite.prenom ?? ""} ${entite.nom ?? ""}`.trim() || "(sans nom)";
}


// Étape 2 du diagnostic (plan Phase 6.4) — reprise d'un prospect/client
// existant (autocomplete) ou création d'une fiche inline.
export function EtapeIdentite({ state, dispatch }: EtapeIdentiteProps) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const prospectsQuery = prospectsResource.useList();
  const clientsQuery = clientsResource.useList();

  function choisirNouveau() {
    dispatch({ type: "SET_IDENTITE", values: { mode: "nouveau", entiteType: null, entiteId: null } });
  }

  function choisirExistant(type: "prospect" | "client", entite: Prospect | Client) {
    dispatch({
      type: "SET_IDENTITE",
      values: {
        mode: "existant",
        entiteType: type,
        entiteId: entite.id,
        typeClient: entite.type_client || "Particulier",
        prenom: entite.prenom ?? "",
        nom: entite.nom ?? "",
        telephone: entite.telephone ?? "",
        email: entite.email ?? "",
        codePostal: entite.code_postal ?? "",
        ville: entite.ville ?? "",
        adresse: entite.adresse ?? "",
      },
    });
    setPickerOpen(false);
  }

  const identiteChoisie = state.identite.mode === "existant" && state.identite.entiteId !== null;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Coordonnées du client</h2>
        <p className="text-sm text-muted-foreground">
          Reprenez un prospect ou client existant, ou créez une nouvelle fiche.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" variant="outline" onClick={() => setPickerOpen(true)}>
          Reprendre un prospect/client existant…
        </Button>
        {state.identite.mode === "nouveau" ? (
          <span className="text-sm text-muted-foreground">Nouvelle fiche</span>
        ) : (
          <span className="flex items-center gap-2 text-sm">
            <span className="rounded-full bg-primary/10 px-2 py-0.5 text-primary">
              {state.identite.entiteType === "client" ? "Client" : "Prospect"} #{state.identite.entiteId}
            </span>
            <button type="button" className="text-muted-foreground underline" onClick={choisirNouveau}>
              Changer / créer une nouvelle fiche
            </button>
          </span>
        )}
      </div>

      <CommandDialog open={pickerOpen} onOpenChange={setPickerOpen}>
        <CommandInput placeholder="Rechercher un prospect ou client…" />
        <CommandList>
          <CommandEmpty>Aucun résultat.</CommandEmpty>
          <CommandGroup heading="Prospects">
            {(prospectsQuery.data ?? []).map((prospect) => (
              <CommandItem
                key={`prospect-${prospect.id}`}
                value={`${nomAffiche(prospect)} ${prospect.telephone ?? ""} ${prospect.email ?? ""}`}
                onSelect={() => choisirExistant("prospect", prospect)}
              >
                {nomAffiche(prospect)} — {prospect.telephone || prospect.email || `#${prospect.id}`}
              </CommandItem>
            ))}
          </CommandGroup>
          <CommandGroup heading="Clients">
            {(clientsQuery.data ?? []).map((client) => (
              <CommandItem
                key={`client-${client.id}`}
                value={`${nomAffiche(client)} ${client.telephone ?? ""} ${client.email ?? ""}`}
                onSelect={() => choisirExistant("client", client)}
              >
                {nomAffiche(client)} — {client.telephone || client.email || `#${client.id}`}
              </CommandItem>
            ))}
          </CommandGroup>
        </CommandList>
      </CommandDialog>

      <div className="space-y-2">
        <Label>Type de client</Label>
        <div className="flex gap-2">
          {["Particulier", "Professionnel"].map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => dispatch({ type: "SET_IDENTITE", values: { typeClient: option } })}
              className={cn(
                "rounded-full border px-3 py-1.5 text-sm transition-colors",
                state.identite.typeClient === option
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-input bg-background hover:bg-accent"
              )}
            >
              {option}
            </button>
          ))}
        </div>
      </div>

      <fieldset disabled={identiteChoisie} className={cn("grid grid-cols-2 gap-4", identiteChoisie && "opacity-60")}>
        <Champ
          label="Prénom *"
          value={state.identite.prenom}
          onChange={(e) => dispatch({ type: "SET_IDENTITE", values: { prenom: e.target.value } })}
        />
        <Champ
          label="Nom *"
          value={state.identite.nom}
          onChange={(e) => dispatch({ type: "SET_IDENTITE", values: { nom: e.target.value } })}
        />
        <Champ
          label="Téléphone"
          value={state.identite.telephone}
          onChange={(e) => dispatch({ type: "SET_IDENTITE", values: { telephone: e.target.value } })}
        />
        <Champ
          label="Email"
          type="email"
          value={state.identite.email}
          onChange={(e) => dispatch({ type: "SET_IDENTITE", values: { email: e.target.value } })}
        />
        <Champ
          label="Code postal"
          value={state.identite.codePostal}
          onChange={(e) => dispatch({ type: "SET_IDENTITE", values: { codePostal: e.target.value } })}
        />
        <Champ
          label="Ville"
          value={state.identite.ville}
          onChange={(e) => dispatch({ type: "SET_IDENTITE", values: { ville: e.target.value } })}
        />
        <Champ
          label="Adresse"
          className="col-span-2"
          value={state.identite.adresse}
          onChange={(e) => dispatch({ type: "SET_IDENTITE", values: { adresse: e.target.value } })}
        />
      </fieldset>
      {identiteChoisie && (
        <p className="text-xs text-muted-foreground">
          Fiche reprise depuis un {state.identite.entiteType === "client" ? "client" : "prospect"} existant — les
          champs ne sont pas modifiables ici, éditez sa fiche directement si besoin.
        </p>
      )}
    </div>
  );
}
