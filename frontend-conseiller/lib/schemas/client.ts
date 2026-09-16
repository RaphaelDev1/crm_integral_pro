import { z } from "zod";

// Miroir de backend/schemas/client.py (ClientBase/ClientCreate/ClientUpdate).
// Convention Phase 0 : tout champ contrôlé du formulaire client doit passer
// par ce schéma — pas de useState non validé.
export const clientBaseSchema = z.object({
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
  operateur_actuel: z.string().optional(),
  techno: z.string().optional(),
  data_go: z.string().optional(),
  offre_actuelle: z.string().optional(),
  cout_mensuel_actuel: z.coerce.number().optional(),
  satisfaction_reseau: z.string().optional(),
  veut_rester: z.string().optional(),
  defaut_technique: z.string().optional(),
  speed_down: z.coerce.number().optional(),
  speed_up: z.coerce.number().optional(),
  fournisseur_energie: z.string().optional(),
  cout_elec: z.coerce.number().optional(),
  cout_gaz: z.coerce.number().optional(),
  objectif_principal: z.string().optional(),
  economie_estimee_an: z.coerce.number().optional(),
  notes: z.string().optional(),
  date_relance: z.string().optional(),
  statut_relance: z.string().optional(),
  age: z.coerce.number().optional(),
  tranche_age: z.string().optional(),
  consentement_rgpd: z.boolean().optional(),
  consentement_demarchage: z.boolean().optional(),
});

export const clientCreateSchema = clientBaseSchema.extend({
  prenom: z.string().trim().min(1, "Le prénom est requis."),
  nom: z.string().trim().min(1, "Le nom est requis."),
});

export const clientUpdateSchema = clientBaseSchema;

export type ClientCreateInput = z.infer<typeof clientCreateSchema>;
export type ClientUpdateInput = z.infer<typeof clientUpdateSchema>;
