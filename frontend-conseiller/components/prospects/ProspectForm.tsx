"use client";

import { AppForm } from "@/components/forms/AppForm";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DialogFooter } from "@/components/ui/dialog";
import { FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  LISTE_OPERATEURS_TEL,
  NIVEAUX_DEFAUT_TECHNIQUE,
  SATISFACTION_RESEAU,
  VEUT_RESTER_OPTIONS,
} from "@/lib/diagnosticConstants";
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
const STATUTS_PROSPECT = ["À relancer", "Fin de contrat", "Relance dossier", "Autre"];

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
    ville: prospect.ville ?? "",
    adresse: prospect.adresse ?? "",
    origine: prospect.origine ?? "",
    statut: prospect.statut ?? "",
    date_relance: prospect.date_relance ?? "",
    notes: prospect.notes ?? "",
    operateur_actuel: prospect.operateur_actuel ?? "",
    satisfaction_reseau: prospect.satisfaction_reseau ?? "",
    veut_rester: prospect.veut_rester ?? "",
    defaut_technique: prospect.defaut_technique ?? "",
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
                  <FormLabel>Prénom</FormLabel>
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
                  <FormLabel>Nom</FormLabel>
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
                  <FormLabel>Téléphone</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Email</FormLabel>
                  <FormControl>
                    <Input type="email" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <FormField
              control={form.control}
              name="ville"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Ville</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="adresse"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Adresse</FormLabel>
                  <FormControl>
                    <Input placeholder="N° et rue" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
          <FormField
            control={form.control}
            name="origine"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Origine</FormLabel>
                <FormControl>
                  <Input placeholder="Chatbot, Manuel, Import…" {...field} />
                </FormControl>
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
          </div>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Réseau actuel</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="operateur_actuel"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Opérateur actuel</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value || undefined}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Sélectionner…" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {LISTE_OPERATEURS_TEL.map((option) => (
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
                    <FormLabel>Souhaite rester chez son opérateur actuel</FormLabel>
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
              <FormField
                control={form.control}
                name="defaut_technique"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Défaut technique potentiel</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value || undefined}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Aucun signalé" />
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
            </CardContent>
          </Card>
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
