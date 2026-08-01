"use client";

import Link from "next/link";
import { useMemo } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { statutDossierBadgeClass, LABELS_STATUT_DOSSIER, type StatutDossier } from "@/lib/dossierStatuts";
import { useAlertesOffresListe, useRejeterAlerteOffre, useValiderAlerteOffre } from "@/lib/hooks/useAlertesOffres";
import { clientsResource } from "@/lib/hooks/useClients";
import { useDashboardSummary } from "@/lib/hooks/useDashboard";
import { useDossiersStagnants } from "@/lib/hooks/useDossiers";
import { useMandatsHonorairesListe } from "@/lib/hooks/useHonoraires";
import { prospectsResource } from "@/lib/hooks/useProspects";
import { classerRelance, dansLesSeptProchainsJours, type RelanceItem } from "@/lib/relances";
import type { AlerteOffre, Dossier } from "@/lib/types";

export default function DashboardPage() {
  const summaryQuery = useDashboardSummary();
  const clientsQuery = clientsResource.useList();
  const prospectsQuery = prospectsResource.useList();
  const mandatsQuery = useMandatsHonorairesListe();

  const mandatsEnAttente = useMemo(
    () => (mandatsQuery.data ?? []).filter((m) => m.statut !== "signe").length,
    [mandatsQuery.data]
  );

  const relances = useMemo(() => {
    const aujourdhui = new Date();
    const items: RelanceItem[] = [];
    for (const client of clientsQuery.data ?? []) {
      items.push({
        id: client.id,
        type: "client",
        label: `${client.prenom ?? ""} ${client.nom ?? ""}`.trim() || `Client #${client.id}`,
        dateRelance: client.date_relance ?? "",
        statutRelance: client.statut_relance,
      });
    }
    for (const prospect of prospectsQuery.data ?? []) {
      if (prospect.converti_at) continue; // relance suivie côté Client une fois converti
      items.push({
        id: prospect.id,
        type: "prospect",
        label: `${prospect.prenom ?? ""} ${prospect.nom ?? ""}`.trim() || `Prospect #${prospect.id}`,
        dateRelance: prospect.date_relance ?? "",
        statutRelance: prospect.statut,
      });
    }

    const retard = items.filter((i) => classerRelance(i.dateRelance, aujourdhui) === "retard");
    const jour = items.filter((i) => classerRelance(i.dateRelance, aujourdhui) === "jour");
    const venir = items.filter((i) => dansLesSeptProchainsJours(i.dateRelance, aujourdhui));
    return { retard, jour, venir };
  }, [clientsQuery.data, prospectsQuery.data]);

  const kpis = summaryQuery.data?.kpis;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-primary">Tableau de bord</h1>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiTile label="Prospects chauds" value={kpis?.prospects_chauds} loading={summaryQuery.isLoading} />
        <KpiTile label="Dossiers actifs" value={kpis?.dossiers_en_cours} loading={summaryQuery.isLoading} />
        <KpiTile label="Clients au total" value={kpis?.total_clients} loading={summaryQuery.isLoading} />
        <KpiTile label="Mandats en attente de signature" value={mandatsEnAttente} loading={mandatsQuery.isLoading} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <RelancesCard
          titre="Relances en retard"
          items={relances.retard}
          loading={clientsQuery.isLoading || prospectsQuery.isLoading}
          badgeVariant="destructive"
          empty="Aucune relance en retard."
        />
        <RelancesCard
          titre="Relances du jour"
          items={relances.jour}
          loading={clientsQuery.isLoading || prospectsQuery.isLoading}
          badgeVariant="default"
          empty="Aucune relance aujourd'hui."
        />
        <RelancesCard
          titre="Relances à venir (7 jours)"
          items={relances.venir}
          loading={clientsQuery.isLoading || prospectsQuery.isLoading}
          badgeVariant="secondary"
          empty="Aucune relance à venir."
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <DossiersStagnantsCard />
        <AlertesOffresCard />
      </div>
    </div>
  );
}

function KpiTile({ label, value, loading }: { label: string; value: number | undefined; loading: boolean }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? <Skeleton className="h-8 w-16" /> : <span className="text-2xl font-bold">{value ?? 0}</span>}
      </CardContent>
    </Card>
  );
}

function RelancesCard({
  titre,
  items,
  loading,
  badgeVariant,
  empty,
}: {
  titre: string;
  items: RelanceItem[];
  loading: boolean;
  badgeVariant: "default" | "destructive" | "secondary";
  empty: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center justify-between">
          {titre}
          <Badge variant={badgeVariant}>{items.length}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-32 w-full" />
        ) : items.length === 0 ? (
          <p className="text-sm text-muted-foreground">{empty}</p>
        ) : (
          <ul className="space-y-1 max-h-64 overflow-y-auto">
            {items.map((item) => (
              <li key={`${item.type}-${item.id}`}>
                <Link
                  href={item.type === "client" ? `/clients/${item.id}` : `/prospects/${item.id}`}
                  className="flex items-center justify-between rounded-md px-2 py-1.5 text-sm hover:bg-slate-100"
                >
                  <span>{item.label}</span>
                  <span className="text-xs text-muted-foreground">{item.dateRelance}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function DossiersStagnantsCard() {
  const stagnantsQuery = useDossiersStagnants();
  const clientsQuery = clientsResource.useList();

  const clientsParId = useMemo(() => {
    const map = new Map<number, string>();
    for (const client of clientsQuery.data ?? []) {
      map.set(client.id, `${client.prenom ?? ""} ${client.nom ?? ""}`.trim());
    }
    return map;
  }, [clientsQuery.data]);

  const label = (dossier: Dossier) => clientsParId.get(dossier.client_id) || `Client #${dossier.client_id}`;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Dossiers stagnants</CardTitle>
      </CardHeader>
      <CardContent>
        {stagnantsQuery.isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : (stagnantsQuery.data ?? []).length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucun dossier stagnant.</p>
        ) : (
          <ul className="space-y-1 max-h-64 overflow-y-auto">
            {(stagnantsQuery.data ?? []).map((dossier) => (
              <li key={dossier.id}>
                <Link
                  href={`/dossiers/${dossier.id}`}
                  className="flex items-center justify-between rounded-md px-2 py-1.5 text-sm hover:bg-slate-100"
                >
                  <span>
                    {label(dossier)} — {dossier.univers}
                  </span>
                  <Badge className={statutDossierBadgeClass(dossier.statut)}>
                    {LABELS_STATUT_DOSSIER[dossier.statut as StatutDossier] ?? dossier.statut}
                  </Badge>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function AlertesOffresCard() {
  const alertesQuery = useAlertesOffresListe("en_attente");
  const clientsQuery = clientsResource.useList();
  const validerMutation = useValiderAlerteOffre();
  const rejeterMutation = useRejeterAlerteOffre();

  const clientsParId = useMemo(() => {
    const map = new Map<number, string>();
    for (const client of clientsQuery.data ?? []) {
      map.set(client.id, `${client.prenom ?? ""} ${client.nom ?? ""}`.trim());
    }
    return map;
  }, [clientsQuery.data]);

  const label = (alerte: AlerteOffre) =>
    alerte.client_id !== null ? clientsParId.get(alerte.client_id) || `Client #${alerte.client_id}` : "—";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Alertes offres moins chères</CardTitle>
      </CardHeader>
      <CardContent>
        {alertesQuery.isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : (alertesQuery.data ?? []).length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucune alerte en attente.</p>
        ) : (
          <ul className="space-y-2 max-h-64 overflow-y-auto">
            {(alertesQuery.data ?? []).map((alerte) => (
              <li key={alerte.id} className="flex items-center justify-between rounded-md px-2 py-1.5 text-sm">
                <span>
                  {label(alerte)} — économie {alerte.economie_mensuelle ?? 0} €/mois
                </span>
                <div className="flex gap-1">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={validerMutation.isPending}
                    onClick={() =>
                      validerMutation.mutate(alerte.id, { onSuccess: () => toast.success("Alerte validée.") })
                    }
                  >
                    Valider
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-destructive"
                    disabled={rejeterMutation.isPending}
                    onClick={() =>
                      rejeterMutation.mutate(alerte.id, { onSuccess: () => toast.success("Alerte rejetée.") })
                    }
                  >
                    Rejeter
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
