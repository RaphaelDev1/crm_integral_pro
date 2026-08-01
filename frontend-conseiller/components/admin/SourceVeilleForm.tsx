"use client";

import { AppForm } from "@/components/forms/AppForm";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { DialogFooter } from "@/components/ui/dialog";
import { FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
  sourceVeilleCreateSchema,
  sourceVeilleUpdateSchema,
  type SourceVeilleCreateInput,
  type SourceVeilleUpdateInput,
} from "@/lib/schemas/veille";
import type { SourceVeille } from "@/lib/types";

type SourceVeilleFormValues = SourceVeilleCreateInput | SourceVeilleUpdateInput;

interface SourceVeilleFormProps {
  mode: "create" | "edit";
  defaultValues: SourceVeilleFormValues;
  onSubmit: (values: SourceVeilleFormValues) => void | Promise<void>;
  submitError?: unknown;
  submitLabel: string;
  isSubmitting?: boolean;
}

export function sourceVeilleToFormValues(source: SourceVeille): SourceVeilleUpdateInput {
  return {
    univers: source.univers ?? "",
    categorie: source.categorie ?? "",
    fournisseur: source.fournisseur ?? "",
    nom_offre: source.nom_offre ?? "",
    url: source.url ?? "",
    selecteur_prix: source.selecteur_prix ?? "",
    actif: source.actif,
  };
}

export function SourceVeilleForm({ mode, defaultValues, onSubmit, submitError, submitLabel, isSubmitting }: SourceVeilleFormProps) {
  const schema = mode === "create" ? sourceVeilleCreateSchema : sourceVeilleUpdateSchema;

  return (
    <AppForm schema={schema} defaultValues={defaultValues} onSubmit={onSubmit} submitError={submitError} className="space-y-4">
      {(form) => (
        <>
          <div className="grid grid-cols-2 gap-4">
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
            <FormField
              control={form.control}
              name="nom_offre"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Nom de l&apos;offre</FormLabel>
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
              name="univers"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Univers</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="telecom / energie / abonnements" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="categorie"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Catégorie</FormLabel>
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
            name="url"
            render={({ field }) => (
              <FormItem>
                <FormLabel>URL surveillée</FormLabel>
                <FormControl>
                  <Input {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="selecteur_prix"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Sélecteur CSS du prix</FormLabel>
                <FormControl>
                  <Input {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="actif"
            render={({ field }) => (
              <FormItem className="flex items-center gap-2 space-y-0">
                <FormControl>
                  <Checkbox checked={field.value} onCheckedChange={field.onChange} />
                </FormControl>
                <FormLabel className="!mt-0">Source active</FormLabel>
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
