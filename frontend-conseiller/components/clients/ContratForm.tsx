"use client";

import { AppForm } from "@/components/forms/AppForm";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { DialogFooter } from "@/components/ui/dialog";
import { FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  CONSERVER_NUMERO_OPTIONS,
  NIVEAUX_DEFAUT_TECHNIQUE,
  SATISFACTION_RESEAU,
  TYPE_SIM_OPTIONS,
  VEUT_RESTER_OPTIONS,
} from "@/lib/diagnosticConstants";
import {
  contratCreateSchema,
  contratUpdateSchema,
  type ContratCreateInput,
  type ContratUpdateInput,
} from "@/lib/schemas/contrat";
import type { Contrat } from "@/lib/types";

// Étapes du cycle de vie d'un contrat (miroir de
// src/contrats_engine.py::ETAPES_CONTRAT + le statut terminal "Résilié").
export const STATUTS_CONTRAT = [
  "Documents reçus",
  "Mandat envoyé",
  "Mandat signé",
  "Souscription en cours",
  "Actif",
  "Résilié",
];

// Type de contrat (stocké dans Contrat.categorie) — même vocabulaire que la
// colonne "Type" affichée dans ContratsTab. `value` reste "Forfait box"
// (comparé littéralement côté backend, voir
// backend/routers/portail_public.py::CATEGORIES_CONTRAT_TELECOM) — seul
// `label` (affiché) utilise le vocabulaire "Box internet" demandé par le client.
export const TYPES_CONTRAT = [
  { value: "Forfait mobile", label: "Forfait mobile" },
  { value: "Forfait box", label: "Box internet" },
  { value: "Énergie électricité", label: "Énergie électricité" },
  { value: "Énergie gaz", label: "Énergie gaz" },
  { value: "Assurance habitation", label: "Assurance habitation" },
  { value: "Abonnement", label: "Abonnement" },
  { value: "Autre", label: "Autre" },
];

export function contratToFormValues(contrat: Contrat): ContratUpdateInput {
  // Box sans "Consommation" déjà saisie : pré-remplir avec le débit mesuré
  // (vrai test de débit, prioritaire) puis, à défaut, le débit auto-déclaré
  // par le prospect sur /economiser (Contrat.debit_declare, voir
  // backend/routers/leads_public.py) plutôt que de laisser le champ vide
  // alors que la donnée existe sur le contrat.
  const debitBox = contrat.speed_down ?? contrat.debit_declare;
  const consommationParDefaut =
    contrat.consommation ||
    (/box/i.test(contrat.categorie ?? "") && debitBox != null ? `${debitBox} Mbps` : "");
  return {
    univers: contrat.univers ?? "",
    categorie: contrat.categorie ?? "",
    fournisseur: contrat.fournisseur ?? "",
    nom_offre: contrat.nom_offre ?? "",
    cout_mensuel: contrat.cout_mensuel ?? undefined,
    reference_contrat: contrat.reference_contrat ?? "",
    statut_contrat: contrat.statut_contrat ?? "",
    date_souscription: contrat.date_souscription ?? "",
    date_fin_engagement: contrat.date_fin_engagement ?? "",
    consommation: consommationParDefaut,
    chez_nous: contrat.chez_nous ?? false,
    satisfaction_reseau: contrat.satisfaction_reseau ?? "",
    veut_rester: contrat.veut_rester ?? "",
    defaut_technique: contrat.defaut_technique ?? "",
    speed_down: contrat.speed_down ?? undefined,
    speed_up: contrat.speed_up ?? undefined,
    ligne_principale: contrat.ligne_principale ?? false,
    meme_operateur_mobile: contrat.meme_operateur_mobile ?? undefined,
    conserver_numero: contrat.conserver_numero ?? "",
    rio: contrat.rio ?? "",
    numero_ligne: contrat.numero_ligne ?? "",
    type_sim: contrat.type_sim ?? "",
    notes: contrat.notes ?? "",
  };
}

// "Situation actuelle" (satisfaction réseau, envie de rester, défaut
// technique, débit mesuré) n'a de sens que pour un forfait mobile/box — pas
// pour l'énergie ou l'assurance. Utile aussi pour un contrat "chez nous" (ex.
// signaler un défaut technique à vérifier sur une ligne déjà chez nous), pas
// seulement pour la situation avant conversion d'un contrat concurrent.
function estForfaitTelecom(categorie: string | undefined): boolean {
  return /mobile|box/i.test(categorie ?? "");
}

// Pour un contrat box, le champ "Consommation" (générique, texte libre) sert en
// pratique à noter le débit — on affiche donc "Débit" plutôt que "Consommation"
// pour ce type de contrat (reste stocké dans la même colonne Contrat.consommation,
// pas de migration nécessaire). Voir aussi contratToFormValues ci-dessus, qui
// pré-remplit ce champ depuis Contrat.speed_down/debit_declare. Exporté pour
// que ContratsTab.tsx applique le même intitulé dans l'affichage lecture seule.
export function estForfaitBox(categorie: string | undefined): boolean {
  return /box/i.test(categorie ?? "");
}

type ContratFormValues = ContratCreateInput | ContratUpdateInput;

interface ContratFormProps {
  mode: "create" | "edit";
  defaultValues: ContratFormValues;
  onSubmit: (values: ContratFormValues) => void | Promise<void>;
  submitError?: unknown;
  submitLabel: string;
  isSubmitting?: boolean;
}

export function ContratForm({
  mode,
  defaultValues,
  onSubmit,
  submitError,
  submitLabel,
  isSubmitting,
}: ContratFormProps) {
  const schema = mode === "create" ? contratCreateSchema : contratUpdateSchema;

  return (
    <AppForm schema={schema} defaultValues={defaultValues} onSubmit={onSubmit} submitError={submitError} className="space-y-4">
      {(form) => (
        <>
          <div className="grid grid-cols-2 gap-4">
            <FormField
              control={form.control}
              name="categorie"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Type</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value || undefined}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Sélectionner…" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {TYPES_CONTRAT.map((type) => (
                        <SelectItem key={type.value} value={type.value}>
                          {type.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="fournisseur"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Fournisseur</FormLabel>
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
              name="nom_offre"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Offre</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="cout_mensuel"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Prix mensuel (€)</FormLabel>
                  <FormControl>
                    <Input type="number" step="0.01" {...field} value={field.value ?? ""} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <FormField
              control={form.control}
              name="consommation"
              render={({ field }) => {
                const estBox = estForfaitBox(form.watch("categorie"));
                return (
                  <FormItem>
                    <FormLabel>{estBox ? "Débit" : "Consommation"}</FormLabel>
                    <FormControl>
                      <Input placeholder={estBox ? "Ex. 400 Mbps" : "Ex. 120 Go, 3500 kWh…"} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                );
              }}
            />
            <FormField
              control={form.control}
              name="chez_nous"
              render={({ field }) => (
                <FormItem className="flex items-center gap-2 space-y-0 self-end pb-2">
                  <FormControl>
                    <Checkbox checked={field.value ?? false} onCheckedChange={field.onChange} />
                  </FormControl>
                  <FormLabel className="!mt-0">Contrat souscrit chez nous</FormLabel>
                </FormItem>
              )}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <FormField
              control={form.control}
              name="statut_contrat"
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
                      {STATUTS_CONTRAT.map((statut) => (
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
            <FormField
              control={form.control}
              name="date_souscription"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Date de souscription</FormLabel>
                  <FormControl>
                    <Input placeholder="JJ/MM/AAAA" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <FormField
              control={form.control}
              name="date_fin_engagement"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Fin d&apos;engagement</FormLabel>
                  <FormControl>
                    <Input placeholder="JJ/MM/AAAA" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="reference_contrat"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Référence</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
          {form.watch("categorie") === "Forfait mobile" && (
            <div className="flex flex-wrap items-center gap-6">
              <FormField
                control={form.control}
                name="ligne_principale"
                render={({ field }) => (
                  <FormItem className="flex items-center gap-2 space-y-0">
                    <FormControl>
                      <Checkbox checked={field.value ?? false} onCheckedChange={field.onChange} />
                    </FormControl>
                    <FormLabel className="!mt-0">
                      Ligne mobile principale
                      <span className="ml-1 font-normal text-muted-foreground">
                        (utilisée pour la situation actuelle renseignée par le client)
                      </span>
                    </FormLabel>
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="meme_operateur_mobile"
                render={({ field }) => (
                  <FormItem className="flex items-center gap-2 space-y-0">
                    <FormControl>
                      <Checkbox checked={field.value ?? false} onCheckedChange={field.onChange} />
                    </FormControl>
                    <FormLabel className="!mt-0">
                      Toutes les lignes chez le même opérateur
                    </FormLabel>
                  </FormItem>
                )}
              />
            </div>
          )}
          {estForfaitTelecom(form.watch("categorie")) && (
            <div className="space-y-4 rounded-md border p-4">
              <p className="text-sm font-medium">Situation actuelle</p>
              <div className="grid grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="satisfaction_reseau"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Satisfaction réseau</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value || undefined}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Sélectionner…" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {SATISFACTION_RESEAU.map((option) => (
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
                <FormField
                  control={form.control}
                  name="veut_rester"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Souhaite rester</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value || undefined}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Sélectionner…" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {VEUT_RESTER_OPTIONS.map((option) => (
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
                name="defaut_technique"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Défaut technique potentiel</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value || undefined}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Sélectionner…" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {NIVEAUX_DEFAUT_TECHNIQUE.map((option) => (
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
              {(form.watch("speed_down") || form.watch("speed_up")) && (
                <p className="text-sm text-muted-foreground">
                  Débit mesuré : {form.watch("speed_down") ?? "—"} Mbps ↓ / {form.watch("speed_up") ?? "—"} Mbps ↑
                </p>
              )}
              {form.watch("categorie") === "Forfait mobile" && (
                <div className="space-y-4 border-t pt-4">
                  <p className="text-sm font-medium">Portabilité</p>
                  <div className="grid grid-cols-2 gap-4">
                    <FormField
                      control={form.control}
                      name="conserver_numero"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Conserver le numéro</FormLabel>
                          <Select onValueChange={field.onChange} value={field.value || undefined}>
                            <FormControl>
                              <SelectTrigger>
                                <SelectValue placeholder="Sélectionner…" />
                              </SelectTrigger>
                            </FormControl>
                            <SelectContent>
                              {CONSERVER_NUMERO_OPTIONS.map((option) => (
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
                    <FormField
                      control={form.control}
                      name="type_sim"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Type de SIM</FormLabel>
                          <Select onValueChange={field.onChange} value={field.value || undefined}>
                            <FormControl>
                              <SelectTrigger>
                                <SelectValue placeholder="Sélectionner…" />
                              </SelectTrigger>
                            </FormControl>
                            <SelectContent>
                              {TYPE_SIM_OPTIONS.map((option) => (
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
                  </div>
                  {form.watch("conserver_numero") === "oui" && (
                    <div className="grid grid-cols-2 gap-4">
                      <FormField
                        control={form.control}
                        name="numero_ligne"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Numéro de ligne à porter</FormLabel>
                            <FormControl>
                              <Input {...field} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name="rio"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>RIO</FormLabel>
                            <FormControl>
                              <Input {...field} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
          <FormField
            control={form.control}
            name="notes"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Notes</FormLabel>
                <FormControl>
                  <Input {...field} />
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
