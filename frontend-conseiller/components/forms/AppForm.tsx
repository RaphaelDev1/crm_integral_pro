"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm, type DefaultValues, type FieldValues, type Path, type UseFormReturn } from "react-hook-form";
import type { z } from "zod";

import { Form } from "@/components/ui/form";
import { ApiError } from "@/lib/api";

interface AppFormProps<TSchema extends z.ZodType<FieldValues>> {
  schema: TSchema;
  defaultValues: DefaultValues<z.infer<TSchema>>;
  onSubmit: (values: z.infer<TSchema>) => void | Promise<void>;
  // Render-prop : donne accès à `form` (formState.isDirty, isSubmitting,
  // errors…) pour construire les <FormField> sans dupliquer le câblage
  // react-hook-form + shadcn <Form> à chaque écran (voir
  // ChangePasswordDialog.tsx pour le pattern reproduit ici).
  children: (form: UseFormReturn<z.infer<TSchema>>) => React.ReactNode;
  className?: string;
  // Erreur de la mutation de soumission (ex. `mutation.error`). Si c'est une
  // ApiError contenant des erreurs de validation Pydantic (voir
  // lib/api.ts:ApiError.fieldErrors), elles sont automatiquement reportées
  // sur les champs correspondants via form.setError.
  submitError?: unknown;
}

export function AppForm<TSchema extends z.ZodType<FieldValues>>({
  schema,
  defaultValues,
  onSubmit,
  children,
  className,
  submitError,
}: AppFormProps<TSchema>) {
  const form = useForm<z.infer<TSchema>>({
    resolver: zodResolver(schema),
    defaultValues,
  });

  useEffect(() => {
    if (!(submitError instanceof ApiError) || submitError.fieldErrors.length === 0) return;
    for (const { field, message } of submitError.fieldErrors) {
      form.setError(field as Path<z.infer<TSchema>>, { type: "server", message });
    }
  }, [submitError, form]);

  return (
    <Form {...form}>
      <form className={className} onSubmit={form.handleSubmit((values) => onSubmit(values))}>
        {children(form)}
      </form>
    </Form>
  );
}
