import { z } from "zod";

// Miroir de backend/schemas/catalogue.py (CatalogueSourceCreate/Update).
export const catalogueSourceBaseSchema = z.object({
  univers: z.string().optional(),
  categorie: z.string().optional(),
  fournisseur: z.string().optional(),
  url: z.string().optional(),
  type_source: z.string().optional(),
  methode: z.string().optional(),
  frequence_h: z.coerce.number().int().optional(),
  actif: z.boolean().optional(),
});

export const catalogueSourceCreateSchema = catalogueSourceBaseSchema.extend({
  url: z.string().trim().min(1, "L'URL est requise."),
  type_source: z.string(),
  methode: z.string(),
  frequence_h: z.coerce.number().int(),
  actif: z.boolean(),
});

export const catalogueSourceUpdateSchema = catalogueSourceBaseSchema;

export type CatalogueSourceCreateInput = z.infer<typeof catalogueSourceCreateSchema>;
export type CatalogueSourceUpdateInput = z.infer<typeof catalogueSourceUpdateSchema>;
