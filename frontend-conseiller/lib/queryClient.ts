import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/lib/api";

// Instance unique, montée par app/providers.tsx. `onError` est injecté par
// l'appelant (toast + Sentry côté UI) pour garder ce fichier indépendant de
// toute lib de présentation.
export function createQueryClient(onError?: (error: unknown) => void) {
  return new QueryClient({
    queryCache: new QueryCache({ onError }),
    mutationCache: new MutationCache({ onError }),
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        retry: (failureCount, error) => {
          // Les erreurs 4xx (dont 401/403) ne se résolvent pas en réessayant.
          if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
            return false;
          }
          return failureCount < 2;
        },
      },
      mutations: {
        retry: false,
      },
    },
  });
}
