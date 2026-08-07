"use client";

import * as Sentry from "@sentry/nextjs";
import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { ThemeProvider } from "next-themes";
import { useState } from "react";
import { toast } from "sonner";

import { Toaster } from "@/components/ui/sonner";
import { ApiError } from "@/lib/api";
import { createQueryClient } from "@/lib/queryClient";

// Intercepteur d'erreurs unique pour toutes les queries/mutations React
// Query : toast utilisateur avec le message backend (ApiError.detail) ou un
// message générique, puis remontée Sentry pour l'observabilité.
function reportQueryError(error: unknown) {
  toast.error(error instanceof ApiError ? error.detail : "Une erreur est survenue.");
  Sentry.captureException(error);
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => createQueryClient(reportQueryError));

  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
      <QueryClientProvider client={queryClient}>
        {children}
        <Toaster richColors position="top-right" />
        {process.env.NODE_ENV !== "production" && <ReactQueryDevtools initialIsOpen={false} />}
      </QueryClientProvider>
    </ThemeProvider>
  );
}
