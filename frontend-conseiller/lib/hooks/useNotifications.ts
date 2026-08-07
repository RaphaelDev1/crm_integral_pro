"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { Notification } from "@/lib/types";

// refetchInterval 30s — alerte le conseiller assez vite quand le client agit
// de son côté (upload de document, signature de mandat) sans recharger la page.
export function useNotifications() {
  return useQuery({
    queryKey: ["notifications", "list"],
    queryFn: () => apiFetch<Notification[]>("/notifications"),
    refetchInterval: 30_000,
  });
}

export function useMarquerNotificationLue() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiFetch<Notification>(`/notifications/${id}/lu`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });
}
