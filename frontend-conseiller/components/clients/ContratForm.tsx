"use client";

import { AppForm } from "@/components/forms/AppForm";
import { Button } from "@/components/ui/button";
import { DialogFooter } from "@/components/ui/dialog";
import { FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
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
// colonne "Type" affichée dans ContratsTab.
export const TYPES_CONTRAT = [
  "Forfait mobile",
  "Forfait box",
  "Énergie électricité",
  "Énergie gaz",
  "Assurance habitation",
  "Abonnement",
  "Autre",
];

export function contratToFormValues(contrat: Contrat): ContratUpdateInput {
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
    notes: contrat.notes ?? "",
  };
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
                        <SelectItem key={type} value={type}>
                          {type}
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
