import { z } from "zod";

// Miroir de backend/schemas/user.py (UserCreate/UserUpdate).
export const ROLES_UTILISATEUR = ["Conseiller", "Admin"] as const;

export const userCreateSchema = z.object({
  username: z.string().trim().min(1, "L'identifiant est requis."),
  nom_complet: z.string().trim().min(1, "Le nom complet est requis."),
  password: z.string().min(8, "Le mot de passe doit contenir au moins 8 caractères."),
  role: z.enum(ROLES_UTILISATEUR),
});

export const userUpdateSchema = z.object({
  nom_complet: z.string().trim().min(1, "Le nom complet est requis.").optional(),
  role: z.enum(ROLES_UTILISATEUR).optional(),
  actif: z.boolean().optional(),
  password: z.string().min(8, "Le mot de passe doit contenir au moins 8 caractères.").optional().or(z.literal("")),
});

export type UserCreateInput = z.infer<typeof userCreateSchema>;
export type UserUpdateInput = z.infer<typeof userUpdateSchema>;
