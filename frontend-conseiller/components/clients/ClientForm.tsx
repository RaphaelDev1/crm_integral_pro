"use client";

import { AppForm } from "@/components/forms/AppForm";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { DialogFooter } from "@/components/ui/dialog";
import { FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { OBJECTIFS_PRINCIPAUX_OPTIONS, TRANCHES_AGE_OPTIONS } from "@/lib/diagnosticConstants";
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
    objectif_principal: client.objectif_principal ?? "",
    notes: client.notes ?? "",
    age: client.age ?? undefined,
    tranche_age: client.tranche_age ?? "",
    consentement_rgpd: client.consentement_rgpd ?? false,
    consentement_demarchage: client.consentement_demarchage ?? false,
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
          <FormField
            control={form.control}
            name="objectif_principal"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Objectif de la demande</FormLabel>
                <p className="text-xs text-muted-foreground">
                  Renseigné d'office si le client vient de la landing /economiser — indique si sa
                  démarche est motivée par une raison financière ou un gain de temps.
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
