import { z } from "zod";

// Miroir de backend/schemas/prospect.py (ProspectBase/ProspectCreate/ProspectUpdate).
export const prospectBaseSchema = z.object({
  ref: z.string().optional(),
  prenom: z.string().optional(),
  nom: z.string().optional(),
  telephone: z.string().optional(),
  email: z.string().email("Adresse e-mail invalide.").optional().or(z.literal("")),
  code_postal: z.string().optional(),
  ville: z.string().optional(),
  adresse: z.string().optional(),
  type_client: z.string().optional(),
  raison_sociale: z.string().optional(),
  effectif: z.string().optional(),
  univers_interesse: z.string().optional(),
  service_principal: z.string().optional(),
  objectif_principal: z.string().optional(),
  operateur_actuel: z.string().optional(),
  techno: z.string().optional(),
  data_go: z.string().optional(),
  cout_mensuel_actuel: z.coerce.number().optional(),
  offre_actuelle: z.string().optional(),
  satisfaction_reseau: z.string().optional(),
  veut_rester: z.string().optional(),
  defaut_technique: z.string().optional(),
  speed_down: z.coerce.number().optional(),
  speed_up: z.coerce.number().optional(),
  cout_elec: z.coerce.number().optional(),
  cout_gaz: z.coerce.number().optional(),
  fournisseur_energie: z.string().optional(),
  abonnements: z.string().optional(),
  lignes_multi: z.string().optional(),
  economie_estimee_an: z.coerce.number().optional(),
  notes: z.string().optional(),
  motif_refus: z.string().optional(),
  statut: z.string().optional(),
  date_relance: z.string().optional(),
  offres_interet: z.string().optional(),
  score: z.coerce.number().optional(),
  origine: z.string().optional(),
  plage_horaire_rappel: z.string().optional(),
  age: z.coerce.number().optional(),
  tranche_age: z.string().optional(),
  consentement_rgpd: z.boolean().optional(),
  consentement_demarchage: z.boolean().optional(),
});

export const prospectCreateSchema = prospectBaseSchema.extend({
  prenom: z.string().trim().min(1, "Le prénom est requis."),
  nom: z.string().trim().min(1, "Le nom est requis."),
});

export const prospectUpdateSchema = prospectBaseSchema;

export type ProspectCreateInput = z.infer<typeof prospectCreateSchema>;
export type ProspectUpdateInput = z.infer<typeof prospectUpdateSchema>;
