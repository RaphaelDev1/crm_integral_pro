"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { DashboardSummary } from "@/lib/types";

// refetchInterval 60s — le conseiller garde souvent l'onglet dashboard ouvert
// toute la journée, les compteurs de relances doivent bouger sans reload manuel.
export function useDashboardSummary() {
  return useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: () => apiFetch<DashboardSummary>("/dashboard/summary"),
    refetchInterval: 60_000,
  });
}
