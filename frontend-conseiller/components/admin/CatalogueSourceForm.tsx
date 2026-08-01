"use client";

import { AppForm } from "@/components/forms/AppForm";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { DialogFooter } from "@/components/ui/dialog";
import { FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
  catalogueSourceCreateSchema,
  catalogueSourceUpdateSchema,
  type CatalogueSourceCreateInput,
  type CatalogueSourceUpdateInput,
} from "@/lib/schemas/catalogue";
import type { CatalogueSource } from "@/lib/types";

type CatalogueSourceFormValues = CatalogueSourceCreateInput | CatalogueSourceUpdateInput;

interface CatalogueSourceFormProps {
  mode: "create" | "edit";
  defaultValues: CatalogueSourceFormValues;
  onSubmit: (values: CatalogueSourceFormValues) => void | Promise<void>;
  submitError?: unknown;
  submitLabel: string;
  isSubmitting?: boolean;
}

export function catalogueSourceToFormValues(source: CatalogueSource): CatalogueSourceUpdateInput {
  return {
    univers: source.univers ?? "",
    categorie: source.categorie ?? "",
    fournisseur: source.fournisseur ?? "",
    url: source.url ?? "",
    type_source: source.type_source,
    methode: source.methode,
    frequence_h: source.frequence_h,
    actif: source.actif,
  };
}

export function CatalogueSourceForm({ mode, defaultValues, onSubmit, submitError, submitLabel, isSubmitting }: CatalogueSourceFormProps) {
  const schema = mode === "create" ? catalogueSourceCreateSchema : catalogueSourceUpdateSchema;

  return (
    <AppForm schema={schema} defaultValues={defaultValues} onSubmit={onSubmit} submitError={submitError} className="space-y-4">
      {(form) => (
        <>
          <div className="grid grid-cols-2 gap-4">
            <FormField
              control={form.control}
              name="univers"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Univers</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="Télécom / Énergie / Abonnements" />
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
            name="url"
            render={({ field }) => (
              <FormItem>
                <FormLabel>URL de la page tarifs</FormLabel>
                <FormControl>
                  <Input {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <div className="grid grid-cols-2 gap-4">
            <FormField
              control={form.control}
              name="methode"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Méthode de récupération</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="requests / playwright" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="frequence_h"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Fréquence (heures)</FormLabel>
                  <FormControl>
                    <Input type="number" {...field} value={field.value ?? ""} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
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
