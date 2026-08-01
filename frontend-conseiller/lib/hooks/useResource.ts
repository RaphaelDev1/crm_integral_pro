"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationOptions,
  type UseQueryOptions,
} from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";

type QueryParams = Record<string, string | number | boolean | undefined | null>;
type Id = string | number;

function buildPath(basePath: string, params?: QueryParams): string {
  if (!params) return basePath;
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `${basePath}?${qs}` : basePath;
}

// Factory générique de hooks React Query pour une ressource REST standard
// (list/one/create/update/delete). Évite de réécrire le même câblage
// queryKey/invalidation pour chaque ressource (clients, prospects,
// dossiers, factures…) — une seule fois ici, un appel par ressource.
//
// `resource` sert de préfixe de queryKey (ex. "clients"), `basePath` est le
// chemin backend correspondant (ex. "/clients"), consommé via apiFetch
// (donc toujours à travers le proxy BFF, voir lib/api.ts).
export function createResourceHooks<TItem, TCreate = Partial<TItem>, TUpdate = Partial<TItem>>(
  resource: string,
  basePath: string
) {
  const keys = {
    lists: () => [resource, "list"] as const,
    list: (params?: QueryParams) => [resource, "list", params ?? {}] as const,
    detail: (id: Id) => [resource, "detail", id] as const,
  };

  function useList(params?: QueryParams, options?: Omit<UseQueryOptions<TItem[]>, "queryKey" | "queryFn">) {
    return useQuery({
      ...options,
      queryKey: keys.list(params),
      queryFn: () => apiFetch<TItem[]>(buildPath(basePath, params)),
    });
  }

  function useOne(id: Id | undefined, options?: Omit<UseQueryOptions<TItem>, "queryKey" | "queryFn" | "enabled">) {
    return useQuery({
      ...options,
      queryKey: keys.detail(id ?? ""),
      queryFn: () => apiFetch<TItem>(`${basePath}/${id}`),
      enabled: id !== undefined,
    });
  }

  function useCreate(options?: Omit<UseMutationOptions<TItem, unknown, TCreate>, "mutationFn" | "onSuccess"> & {
    onSuccess?: (data: TItem, variables: TCreate) => void;
  }) {
    const queryClient = useQueryClient();
    return useMutation({
      ...options,
      mutationFn: (values: TCreate) =>
        apiFetch<TItem>(basePath, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(values),
        }),
      onSuccess: (data, variables) => {
        queryClient.invalidateQueries({ queryKey: keys.lists() });
        options?.onSuccess?.(data, variables);
      },
    });
  }

  function useUpdate(
    options?: Omit<UseMutationOptions<TItem, unknown, { id: Id; values: TUpdate }>, "mutationFn" | "onSuccess"> & {
      onSuccess?: (data: TItem, variables: { id: Id; values: TUpdate }) => void;
    }
  ) {
    const queryClient = useQueryClient();
    return useMutation({
      ...options,
      mutationFn: ({ id, values }: { id: Id; values: TUpdate }) =>
        apiFetch<TItem>(`${basePath}/${id}`, {
          method: "PUT",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(values),
        }),
      onSuccess: (data, variables) => {
        queryClient.invalidateQueries({ queryKey: keys.lists() });
        queryClient.invalidateQueries({ queryKey: keys.detail(variables.id) });
        options?.onSuccess?.(data, variables);
      },
    });
  }

  function useDelete(options?: Omit<UseMutationOptions<void, unknown, Id>, "mutationFn" | "onSuccess"> & {
    onSuccess?: (data: void, id: Id) => void;
  }) {
    const queryClient = useQueryClient();
    return useMutation({
      ...options,
      mutationFn: (id: Id) => apiFetch<void>(`${basePath}/${id}`, { method: "DELETE" }),
      onSuccess: (data, id) => {
        queryClient.invalidateQueries({ queryKey: keys.lists() });
        options?.onSuccess?.(data, id);
      },
    });
  }

  return { keys, useList, useOne, useCreate, useUpdate, useDelete };
}
