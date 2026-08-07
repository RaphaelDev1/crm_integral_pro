"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Champ, ChampSelect } from "@/components/diagnostic/champs";
import { EFFECTIF_OPTIONS } from "@/lib/diagnosticConstants";
import { clientsResource } from "@/lib/hooks/useClients";
import type { DiagnosticDispatch, DiagnosticState, IdentiteState } from "@/lib/hooks/useDiagnosticWizard";
import { useCommunesParCodePostal } from "@/lib/hooks/useGeo";
import {
  prospectsResource,
  useEnvoyerLienDocumentsProspect,
  useGenererLienDocumentsProspect,
} from "@/lib/hooks/useProspects";
import type { Client, Prospect } from "@/lib/types";
import { cn } from "@/lib/utils";

interface EtapeIdentiteProps {
  state: DiagnosticState;
  dispatch: DiagnosticDispatch;
}

function nomAffiche(entite: { prenom: string | null; nom: string | null; telephone?: string | null }) {
  return `${entite.prenom ?? ""} ${entite.nom ?? ""}`.trim() || "(sans nom)";
}

// Mapping fiche existante (Prospect ou Client) -> champs du wizard — extrait
// pour être réutilisé à la fois par la reprise via CommandDialog ci-dessous et
// par le pré-remplissage depuis les boutons "Nouveau diagnostic" des fiches
// prospect/client (voir app/(conseiller)/diagnostic/page.tsx).
export function valeursIdentiteDepuisEntite(
  type: "prospect" | "client",
  entite: Prospect | Client
): Partial<IdentiteState> {
  return {
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
    raisonSociale: entite.raison_sociale ?? "",
    effectif: entite.effectif ?? "",
  };
}


// Étape 2 du diagnostic (plan Phase 6.4) — reprise d'un prospect/client
// existant (autocomplete) ou création d'une fiche inline.
export function EtapeIdentite({ state, dispatch }: EtapeIdentiteProps) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const prospectsQuery = prospectsResource.useList();
  const clientsQuery = clientsResource.useList();
  const majProspect = prospectsResource.useUpdate();
  const majClient = clientsResource.useUpdate();

  function choisirNouveau() {
    dispatch({ type: "SET_IDENTITE", values: { mode: "nouveau", entiteType: null, entiteId: null } });
  }

  function choisirExistant(type: "prospect" | "client", entite: Prospect | Client) {
    dispatch({ type: "SET_IDENTITE", values: valeursIdentiteDepuisEntite(type, entite) });
    setPickerOpen(false);
  }

  const identiteChoisie = state.identite.mode === "existant" && state.identite.entiteId !== null;
  const estProfessionnel = state.identite.typeClient === "Professionnel";

  // Déverrouillage temporaire des champs d'une fiche reprise, pour corriger
  // une erreur de saisie sans devoir aller sur la fiche prospect/client
  // directement (voir demande produit — l'ancien comportement bloquait toute
  // correction dès qu'une fiche existante était sélectionnée à l'étape 2).
  const [correctionEnCours, setCorrectionEnCours] = useState(false);
  const champsVerrouilles = identiteChoisie && !correctionEnCours;

  function handleAnnulerCorrection() {
    if (state.identite.entiteType && state.identite.entiteId != null) {
      const source =
        state.identite.entiteType === "prospect"
          ? (prospectsQuery.data ?? []).find((p) => p.id === state.identite.entiteId)
          : (clientsQuery.data ?? []).find((c) => c.id === state.identite.entiteId);
      if (source) {
        dispatch({ type: "SET_IDENTITE", values: valeursIdentiteDepuisEntite(state.identite.entiteType, source) });
      }
    }
    setCorrectionEnCours(false);
  }

  function handleEnregistrerCorrection() {
    if (!state.identite.entiteType || state.identite.entiteId == null) return;
    const valeurs = {
      prenom: state.identite.prenom,
      nom: state.identite.nom,
      telephone: state.identite.telephone,
      email: state.identite.email,
      code_postal: state.identite.codePostal,
      ville: state.identite.ville,
      adresse: state.identite.adresse,
      raison_sociale: state.identite.raisonSociale || undefined,
      effectif: state.identite.effectif || undefined,
    };
    const mutation = state.identite.entiteType === "prospect" ? majProspect : majClient;
    mutation.mutate(
      { id: state.identite.entiteId, values: valeurs },
      {
        onSuccess: () => {
          toast.success("Informations corrigées.");
          setCorrectionEnCours(false);
        },
        onError: () => toast.error("Échec de l'enregistrement de la correction."),
      }
    );
  }

  // Auto-complétion ville à partir du code postal — ne se déclenche que si la
  // ville n'a pas déjà été saisie manuellement (évite d'écraser une correction
  // du conseiller) et jamais sur une fiche reprise (déjà renseignée).
  const communesQuery = useCommunesParCodePostal(state.identite.codePostal);
  useEffect(() => {
    if (identiteChoisie) return;
    const villes = communesQuery.data?.villes ?? [];
    if (villes.length === 1 && state.identite.ville !== villes[0]) {
      dispatch({ type: "SET_IDENTITE", values: { ville: villes[0] } });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [communesQuery.data]);
  const suggestionsVille = (communesQuery.data?.villes ?? []).length > 1 ? communesQuery.data!.villes : [];

  const [lienOpen, setLienOpen] = useState(false);
  const [lienUrl, setLienUrl] = useState<string | null>(null);
  const lienMutation = useGenererLienDocumentsProspect();
  const envoyerLienMutation = useEnvoyerLienDocumentsProspect();
  const peutEnvoyerLien = state.identite.mode === "existant" && state.identite.entiteType === "prospect";

  function handleEnvoyerLien() {
    if (!state.identite.entiteId) return;
    lienMutation.mutate(state.identite.entiteId, {
      onSuccess: (data) => {
        setLienUrl(data.url);
        setLienOpen(true);
      },
    });
  }

  function handleEnvoyerParEmail() {
    if (!state.identite.entiteId) return;
    envoyerLienMutation.mutate(
      { prospectId: state.identite.entiteId, canal: "email" },
      {
        onSuccess: (data) => {
          toast.success(data.email_envoye ? "Lien envoyé par email." : "Échec de l'envoi de l'email.");
        },
      }
    );
  }

  async function handleCopierLien() {
    if (!lienUrl) return;
    await navigator.clipboard.writeText(lienUrl);
    toast.success("Lien copié.");
  }

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
                value={`${prospect.ref ?? ""} ${nomAffiche(prospect)} ${prospect.telephone ?? ""} ${prospect.email ?? ""}`}
                onSelect={() => choisirExistant("prospect", prospect)}
              >
                {prospect.ref ? `${prospect.ref} · ` : ""}
                {nomAffiche(prospect)} — {prospect.telephone || prospect.email || `#${prospect.id}`}
              </CommandItem>
            ))}
          </CommandGroup>
          <CommandGroup heading="Clients">
            {(clientsQuery.data ?? []).map((client) => (
              <CommandItem
                key={`client-${client.id}`}
                value={`${client.ref ?? ""} ${nomAffiche(client)} ${client.telephone ?? ""} ${client.email ?? ""}`}
                onSelect={() => choisirExistant("client", client)}
              >
                {client.ref ? `${client.ref} · ` : ""}
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

      <fieldset disabled={champsVerrouilles} className={cn("grid grid-cols-2 gap-4", champsVerrouilles && "opacity-60")}>
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
          label="Téléphone *"
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
          label="Code postal *"
          value={state.identite.codePostal}
          onChange={(e) => dispatch({ type: "SET_IDENTITE", values: { codePostal: e.target.value } })}
        />
        <div className="space-y-2">
          <Champ
            label="Ville *"
            value={state.identite.ville}
            onChange={(e) => dispatch({ type: "SET_IDENTITE", values: { ville: e.target.value } })}
          />
          {suggestionsVille.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {suggestionsVille.map((ville) => (
                <button
                  key={ville}
                  type="button"
                  onClick={() => dispatch({ type: "SET_IDENTITE", values: { ville } })}
                  className="rounded-full border border-input px-2 py-0.5 text-xs hover:bg-accent"
                >
                  {ville}
                </button>
              ))}
            </div>
          )}
        </div>
        <Champ
          label="Adresse"
          className="col-span-2"
          value={state.identite.adresse}
          onChange={(e) => dispatch({ type: "SET_IDENTITE", values: { adresse: e.target.value } })}
        />
        {estProfessionnel && (
          <>
            <Champ
              label="Nom de l'entreprise *"
              value={state.identite.raisonSociale ?? ""}
              onChange={(e) => dispatch({ type: "SET_IDENTITE", values: { raisonSociale: e.target.value } })}
            />
            <ChampSelect
              label="Nombre d'employés *"
              value={state.identite.effectif ?? ""}
              onChange={(value) => dispatch({ type: "SET_IDENTITE", values: { effectif: value } })}
              options={EFFECTIF_OPTIONS}
            />
          </>
        )}
      </fieldset>
      {identiteChoisie && !correctionEnCours && (
        <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
          <p>
            Fiche reprise depuis un {state.identite.entiteType === "client" ? "client" : "prospect"} existant — les
            champs sont verrouillés par défaut.
          </p>
          <Button type="button" variant="outline" size="sm" onClick={() => setCorrectionEnCours(true)}>
            Corriger ces informations
          </Button>
        </div>
      )}
      {identiteChoisie && correctionEnCours && (
        <div className="flex items-center justify-between gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs">
          <p className="text-amber-800">
            Champs déverrouillés — corrigez une erreur de saisie puis enregistrez, ou annulez pour revenir aux
            informations d&apos;origine.
          </p>
          <div className="flex shrink-0 gap-2">
            <Button type="button" variant="ghost" size="sm" onClick={handleAnnulerCorrection}>
              Annuler
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={handleEnregistrerCorrection}
              disabled={majProspect.isPending || majClient.isPending}
            >
              Enregistrer les corrections
            </Button>
          </div>
        </div>
      )}

      {peutEnvoyerLien && (
        <div className="rounded-md border p-4 space-y-2">
          <p className="text-sm font-medium">Collecte facture / test de débit</p>
          <p className="text-xs text-muted-foreground">
            Envoyez un lien personnel au prospect pour qu&apos;il transmette lui-même sa facture actuelle et/ou son
            test de débit, avant même la fin du diagnostic.
          </p>
          <Button type="button" variant="outline" onClick={handleEnvoyerLien} disabled={lienMutation.isPending}>
            Envoyer lien collecte docs / facture
          </Button>
        </div>
      )}

      <Dialog open={lienOpen} onOpenChange={setLienOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Lien de collecte de documents</DialogTitle>
          </DialogHeader>
          <div className="flex gap-2">
            <Input readOnly value={lienUrl ?? ""} />
            <Button type="button" onClick={handleCopierLien}>
              Copier
            </Button>
          </div>
          <Button type="button" variant="outline" onClick={handleEnvoyerParEmail} disabled={envoyerLienMutation.isPending}>
            {envoyerLienMutation.isPending ? "Envoi…" : "Envoyer par email"}
          </Button>
        </DialogContent>
      </Dialog>
    </div>
  );
}
