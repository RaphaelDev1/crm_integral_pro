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
  consommation: z.string().optional(),
  chez_nous: z.boolean().optional(),
  satisfaction_reseau: z.string().optional(),
  veut_rester: z.string().optional(),
  defaut_technique: z.string().optional(),
  speed_down: z.coerce.number().optional(),
  speed_up: z.coerce.number().optional(),
  ligne_principale: z.boolean().optional(),
  meme_operateur_mobile: z.boolean().optional(),
  conserver_numero: z.string().optional(),
  rio: z.string().optional(),
  numero_ligne: z.string().optional(),
  type_sim: z.string().optional(),
  chauffage_principal: z.string().optional(),
  puissance_kva: z.string().optional(),
  option_tarifaire: z.string().optional(),
  gros_equipement_electrique: z.boolean().optional(),
  usage_tv: z.string().optional(),
  abonnements_payants: z.string().optional(),
  notes: z.string().optional(),
});

export const contratCreateSchema = contratBaseSchema
  .extend({
    client_id: z.number().optional(),
    prospect_id: z.number().optional(),
    fournisseur: z.string().trim().min(1, "Le fournisseur est requis."),
  })
  .refine((values) => values.client_id != null || values.prospect_id != null, {
    message: "Un contrat doit être rattaché à un client ou un prospect.",
    path: ["client_id"],
  });

export const contratUpdateSchema = contratBaseSchema;

export type ContratCreateInput = z.infer<typeof contratCreateSchema>;
export type ContratUpdateInput = z.infer<typeof contratUpdateSchema>;
