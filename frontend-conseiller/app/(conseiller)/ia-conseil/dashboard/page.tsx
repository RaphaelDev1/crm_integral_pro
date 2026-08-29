"use client";

import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AlertTriangle, Euro, FolderKanban, Wallet, type LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/contexts/AuthContext";
import { useAntiBiaisCommercial, useDashboardIaConseil } from "@/lib/hooks/useIaConseil";
import type { PipelineSouscriptions } from "@/lib/types-ia-conseil";

function formatEuros(value: number): string {
  return `${value.toFixed(0)} €`;
}

const LABELS_PIPELINE: Record<keyof PipelineSouscriptions, string> = {
  en_attente: "En attente",
  active: "Active",
  resiliee: "Résiliée",
  annulee: "Annulée",
};

// Dashboard conseiller enrichi (§2.5) — calqué sur dashboard/utm/page.tsx
// (KpiTile, thème clair/sombre via variables CSS pour le graphique).
export default function DashboardIaConseilPage() {
  const { estAdmin } = useAuth();
  const resumeQuery = useDashboardIaConseil();
  const antiBiaisQuery = useAntiBiaisCommercial();

  const resume = resumeQuery.data;

  const dataCommissions = useMemo(
    () => (resume?.commissions_mensuelles ?? []).map((c) => ({ mois: c.mois, Prévue: c.prevue, Encaissée: c.encaissee })),
    [resume]
  );

  const commissionsDuMois = resume?.commissions_mensuelles.at(-1);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-primary">Dashboard IA Conseil</h1>
        <p className="text-sm text-muted-foreground">Économies générées, pipeline de souscriptions et commissions.</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiTile
          label="Économies générées (année)"
          value={resume ? formatEuros(resume.economies_ytd_total) : undefined}
          loading={resumeQuery.isLoading}
          icon={Euro}
          iconClass="text-emerald-600 bg-emerald-50"
          borderClass="border-l-emerald-300"
        />
        <KpiTile
          label="Souscriptions actives"
          value={resume ? String(resume.pipeline.active) : undefined}
          loading={resumeQuery.isLoading}
          icon={FolderKanban}
          iconClass="text-blue-600 bg-blue-50"
          borderClass="border-l-blue-300"
        />
        <KpiTile
          label="Relances à venir"
          value={resume ? String(resume.alertes_clients.length) : undefined}
          loading={resumeQuery.isLoading}
          icon={AlertTriangle}
          iconClass="text-amber-600 bg-amber-50"
          borderClass="border-l-amber-300"
        />
        <KpiTile
          label="Commissions du mois"
          value={commissionsDuMois ? formatEuros(commissionsDuMois.prevue) : undefined}
          loading={resumeQuery.isLoading}
          icon={Wallet}
          iconClass="text-violet-600 bg-violet-50"
          borderClass="border-l-violet-300"
        />
      </div>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Commissions par mois</h2>
        <Card>
          <CardContent className="pt-6">
            {resumeQuery.isLoading ? (
              <Skeleton className="h-72 w-full" />
            ) : dataCommissions.length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucune souscription datée pour l&apos;instant.</p>
            ) : (
              <div className="commissions-chart-wrap">
                <style jsx>{`
                  .commissions-chart-wrap {
                    --series-prevue: #2a78d6;
                    --series-encaissee: #2f9e6b;
                    --chart-grid: #e1e0d9;
                    --chart-axis: #c3c2b7;
                    --chart-ink: #52514e;
                  }
                  :global(.dark) .commissions-chart-wrap {
                    --series-prevue: #3987e5;
                    --series-encaissee: #3ab57e;
                    --chart-grid: #2c2c2a;
                    --chart-axis: #383835;
                    --chart-ink: #c3c2b7;
                  }
                `}</style>
                <ResponsiveContainer width="100%" height={288}>
                  <BarChart data={dataCommissions} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
                    <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
                    <XAxis dataKey="mois" tick={{ fontSize: 11, fill: "var(--chart-ink)" }} tickLine={false} axisLine={{ stroke: "var(--chart-axis)" }} />
                    <YAxis tick={{ fontSize: 11, fill: "var(--chart-ink)" }} tickLine={false} axisLine={false} width={48} />
                    <Tooltip
                      contentStyle={{ background: "hsl(var(--card))", borderColor: "hsl(var(--border))", borderRadius: 8, fontSize: 12 }}
                      labelStyle={{ color: "hsl(var(--foreground))", fontWeight: 600 }}
                      cursor={{ fill: "hsl(var(--muted))" }}
                    />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="Prévue" fill="var(--series-prevue)" radius={[4, 4, 0, 0]} maxBarSize={32} />
                    <Bar dataKey="Encaissée" fill="var(--series-encaissee)" radius={[4, 4, 0, 0]} maxBarSize={32} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Pipeline de souscriptions</h2>
        {resumeQuery.isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {(Object.keys(LABELS_PIPELINE) as (keyof PipelineSouscriptions)[]).map((statut) => (
              <Card key={statut}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">{LABELS_PIPELINE[statut]}</CardTitle>
                </CardHeader>
                <CardContent>
                  <span className="text-2xl font-bold tracking-tight">{resume?.pipeline[statut] ?? 0}</span>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Relances planifiées à venir</h2>
        <Card>
          <CardContent className="pt-6">
            {resumeQuery.isLoading ? (
              <Skeleton className="h-32 w-full" />
            ) : (resume?.alertes_clients ?? []).length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucune relance planifiée à venir.</p>
            ) : (
              <ul className="space-y-1">
                {(resume?.alertes_clients ?? []).map((alerte) => (
                  <li key={alerte.id} className="flex items-center justify-between rounded-md px-2 py-1.5 text-sm">
                    <span>{alerte.type}</span>
                    <span className="text-muted-foreground">{alerte.date_prevue}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </section>

      {estAdmin() && (
        <section className="space-y-3" id="anti-biais">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Audit anti-biais commercial</h2>
          <Card>
            <CardContent className="pt-6">
              {antiBiaisQuery.isLoading ? (
                <Skeleton className="h-32 w-full" />
              ) : (antiBiaisQuery.data ?? []).length === 0 ? (
                <p className="text-sm text-muted-foreground">Aucune souscription rattachée à une session pour l&apos;instant.</p>
              ) : (
                <ul className="space-y-2">
                  {(antiBiaisQuery.data ?? []).map((ligne) => (
                    <li key={ligne.conseiller_id ?? "inconnu"} className="flex items-center justify-between rounded-md px-2 py-1.5 text-sm">
                      <span>
                        Conseiller #{ligne.conseiller_id ?? "?"} — {ligne.nb_biais_possible}/{ligne.nb_souscriptions_avec_session}{" "}
                        souscriptions à risque ({(ligne.ratio * 100).toFixed(0)}%)
                      </span>
                      {ligne.au_dela_du_seuil && <Badge variant="destructive">Au-delà du seuil</Badge>}
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </section>
      )}
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
  value: string | undefined;
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
          {loading ? <Skeleton className="h-8 w-16 mt-1" /> : <span className="text-2xl font-bold tracking-tight">{value ?? "—"}</span>}
        </div>
        <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${iconClass}`}>
          <Icon className="h-5 w-5" />
        </span>
      </CardContent>
    </Card>
  );
}
