"use client";

import { AppForm } from "@/components/forms/AppForm";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { DialogFooter } from "@/components/ui/dialog";
import { FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ROLES_UTILISATEUR, userCreateSchema, userUpdateSchema, type UserCreateInput, type UserUpdateInput } from "@/lib/schemas/user";
import type { User } from "@/lib/types";

type UserFormValues = UserCreateInput | UserUpdateInput;

interface UserFormProps {
  mode: "create" | "edit";
  defaultValues: UserFormValues;
  onSubmit: (values: UserFormValues) => void | Promise<void>;
  submitError?: unknown;
  submitLabel: string;
  isSubmitting?: boolean;
}

export function userToFormValues(user: User): UserUpdateInput {
  return {
    nom_complet: user.nom_complet,
    role: user.role as UserUpdateInput["role"],
    telephone: user.telephone ?? "",
    actif: user.actif,
    password: "",
  };
}

export function UserForm({ mode, defaultValues, onSubmit, submitError, submitLabel, isSubmitting }: UserFormProps) {
  const schema = mode === "create" ? userCreateSchema : userUpdateSchema;

  return (
    <AppForm schema={schema} defaultValues={defaultValues} onSubmit={onSubmit} submitError={submitError} className="space-y-4">
      {(form) => (
        <>
          {mode === "create" && (
            <FormField
              control={form.control}
              name="username"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Identifiant</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          )}
          <FormField
            control={form.control}
            name="nom_complet"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Nom complet</FormLabel>
                <FormControl>
                  <Input {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="role"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Rôle</FormLabel>
                <Select onValueChange={field.onChange} value={field.value}>
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {ROLES_UTILISATEUR.map((role) => (
                      <SelectItem key={role} value={role}>
                        {role}
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
            name="telephone"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Téléphone (affiché sur les PDF de restitution)</FormLabel>
                <FormControl>
                  <Input {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{mode === "create" ? "Mot de passe" : "Nouveau mot de passe (optionnel)"}</FormLabel>
                <FormControl>
                  <Input type="password" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          {mode === "edit" && (
            <FormField
              control={form.control}
              name="actif"
              render={({ field }) => (
                <FormItem className="flex items-center gap-2 space-y-0">
                  <FormControl>
                    <Checkbox checked={field.value} onCheckedChange={field.onChange} />
                  </FormControl>
                  <FormLabel className="!mt-0">Compte actif</FormLabel>
                </FormItem>
              )}
            />
          )}
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
