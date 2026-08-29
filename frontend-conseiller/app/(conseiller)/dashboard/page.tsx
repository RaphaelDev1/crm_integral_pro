"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Flame,
  FolderKanban,
  Users,
  FileSignature,
  type LucideIcon,
} from "lucide-react";
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
    // Les clients sont poussés avant les prospects : la file du dashboard doit
    // prioriser les clients (voir demande produit), et le tri clients-avant-
    // prospects reste stable puisque Array.filter() préserve l'ordre.
    const items: RelanceItem[] = [];
    for (const client of clientsQuery.data ?? []) {
      items.push({
        id: client.id,
        type: "client",
        label: `${client.prenom ?? ""} ${client.nom ?? ""}`.trim() || `Client #${client.id}`,
        ref: client.ref,
        theme: null,
        score: null,
        economieEstimeeAn: client.economie_estimee_an,
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
        ref: prospect.ref,
        theme: prospect.service_principal || prospect.univers_interesse || null,
        score: prospect.score,
        economieEstimeeAn: prospect.economie_estimee_an,
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
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-primary">Tableau de bord</h1>
        <p className="text-sm text-muted-foreground">Vue d&apos;ensemble de votre activité du jour.</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiTile
          label="Prospects chauds"
          value={kpis?.prospects_chauds}
          loading={summaryQuery.isLoading}
          icon={Flame}
          iconClass="text-orange-600 bg-orange-50"
          borderClass="border-l-orange-300"
        />
        <KpiTile
          label="Dossiers actifs"
          value={kpis?.dossiers_en_cours}
          loading={summaryQuery.isLoading}
          icon={FolderKanban}
          iconClass="text-blue-600 bg-blue-50"
          borderClass="border-l-blue-300"
        />
        <KpiTile
          label="Clients au total"
          value={kpis?.total_clients}
          loading={summaryQuery.isLoading}
          icon={Users}
          iconClass="text-emerald-600 bg-emerald-50"
          borderClass="border-l-emerald-300"
        />
        <KpiTile
          label="Mandats en attente de signature"
          value={mandatsEnAttente}
          loading={mandatsQuery.isLoading}
          icon={FileSignature}
          iconClass="text-violet-600 bg-violet-50"
          borderClass="border-l-violet-300"
        />
      </div>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Relances</h2>
        <RelanceQueueCard
          groupes={[
            { cle: "retard", titre: "Relances en retard", items: relances.retard, badgeVariant: "destructive", empty: "Aucune relance en retard.", ouvertParDefaut: true },
            { cle: "jour", titre: "Relances du jour", items: relances.jour, badgeVariant: "default", empty: "Aucune relance aujourd'hui.", ouvertParDefaut: true },
            { cle: "venir", titre: "Relances à venir (7 jours)", items: relances.venir, badgeVariant: "secondary", empty: "Aucune relance à venir.", ouvertParDefaut: true },
          ]}
          loading={clientsQuery.isLoading || prospectsQuery.isLoading}
        />
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Suivi</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <DossiersStagnantsCard />
          <AlertesOffresCard />
        </div>
      </section>
    </div>
  );
}

function KpiTile({
  label,
  value,
  loading,
  icon: Icon,
  iconClass,
  borderClass,
}: {
  label: string;
  value: number | undefined;
  loading: boolean;
  icon: LucideIcon;
  iconClass: string;
  borderClass: string;
}) {
  return (
    <Card className={`border-l-4 ${borderClass}`}>
      <CardContent className="pt-5 pb-4 flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium text-muted-foreground">{label}</p>
          {loading ? (
            <Skeleton className="h-8 w-16 mt-1" />
          ) : (
            <span className="text-3xl font-bold tracking-tight">{value ?? 0}</span>
          )}
        </div>
        <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${iconClass}`}>
          <Icon className="h-5 w-5" />
        </span>
      </CardContent>
    </Card>
  );
}

interface GroupeRelance {
  cle: string;
  titre: string;
  items: RelanceItem[];
  badgeVariant: "default" | "destructive" | "secondary";
  empty: string;
  ouvertParDefaut: boolean;
}

function formatDateRelance(iso: string): string {
  if (!iso) return "—";
  const [annee, mois, jour] = iso.split("-");
  if (!annee || !mois || !jour) return iso;
  return `${jour}/${mois}/${annee}`;
}

// dossier.date_creation est déjà au format "JJ/MM/AAAA HH:MM" (voir
// backend/models/dossier.py) — on ne garde que la date pour l'affichage.
function formatDateCreationDossier(dateCreation: string | null): string {
  if (!dateCreation) return "—";
  return dateCreation.split(" ")[0];
}

function scorePastilleClass(score: number | null): string {
  if (score == null) return "border-slate-200 bg-slate-100 text-slate-500";
  if (score >= 70) return "border-emerald-300 bg-emerald-100 text-emerald-800";
  if (score >= 40) return "border-amber-300 bg-amber-100 text-amber-800";
  return "border-red-300 bg-red-100 text-red-800";
}

// Pastille de score volontairement plus grande que le reste des badges de la
// ligne — c'est l'information la plus utile pour prioriser un coup de fil.
function ScorePastille({ score }: { score: number | null }) {
  return (
    <span
      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full border-2 text-base font-bold ${scorePastilleClass(score)}`}
    >
      {score != null ? score.toFixed(0) : "—"}
    </span>
  );
}

// Une seule carte, groupes repliables — chaque groupe qui s'ouvre pousse les
// suivants plus bas dans le flux normal du document (pas de tableau flottant).
function RelanceQueueCard({ groupes, loading }: { groupes: GroupeRelance[]; loading: boolean }) {
  const [ouverts, setOuverts] = useState<Set<string>>(
    () => new Set(groupes.filter((g) => g.ouvertParDefaut).map((g) => g.cle))
  );

  const toggle = (cle: string) => {
    setOuverts((prev) => {
      const next = new Set(prev);
      if (next.has(cle)) next.delete(cle);
      else next.add(cle);
      return next;
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">À traiter</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {loading ? (
          <Skeleton className="h-48 w-full" />
        ) : (
          groupes.map((groupe) => {
            const estOuvert = ouverts.has(groupe.cle);
            return (
              <div key={groupe.cle} className="rounded-md border">
                <button
                  type="button"
                  onClick={() => toggle(groupe.cle)}
                  className="flex w-full items-center justify-between px-3 py-2 text-left hover:bg-slate-900/5 dark:hover:bg-white/10"
                >
                  <span className="flex items-center gap-2 font-medium text-sm">
                    {estOuvert ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                    {groupe.titre}
                  </span>
                  <Badge variant={groupe.badgeVariant}>{groupe.items.length}</Badge>
                </button>
                {estOuvert && (
                  <div className="border-t px-3 py-2">
                    {groupe.items.length === 0 ? (
                      <p className="text-sm text-muted-foreground py-1">{groupe.empty}</p>
                    ) : (
                      <ul className="divide-y">
                        {groupe.items.map((item) => (
                          <li key={`${item.type}-${item.id}`}>
                            <Link
                              href={item.type === "client" ? `/clients/${item.id}` : `/prospects/${item.id}`}
                              className="flex flex-wrap items-center gap-3 py-3 text-sm hover:bg-slate-900/5 dark:hover:bg-white/10 rounded-md px-2"
                            >
                              <ScorePastille score={item.score} />
                              <Badge variant={item.type === "client" ? "default" : "outline"} className="shrink-0">
                                {item.type === "client" ? "Client" : "Prospect"}
                              </Badge>
                              <span className="flex-1 min-w-[10rem]">
                                <span className="block font-medium leading-tight">{item.label}</span>
                                <span className="block text-xs text-muted-foreground leading-tight">
                                  {item.ref || "—"}
                                  {item.statutRelance ? ` · ${item.statutRelance}` : ""}
                                </span>
                              </span>
                              <span className="hidden sm:flex shrink-0 w-32 items-center justify-center truncate rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
                                {item.theme || "—"}
                              </span>
                              <span className="shrink-0 w-28 rounded-full bg-emerald-100 px-2.5 py-1 text-center text-xs font-bold text-emerald-800">
                                {item.economieEstimeeAn != null ? `${item.economieEstimeeAn.toFixed(0)} €/an` : "—"}
                              </span>
                              <span className="shrink-0 w-24 rounded-full bg-amber-100 px-2.5 py-1 text-center text-xs font-bold text-amber-800">
                                {formatDateRelance(item.dateRelance)}
                              </span>
                            </Link>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}

function DossiersStagnantsCard() {
  const stagnantsQuery = useDossiersStagnants();
  const clientsQuery = clientsResource.useList();

  const refsParId = useMemo(() => {
    const map = new Map<number, string>();
    for (const client of clientsQuery.data ?? []) {
      map.set(client.id, client.ref || `#${client.id}`);
    }
    return map;
  }, [clientsQuery.data]);

  const ref = (dossier: Dossier) => refsParId.get(dossier.client_id) || `#${dossier.client_id}`;

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
          // Déjà trié par économie annuelle décroissante puis par date de
          // création croissante côté backend (dossier_engine.dossiers_stagnants)
          // — les dossiers les plus rentables, et parmi eux les plus anciens,
          // apparaissent en premier.
          <ul className="space-y-1 max-h-64 overflow-y-auto">
            {(stagnantsQuery.data ?? []).map((dossier) => (
              <li key={dossier.id}>
                <Link
                  href={`/dossiers/${dossier.id}`}
                  className="flex items-center justify-between gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-slate-100"
                >
                  <span className="flex items-center gap-2 min-w-0">
                    <span className="font-medium shrink-0">{ref(dossier)}</span>
                    <span className="text-muted-foreground truncate">{dossier.univers}</span>
                    <span className="text-xs text-muted-foreground shrink-0">
                      créé le {formatDateCreationDossier(dossier.date_creation)}
                    </span>
                  </span>
                  <span className="flex items-center gap-2 shrink-0">
                    <span className="text-emerald-700 font-medium">
                      {(dossier.economie_annuelle_estimee ?? 0).toFixed(0)} €/an
                    </span>
                    <Badge className={statutDossierBadgeClass(dossier.statut)}>
                      {LABELS_STATUT_DOSSIER[dossier.statut as StatutDossier] ?? dossier.statut}
                    </Badge>
                  </span>
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
