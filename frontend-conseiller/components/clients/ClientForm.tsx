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
  clientCreateSchema,
  clientUpdateSchema,
  type ClientCreateInput,
  type ClientUpdateInput,
} from "@/lib/schemas/client";
import type { Client } from "@/lib/types";

// Composant réutilisable pour la création (Dialog de la liste, schéma
// clientCreateSchema — prénom/nom requis) et l'édition (onglet Infos de la
// fiche, schéma clientUpdateSchema — tous champs optionnels).
type ClientFormValues = ClientCreateInput | ClientUpdateInput;

interface ClientFormProps {
  mode: "create" | "edit";
  defaultValues: ClientFormValues;
  onSubmit: (values: ClientFormValues) => void | Promise<void>;
  submitError?: unknown;
  submitLabel: string;
  isSubmitting?: boolean;
}

export function clientToFormValues(client: Client): ClientUpdateInput {
  return {
    ref: client.ref ?? "",
    prenom: client.prenom ?? "",
    nom: client.nom ?? "",
    telephone: client.telephone ?? "",
    email: client.email ?? "",
    code_postal: client.code_postal ?? "",
    ville: client.ville ?? "",
    adresse: client.adresse ?? "",
    type_client: client.type_client ?? "",
    notes: client.notes ?? "",
    operateur_actuel: client.operateur_actuel ?? "",
    satisfaction_reseau: client.satisfaction_reseau ?? "",
    veut_rester: client.veut_rester ?? "",
    defaut_technique: client.defaut_technique ?? "",
  };
}

export function ClientForm({
  mode,
  defaultValues,
  onSubmit,
  submitError,
  submitLabel,
  isSubmitting,
}: ClientFormProps) {
  const schema = mode === "create" ? clientCreateSchema : clientUpdateSchema;

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
          <div className="grid grid-cols-3 gap-4">
            <FormField
              control={form.control}
              name="adresse"
              render={({ field }) => (
                <FormItem className="col-span-2">
                  <FormLabel>Adresse</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="code_postal"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Code postal</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
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
