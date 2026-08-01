import { z } from "zod";

// Miroir de backend/schemas/veille.py (SourceVeilleCreate/SourceVeilleUpdate).
export const sourceVeilleBaseSchema = z.object({
  univers: z.string().optional(),
  categorie: z.string().optional(),
  fournisseur: z.string().optional(),
  nom_offre: z.string().optional(),
  url: z.string().optional(),
  selecteur_prix: z.string().optional(),
  actif: z.boolean().optional(),
});

export const sourceVeilleCreateSchema = sourceVeilleBaseSchema.extend({
  fournisseur: z.string().trim().min(1, "Le fournisseur est requis."),
  url: z.string().trim().min(1, "L'URL est requise."),
  actif: z.boolean(),
});

export const sourceVeilleUpdateSchema = sourceVeilleBaseSchema;

export type SourceVeilleCreateInput = z.infer<typeof sourceVeilleCreateSchema>;
export type SourceVeilleUpdateInput = z.infer<typeof sourceVeilleUpdateSchema>;
