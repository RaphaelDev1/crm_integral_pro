import { z } from "zod";

import { UNIVERS_DIAGNOSTIC } from "@/lib/diagnosticConstants";

// Étape 1 — Univers. Miroir de src/app.py (w_univers, w_service_principal).
export const etapeUniversSchema = z
  .object({
    univers: z.array(z.enum(UNIVERS_DIAGNOSTIC)).min(1, "Cochez au moins un univers."),
    servicePrincipal: z.string().optional(),
  })
  .superRefine((values, ctx) => {
    if (values.univers.includes("Télécom") && !values.servicePrincipal) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["servicePrincipal"],
        message: "Sélectionnez le service principal recherché.",
      });
    }
  });
export type EtapeUniversValues = z.infer<typeof etapeUniversSchema>;

// Étape 2 — Identité du client (mode "nouveau"). Sous-ensemble de
// lib/schemas/prospect.ts::prospectCreateSchema — le diagnostic ne collecte
// que les champs utiles à l'étude, pas le reste de la fiche prospect.
export const etapeIdentiteSchema = z
  .object({
    typeClient: z.string().min(1),
    prenom: z.string().trim().min(1, "Le prénom est requis."),
    nom: z.string().trim().min(1, "Le nom est requis."),
    telephone: z.string().trim().min(1, "Le téléphone est requis."),
    email: z.string().email("Adresse e-mail invalide.").optional().or(z.literal("")),
    codePostal: z.string().trim().min(1, "Le code postal est requis."),
    ville: z.string().trim().min(1, "La ville est requise."),
    adresse: z.string().optional(),
    raisonSociale: z.string().optional(),
    effectif: z.string().optional(),
  })
  .superRefine((values, ctx) => {
    if (values.typeClient === "Professionnel") {
      if (!values.raisonSociale?.trim()) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["raisonSociale"],
          message: "Le nom de l'entreprise est requis pour un client professionnel.",
        });
      }
      if (!values.effectif?.trim()) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["effectif"],
          message: "Le nombre d'employés est requis pour un client professionnel.",
        });
      }
    }
  });
export type EtapeIdentiteValues = z.infer<typeof etapeIdentiteSchema>;

// Étape 3 — Situation actuelle, sous-schéma Télécom (requis uniquement si
// "Télécom" a été coché à l'étape 1 — voir _champs_obligatoires_telecom()
// dans src/app.py, reproduit ici via .superRefine côté page).
export const situationTelecomSchema = z.object({
  operateurActuel: z.string().min(1, "Renseignez l'opérateur actuel."),
  techno: z.string().min(1),
  offreActuelle: z.string().optional(),
  coutMensuelActuel: z.coerce.number().min(0.01, "Le coût mensuel actuel est requis."),
  dataGoMin: z.string().optional(),
  debitSouhaite: z.string().optional(),
  satisfactionReseau: z.string().min(1, "Renseignez la satisfaction réseau du client."),
  defautTechnique: z.string().min(1, "Renseignez le défaut technique potentiel."),
  veutRester: z.string().min(1, "Indiquez si le client souhaite rester chez son opérateur actuel."),
  speedDown: z.coerce.number().min(0).optional(),
  speedUp: z.coerce.number().min(0).optional(),
});
export type SituationTelecomValues = z.infer<typeof situationTelecomSchema>;

export const situationEnergieSchema = z.object({
  fournisseurEnergie: z.string().optional(),
  coutElec: z.coerce.number().min(0).optional(),
  coutGaz: z.coerce.number().min(0).optional(),
});
export type SituationEnergieValues = z.infer<typeof situationEnergieSchema>;

export const abonnementItemSchema = z.object({
  nom: z.string().trim().min(1, "Le nom de l'abonnement est requis."),
  categorie: z.string().min(1, "Choisissez une catégorie."),
  cout: z.coerce.number().min(0.01, "Le coût mensuel est requis."),
});
export type AbonnementItem = z.infer<typeof abonnementItemSchema> & { id: string };
