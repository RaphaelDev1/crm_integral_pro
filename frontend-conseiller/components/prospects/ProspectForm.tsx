"use client";

import { useEffect, useState } from "react";
import type { UseFormReturn } from "react-hook-form";

import { AppForm } from "@/components/forms/AppForm";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { DialogFooter } from "@/components/ui/dialog";
import { FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  combinerCreneauRappel,
  decomposerCreneauRappel,
  DOMAINES_EMAIL_COURANTS,
  JOURS_RAPPEL_OPTIONS,
  OBJECTIFS_PRINCIPAUX_OPTIONS,
  PLAGES_HORAIRES_RAPPEL_OPTIONS,
  TRANCHES_AGE_OPTIONS,
} from "@/lib/diagnosticConstants";
import { useAdresseAutocomplete } from "@/lib/hooks/useAdresseAutocomplete";
import { useCommunesParCodePostal } from "@/lib/hooks/useGeo";
import {
  prospectCreateSchema,
  prospectUpdateSchema,
  type ProspectCreateInput,
  type ProspectUpdateInput,
} from "@/lib/schemas/prospect";
import type { Prospect } from "@/lib/types";

// Sous-ensemble de champs exposé au formulaire, même logique que
// components/clients/ClientForm.tsx qui n'expose pas non plus tous les
// champs du type complet.
type ProspectFormValues = ProspectCreateInput | ProspectUpdateInput;

// Raisons de relance proposées au conseiller (le champ reste une string libre
// côté backend — "À relancer" est conservé en premier pour les fiches déjà
// existantes qui portent encore la valeur par défaut historique).
const STATUTS_PROSPECT = ["À relancer", "Fin de contrat", "Relance dossier", "Refusé", "Autre"];

// Code postal -> ville (menu déroulant si plusieurs communes) + autocomplete
// d'adresse (menu déroulant de suggestions) — même logique/hooks que
// components/diagnostic/EtapeIdentite.tsx et components/ia-conseil/AnswerInput.tsx,
// extraite en sous-composant car les hooks doivent s'exécuter dans un vrai
// composant React (pas dans la render-prop `children` de AppForm).
function AdresseFields({ form }: { form: UseFormReturn<ProspectFormValues> }) {
  const codePostal = form.watch("code_postal") ?? "";
  const adresse = form.watch("adresse") ?? "";
  const communesQuery = useCommunesParCodePostal(codePostal);
  const villesTrouvees = communesQuery.data?.villes ?? [];
  const adresseQuery = useAdresseAutocomplete(adresse);
  const suggestionsAdresse = adresseQuery.data?.resultats ?? [];

  useEffect(() => {
    if (villesTrouvees.length === 1 && form.getValues("ville") !== villesTrouvees[0]) {
      form.setValue("ville", villesTrouvees[0], { shouldDirty: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [villesTrouvees.join("|")]);

  function choisirAdresse(resultat: { label: string | null; code_postal: string | null; ville: string | null }) {
    if (resultat.label) form.setValue("adresse", resultat.label, { shouldDirty: true });
    if (resultat.code_postal) form.setValue("code_postal", resultat.code_postal, { shouldDirty: true });
    if (resultat.ville) form.setValue("ville", resultat.ville, { shouldDirty: true });
  }

  return (
    <div className="grid grid-cols-3 gap-4">
      <FormField
        control={form.control}
        name="code_postal"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Code postal *</FormLabel>
            <FormControl>
              <Input {...field} />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />
      <FormField
        control={form.control}
        name="ville"
        render={({ field }) =>
          villesTrouvees.length > 1 ? (
            <FormItem>
              <FormLabel>Ville *</FormLabel>
              <Select onValueChange={field.onChange} value={field.value || undefined}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="Sélectionner une ville…" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {villesTrouvees.map((ville) => (
                    <SelectItem key={ville} value={ville}>
                      {ville}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">Plusieurs villes correspondent à ce code postal.</p>
              <FormMessage />
            </FormItem>
          ) : (
            <FormItem>
              <FormLabel>Ville *</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )
        }
      />
      <FormField
        control={form.control}
        name="adresse"
        render={({ field }) => (
          <FormItem className="relative">
            <FormLabel>Adresse</FormLabel>
            <FormControl>
              <Input placeholder="N° et rue" autoComplete="off" {...field} />
            </FormControl>
            {suggestionsAdresse.length > 0 && (
              <ul className="absolute z-10 mt-1 w-full rounded-md border bg-popover shadow-md">
                {suggestionsAdresse.map((resultat) => (
                  <li key={resultat.label}>
                    <button
                      type="button"
                      className="w-full px-3 py-2 text-left text-sm hover:bg-accent"
                      onClick={() => choisirAdresse(resultat)}
                    >
                      {resultat.label}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <FormMessage />
          </FormItem>
        )}
      />
    </div>
  );
}

// Suggestions de domaines email (@gmail.com, @yahoo.fr…) une fois le "@"
// tapé, pour éviter de retaper la fin de l'adresse — filtrées sur ce qui est
// déjà saisi après le "@". Le menu se ferme dès qu'un domaine est choisi.
function EmailField({ form }: { form: UseFormReturn<ProspectFormValues> }) {
  const [suggestionsFermees, setSuggestionsFermees] = useState(false);
  const email = form.watch("email") ?? "";
  const indexArobase = email.indexOf("@");
  const partieDomaine = indexArobase >= 0 ? email.slice(indexArobase + 1) : null;
  const suggestions =
    partieDomaine != null
      ? DOMAINES_EMAIL_COURANTS.filter((domaine) => domaine.startsWith(partieDomaine.toLowerCase()) && domaine !== partieDomaine.toLowerCase())
      : [];
  const afficherSuggestions = !suggestionsFermees && suggestions.length > 0;

  function choisirDomaine(domaine: string) {
    form.setValue("email", `${email.slice(0, indexArobase)}@${domaine}`, { shouldDirty: true });
    setSuggestionsFermees(true);
  }

  return (
    <FormField
      control={form.control}
      name="email"
      render={({ field }) => (
        <FormItem className="relative">
          <FormLabel>Email</FormLabel>
          <FormControl>
            <Input
              type="email"
              autoComplete="off"
              {...field}
              onChange={(e) => {
                setSuggestionsFermees(false);
                field.onChange(e);
              }}
            />
          </FormControl>
          {afficherSuggestions && (
            <ul className="absolute z-10 mt-1 w-full rounded-md border bg-popover shadow-md">
              {suggestions.map((domaine) => (
                <li key={domaine}>
                  <button
                    type="button"
                    className="w-full px-3 py-2 text-left text-sm hover:bg-accent"
                    onClick={() => choisirDomaine(domaine)}
                  >
                    {email.slice(0, indexArobase)}@{domaine}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <FormMessage />
        </FormItem>
      )}
    />
  );
}

interface ProspectFormProps {
  mode: "create" | "edit";
  defaultValues: ProspectFormValues;
  onSubmit: (values: ProspectFormValues) => void | Promise<void>;
  submitError?: unknown;
  submitLabel: string;
  isSubmitting?: boolean;
}

export function prospectToFormValues(prospect: Prospect): ProspectUpdateInput {
  return {
    ref: prospect.ref ?? "",
    prenom: prospect.prenom ?? "",
    nom: prospect.nom ?? "",
    telephone: prospect.telephone ?? "",
    email: prospect.email ?? "",
    code_postal: prospect.code_postal ?? "",
    ville: prospect.ville ?? "",
    adresse: prospect.adresse ?? "",
    origine: prospect.origine ?? "",
    objectif_principal: prospect.objectif_principal ?? "",
    statut: prospect.statut ?? "",
    date_relance: prospect.date_relance ?? "",
    plage_horaire_rappel: prospect.plage_horaire_rappel ?? "",
    notes: prospect.notes ?? "",
    motif_refus: prospect.motif_refus ?? "",
    age: prospect.age ?? undefined,
    tranche_age: prospect.tranche_age ?? "",
    consentement_rgpd: prospect.consentement_rgpd ?? false,
    consentement_demarchage: prospect.consentement_demarchage ?? false,
  };
}

export function ProspectForm({
  mode,
  defaultValues,
  onSubmit,
  submitError,
  submitLabel,
  isSubmitting,
}: ProspectFormProps) {
  const schema = mode === "create" ? prospectCreateSchema : prospectUpdateSchema;

  return (
    <AppForm schema={schema} defaultValues={defaultValues} onSubmit={onSubmit} submitError={submitError} className="space-y-4">
      {(form) => (
        <>
          <p className="text-xs text-muted-foreground">
            * Champs requis pour pouvoir lancer un nouveau diagnostic sur ce prospect.
          </p>
          <FormField
            control={form.control}
            name="ref"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Référence</FormLabel>
                <FormControl>
                  <Input
                    {...field}
                    disabled
                    readOnly
                    placeholder={mode === "create" ? "Générée automatiquement à la création" : undefined}
                  />
                </FormControl>
                <p className="text-xs text-muted-foreground">Générée automatiquement, non modifiable.</p>
                <FormMessage />
              </FormItem>
            )}
          />
          <div className="grid grid-cols-2 gap-4">
            <FormField
              control={form.control}
              name="prenom"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Prénom *</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="nom"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Nom *</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <FormField
              control={form.control}
              name="telephone"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Téléphone *</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <EmailField form={form} />
          </div>
          <AdresseFields form={form} />
          <FormField
            control={form.control}
            name="objectif_principal"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Objectif de la demande</FormLabel>
                <p className="text-xs text-muted-foreground">
                  Renseigné d'office s'il vient de la landing /economiser — indique si sa démarche
                  est motivée par une raison financière ou un gain de temps.
                </p>
                <Select onValueChange={field.onChange} value={field.value || undefined}>
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue placeholder="Sélectionner…" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {OBJECTIFS_PRINCIPAUX_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />
          <div className="grid grid-cols-2 gap-4">
            <FormField
              control={form.control}
              name="statut"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Statut</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value || undefined}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Sélectionner…" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {STATUTS_PROSPECT.map((statut) => (
                        <SelectItem key={statut} value={statut}>
                          {statut}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            {form.watch("statut") === "Refusé" && (
              <FormField
                control={form.control}
                name="motif_refus"
                render={({ field }) => (
                  <FormItem className="col-span-2">
                    <FormLabel>Motif du refus</FormLabel>
                    <FormControl>
                      <Textarea {...field} rows={3} placeholder="Raisons et motivations données par le client" />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}
            <FormField
              control={form.control}
              name="date_relance"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Date de relance</FormLabel>
                  <FormControl>
                    <Input type="date" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="plage_horaire_rappel"
              render={({ field }) => {
                const { jour, plage } = decomposerCreneauRappel(field.value);
                return (
                  <FormItem className="col-span-2">
                    <FormLabel>Créneau de rappel souhaité</FormLabel>
                    <div className="grid grid-cols-2 gap-2">
                      <Select
                        value={jour || undefined}
                        onValueChange={(valeur) => field.onChange(combinerCreneauRappel(valeur, plage))}
                      >
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Jour" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {JOURS_RAPPEL_OPTIONS.map((option) => (
                            <SelectItem key={option} value={option}>
                              {option}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <Select
                        value={plage || undefined}
                        onValueChange={(valeur) => field.onChange(combinerCreneauRappel(jour, valeur))}
                      >
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Plage horaire" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {PLAGES_HORAIRES_RAPPEL_OPTIONS.map((option) => (
                            <SelectItem key={option} value={option}>
                              {option}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <FormMessage />
                  </FormItem>
                );
              }}
            />
          </div>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Consentements</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="tranche_age"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Tranche d'âge</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value || undefined}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Sélectionner…" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {TRANCHES_AGE_OPTIONS.map((option) => (
                            <SelectItem key={option} value={option}>
                              {option}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <FormField
                control={form.control}
                name="consentement_rgpd"
                render={({ field }) => (
                  <FormItem className="flex items-center gap-2 space-y-0">
                    <FormControl>
                      <Checkbox checked={field.value ?? false} onCheckedChange={field.onChange} />
                    </FormControl>
                    <FormLabel className="!mt-0">Consentement RGPD</FormLabel>
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="consentement_demarchage"
                render={({ field }) => (
                  <FormItem className="flex items-center gap-2 space-y-0">
                    <FormControl>
                      <Checkbox checked={field.value ?? false} onCheckedChange={field.onChange} />
                    </FormControl>
                    <FormLabel className="!mt-0">Consentement démarchage téléphonique</FormLabel>
                  </FormItem>
                )}
              />
            </CardContent>
          </Card>
          <FormField
            control={form.control}
            name="notes"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Notes</FormLabel>
                <FormControl>
                  <Textarea {...field} rows={8} className="min-h-[220px] text-base" />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <DialogFooter>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Enregistrement…" : submitLabel}
            </Button>
          </DialogFooter>
        </>
      )}
    </AppForm>
  );
}
