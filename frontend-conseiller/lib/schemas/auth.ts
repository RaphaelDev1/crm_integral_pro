import { z } from "zod";

// `nouveau_mot_de_passe` mirroir de backend/schemas/auth.py:ChangePasswordRequest
// (POST /auth/change-password) ; `confirmation` est un champ client-only,
// jamais envoyé au backend.
export const changePasswordSchema = z
  .object({
    nouveau_mot_de_passe: z.string().min(8, "8 caractères minimum."),
    confirmation: z.string(),
  })
  .refine((data) => data.nouveau_mot_de_passe === data.confirmation, {
    message: "Les mots de passe ne correspondent pas.",
    path: ["confirmation"],
  });

export type ChangePasswordInput = z.infer<typeof changePasswordSchema>;
