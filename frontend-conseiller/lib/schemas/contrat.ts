import { z } from "zod";

// Miroir de backend/schemas/contrat.py (ContratBase/ContratCreate/ContratUpdate).
export const contratBaseSchema = z.object({
  univers: z.string().optional(),
  categorie: z.string().optional(),
  fournisseur: z.string().optional(),
  nom_offre: z.string().optional(),
  cout_mensuel: z.coerce.number().optional(),
  economie_mensuelle: z.coerce.number().optional(),
  reference_contrat: z.string().optional(),
  statut_contrat: z.string().optional(),
  date_souscription: z.string().optional(),
  date_fin_engagement: z.string().optional(),
  notes: z.string().optional(),
});

export const contratCreateSchema = contratBaseSchema.extend({
  client_id: z.number(),
  fournisseur: z.string().trim().min(1, "Le fournisseur est requis."),
});

export const contratUpdateSchema = contratBaseSchema;

export type ContratCreateInput = z.infer<typeof contratCreateSchema>;
export type ContratUpdateInput = z.infer<typeof contratUpdateSchema>;
