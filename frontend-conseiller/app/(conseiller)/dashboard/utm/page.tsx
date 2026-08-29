"use client";

import { useMemo, useState, type FormEvent } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  CheckCircle2,
  Euro,
  Percent,
  PhoneCall,
  Trash2,
  Users,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import { toast } from "sonner";

import { AdminGuard } from "@/components/layout/AdminGuard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTable } from "@/components/ui/data-table";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  useCampagnesCouts,
  useDashboardAttribution,
  useDashboardUtm,
  useDashboardUtmInscrits,
  useEnregistrerCoutCampagne,
  useSupprimerCoutCampagne,
} from "@/lib/hooks/useDashboardUtm";
import type { CampagneCout, CampagneStats, InscritUtm, ParcoursAttribution, RepartitionSource } from "@/lib/types";
import type { ColumnDef } from "@tanstack/react-table";

function isoDateJoursAvant(jours: number): string {
  const date = new Date();
  date.setDate(date.getDate() - jours);
  return date.toISOString().slice(0, 10);
}

function formatEuros(value: number | null): string {
  return value != null ? `${value.toFixed(0)} €` : "—";
}

function formatPourcentage(value: number | null): string {
  return value != null ? `${value.toFixed(1)} %` : "—";
}

interface CoutFormState {
  utm_source: string;
  utm_campaign: string;
  mois: string;
  cout: string;
  notes: string;
}

function coutFormInitial(): CoutFormState {
  return { utm_source: "", utm_campaign: "", mois: new Date().toISOString().slice(0, 7), cout: "", notes: "" };
}

export default function DashboardUtmPage() {
  const [debut, setDebut] = useState(() => isoDateJoursAvant(30));
  const [fin, setFin] = useState(() => isoDateJoursAvant(0));

  const utmQuery = useDashboardUtm(debut || undefined, fin || undefined);
  const attributionQuery = useDashboardAttribution(debut || undefined, fin || undefined);
  const inscritsQuery = useDashboardUtmInscrits(debut || undefined, fin || undefined);

  const totaux = utmQuery.data?.totaux;
  const campagnes = useMemo(() => utmQuery.data?.campagnes ?? [], [utmQuery.data]);

  const dataGraphique = useMemo(
    () =>
      [...campagnes]
        .sort((a, b) => b.leads - a.leads)
        .slice(0, 10)
        .map((campagne) => ({
          nom: campagne.utm_campaign || campagne.utm_source,
          leads: campagne.leads,
          conversions: campagne.conversions,
        })),
    [campagnes]
  );

  const columns = useMemo<ColumnDef<CampagneStats>[]>(
    () => [
      { id: "utm_source", header: "Source", accessorFn: (c) => c.utm_source },
      { id: "utm_campaign", header: "Campagne", accessorFn: (c) => c.utm_campaign || "—" },
      { id: "leads", header: "Leads", accessorFn: (c) => c.leads },
      { id: "rappels_effectues", header: "Rappels effectués", accessorFn: (c) => c.rappels_effectues },
      { id: "conversions", header: "Conversions", accessorFn: (c) => c.conversions },
      {
        id: "taux_conversion",
        header: "Taux de conversion",
        accessorFn: (c) => c.taux_conversion,
        cell: ({ row }) => formatPourcentage(row.original.taux_conversion),
      },
      {
        id: "ca_genere",
        header: "CA généré",
        accessorFn: (c) => c.ca_genere,
        cell: ({ row }) => formatEuros(row.original.ca_genere),
      },
      {
        id: "cout_pub",
        header: "Coût pub",
        accessorFn: (c) => c.cout_pub ?? 0,
        cell: ({ row }) => formatEuros(row.original.cout_pub),
      },
      {
        id: "cac",
        header: "CAC",
        accessorFn: (c) => c.cac ?? 0,
        cell: ({ row }) => formatEuros(row.original.cac),
      },
    ],
    []
  );

  const inscritsColumns = useMemo<ColumnDef<InscritUtm>[]>(
    () => [
      {
        id: "nom",
        header: "Nom",
        accessorFn: (i) => [i.prenom, i.nom].filter(Boolean).join(" ") || "—",
      },
      { id: "email", header: "E-mail", accessorFn: (i) => i.email || "—" },
      { id: "telephone", header: "Téléphone", accessorFn: (i) => i.telephone || "—" },
      { id: "ville", header: "Ville", accessorFn: (i) => i.ville || "—" },
      { id: "utm_source", header: "Source", accessorFn: (i) => i.utm_source },
      { id: "utm_campaign", header: "Campagne", accessorFn: (i) => i.utm_campaign || "—" },
      { id: "date_creation", header: "Inscrit le", accessorFn: (i) => i.date_creation || "—" },
      { id: "statut", header: "Statut", accessorFn: (i) => i.statut || "—" },
    ],
    []
  );

  return (
    <AdminGuard>
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-primary">Tunnel de conversion par UTM</h1>
        <p className="text-sm text-muted-foreground">
          Performance des campagnes payantes (TikTok, Meta, Google Ads) de la capture du lead à la conversion.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs font-medium text-muted-foreground">Début</span>
          <Input type="date" value={debut} onChange={(e) => setDebut(e.target.value)} className="w-40" />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs font-medium text-muted-foreground">Fin</span>
          <Input type="date" value={fin} onChange={(e) => setFin(e.target.value)} className="w-40" />
        </label>
        {(debut || fin) && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setDebut("");
              setFin("");
            }}
          >
            Tout l&apos;historique
          </Button>
        )}
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <KpiTile
          label="Leads"
          value={totaux != null ? String(totaux.leads) : undefined}
          loading={utmQuery.isLoading}
          icon={Users}
          iconClass="text-blue-600 bg-blue-50"
          borderClass="border-l-blue-300"
        />
        <KpiTile
          label="Rappels effectués"
          value={totaux != null ? String(totaux.rappels_effectues) : undefined}
          loading={utmQuery.isLoading}
          icon={PhoneCall}
          iconClass="text-violet-600 bg-violet-50"
          borderClass="border-l-violet-300"
        />
        <KpiTile
          label="Conversions"
          value={totaux != null ? String(totaux.conversions) : undefined}
          loading={utmQuery.isLoading}
          icon={CheckCircle2}
          iconClass="text-emerald-600 bg-emerald-50"
          borderClass="border-l-emerald-300"
        />
        <KpiTile
          label="Taux de conversion"
          value={totaux != null ? formatPourcentage(totaux.taux_conversion) : undefined}
          loading={utmQuery.isLoading}
          icon={Percent}
          iconClass="text-amber-600 bg-amber-50"
          borderClass="border-l-amber-300"
        />
        <KpiTile
          label="CA généré"
          value={totaux != null ? formatEuros(totaux.ca_genere) : undefined}
          loading={utmQuery.isLoading}
          icon={Euro}
          iconClass="text-emerald-600 bg-emerald-50"
          borderClass="border-l-emerald-300"
        />
        <KpiTile
          label="CAC"
          value={totaux != null ? formatEuros(totaux.cac) : undefined}
          loading={utmQuery.isLoading}
          icon={Wallet}
          iconClass="text-orange-600 bg-orange-50"
          borderClass="border-l-orange-300"
          hint={totaux != null && totaux.cac == null ? "aucune dépense pub renseignée" : undefined}
        />
      </div>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Leads vs conversions par campagne
        </h2>
        <Card>
          <CardContent className="pt-6">
            {utmQuery.isLoading ? (
              <Skeleton className="h-80 w-full" />
            ) : dataGraphique.length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucune campagne sur cette période.</p>
            ) : (
              <div className="utm-chart-wrap">
                <style jsx>{`
                  .utm-chart-wrap {
                    --series-leads: #2a78d6;
                    --series-conversions: #eb6834;
                    --chart-grid: #e1e0d9;
                    --chart-axis: #c3c2b7;
                    --chart-ink: #52514e;
                  }
                  :global(.dark) .utm-chart-wrap {
                    --series-leads: #3987e5;
                    --series-conversions: #d95926;
                    --chart-grid: #2c2c2a;
                    --chart-axis: #383835;
                    --chart-ink: #c3c2b7;
                  }
                `}</style>
                <ResponsiveContainer width="100%" height={320}>
                  <BarChart data={dataGraphique} margin={{ top: 8, right: 8, left: 0, bottom: 24 }}>
                    <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
                    <XAxis
                      dataKey="nom"
                      tick={{ fontSize: 11, fill: "var(--chart-ink)" }}
                      tickLine={false}
                      axisLine={{ stroke: "var(--chart-axis)" }}
                      interval={0}
                      angle={-20}
                      textAnchor="end"
                      height={50}
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: "var(--chart-ink)" }}
                      tickLine={false}
                      axisLine={false}
                      allowDecimals={false}
                      width={32}
                    />
                    <Tooltip
                      contentStyle={{
                        background: "hsl(var(--card))",
                        borderColor: "hsl(var(--border))",
                        borderRadius: 8,
                        fontSize: 12,
                      }}
                      labelStyle={{ color: "hsl(var(--foreground))", fontWeight: 600 }}
                      cursor={{ fill: "hsl(var(--muted))" }}
                    />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="leads" name="Leads" fill="var(--series-leads)" radius={[4, 4, 0, 0]} maxBarSize={24} />
                    <Bar
                      dataKey="conversions"
                      name="Conversions"
                      fill="var(--series-conversions)"
                      radius={[4, 4, 0, 0]}
                      maxBarSize={24}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Détail par campagne</h2>
        {utmQuery.isLoading ? (
          <Skeleton className="h-64 w-full" />
        ) : (
          <DataTable
            columns={columns}
            data={campagnes}
            globalFilterPlaceholder="Rechercher une source ou une campagne…"
            emptyMessage="Aucune campagne sur cette période."
            defaultSorting={[{ id: "leads", desc: true }]}
          />
        )}
      </section>

      <AttributionSection loading={attributionQuery.isLoading} data={attributionQuery.data} />

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Inscrits récents</h2>
        {inscritsQuery.isLoading ? (
          <Skeleton className="h-64 w-full" />
        ) : (
          <DataTable
            columns={inscritsColumns}
            data={inscritsQuery.data?.inscrits ?? []}
            globalFilterPlaceholder="Rechercher un inscrit (nom, e-mail, ville…)…"
            emptyMessage="Aucun inscrit sur cette période."
            defaultSorting={[{ id: "date_creation", desc: true }]}
          />
        )}
      </section>

      <DepensesPublicitairesCard />
    </div>
    </AdminGuard>
  );
}

function KpiTile({
  label,
  value,
  loading,
  icon: Icon,
  iconClass,
  borderClass,
  hint,
}: {
  label: string;
  value: string | undefined;
  loading: boolean;
  icon: LucideIcon;
  iconClass: string;
  borderClass: string;
  hint?: string;
}) {
  return (
    <Card className={`border-l-4 ${borderClass}`}>
      <CardContent className="pt-5 pb-4 flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium text-muted-foreground">{label}</p>
          {loading ? (
            <Skeleton className="h-8 w-16 mt-1" />
          ) : (
            <span className="text-2xl font-bold tracking-tight">{value ?? "—"}</span>
          )}
          {!loading && hint && <p className="text-[11px] text-muted-foreground mt-1">{hint}</p>}
        </div>
        <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${iconClass}`}>
          <Icon className="h-5 w-5" />
        </span>
      </CardContent>
    </Card>
  );
}

function AttributionSection({
  loading,
  data,
}: {
  loading: boolean;
  data:
    | {
        parcours: ParcoursAttribution[];
        par_source_premier_touch: RepartitionSource[];
        par_source_dernier_touch: RepartitionSource[];
      }
    | undefined;
}) {
  return (
    <section className="space-y-3">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        Attribution premier vs dernier contact
      </h2>
      {loading ? (
        <Skeleton className="h-48 w-full" />
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <RepartitionCard titre="Par source — premier contact" lignes={data?.par_source_premier_touch ?? []} />
            <RepartitionCard titre="Par source — dernier contact" lignes={data?.par_source_dernier_touch ?? []} />
          </div>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Parcours les plus fréquents</CardTitle>
            </CardHeader>
            <CardContent>
              {(data?.parcours ?? []).length === 0 ? (
                <p className="text-sm text-muted-foreground">Aucun parcours sur cette période.</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Parcours</TableHead>
                      <TableHead>Prospects</TableHead>
                      <TableHead>Conversions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(data?.parcours ?? []).slice(0, 8).map((p, i) => (
                      <TableRow key={`${p.premier_touch_source}-${p.dernier_touch_source}-${i}`}>
                        <TableCell>
                          {p.premier_touch_source} → {p.dernier_touch_source}
                        </TableCell>
                        <TableCell>{p.nb_prospects}</TableCell>
                        <TableCell>{p.nb_conversions}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </section>
  );
}

function RepartitionCard({ titre, lignes }: { titre: string; lignes: RepartitionSource[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{titre}</CardTitle>
      </CardHeader>
      <CardContent>
        {lignes.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucune donnée sur cette période.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Source</TableHead>
                <TableHead>Prospects</TableHead>
                <TableHead>Conversions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {lignes.map((ligne) => (
                <TableRow key={ligne.utm_source}>
                  <TableCell>{ligne.utm_source}</TableCell>
                  <TableCell>{ligne.nb_prospects}</TableCell>
                  <TableCell>{ligne.nb_conversions}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

// Saisie manuelle du coût publicitaire par (source, campagne, mois) — pas
// d'intégration live Meta/TikTok/Google Ads, c'est cette saisie qui rend le
// CAC calculable dans le tunnel ci-dessus (voir useDashboardUtm).
function DepensesPublicitairesCard() {
  const coutsQuery = useCampagnesCouts();
  const enregistrerMutation = useEnregistrerCoutCampagne();
  const supprimerMutation = useSupprimerCoutCampagne();
  const [form, setForm] = useState<CoutFormState>(() => coutFormInitial());

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const utmSource = form.utm_source.trim();
    const cout = Number(form.cout);
    if (!utmSource || !form.mois || !form.cout || Number.isNaN(cout)) {
      toast.error("Source, mois et coût sont requis.");
      return;
    }
    enregistrerMutation.mutate(
      {
        utm_source: utmSource,
        utm_campaign: form.utm_campaign.trim() || undefined,
        mois: form.mois,
        cout,
        notes: form.notes.trim() || undefined,
      },
      {
        onSuccess: () => {
          toast.success("Dépense publicitaire enregistrée.");
          setForm(coutFormInitial());
        },
      }
    );
  };

  const handleDelete = (cout: CampagneCout) => {
    if (!window.confirm(`Supprimer la dépense "${cout.utm_source}${cout.utm_campaign ? ` / ${cout.utm_campaign}` : ""} — ${cout.mois}" ?`))
      return;
    supprimerMutation.mutate(cout.id, { onSuccess: () => toast.success("Dépense supprimée.") });
  };

  return (
    <section className="space-y-3">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Dépenses publicitaires</h2>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Saisir une dépense</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <form onSubmit={handleSubmit} className="grid grid-cols-2 md:grid-cols-5 gap-3 items-end">
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-xs font-medium text-muted-foreground">Source *</span>
              <Input
                placeholder="tiktok"
                value={form.utm_source}
                onChange={(e) => setForm((f) => ({ ...f, utm_source: e.target.value }))}
                required
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-xs font-medium text-muted-foreground">Campagne</span>
              <Input
                placeholder="rentree_2026"
                value={form.utm_campaign}
                onChange={(e) => setForm((f) => ({ ...f, utm_campaign: e.target.value }))}
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-xs font-medium text-muted-foreground">Mois *</span>
              <Input
                type="month"
                value={form.mois}
                onChange={(e) => setForm((f) => ({ ...f, mois: e.target.value }))}
                required
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-xs font-medium text-muted-foreground">Coût (€) *</span>
              <Input
                type="number"
                min="0"
                step="0.01"
                placeholder="500"
                value={form.cout}
                onChange={(e) => setForm((f) => ({ ...f, cout: e.target.value }))}
                required
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-xs font-medium text-muted-foreground">Notes</span>
              <Input
                placeholder="optionnel"
                value={form.notes}
                onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
              />
            </label>
            <div className="col-span-2 md:col-span-5">
              <Button type="submit" disabled={enregistrerMutation.isPending}>
                Enregistrer
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Dépenses saisies</CardTitle>
        </CardHeader>
        <CardContent>
          {coutsQuery.isLoading ? (
            <Skeleton className="h-32 w-full" />
          ) : (coutsQuery.data ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucune dépense publicitaire renseignée.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Source</TableHead>
                  <TableHead>Campagne</TableHead>
                  <TableHead>Mois</TableHead>
                  <TableHead>Coût</TableHead>
                  <TableHead>Notes</TableHead>
                  <TableHead className="sr-only">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(coutsQuery.data ?? []).map((cout) => (
                  <TableRow key={cout.id}>
                    <TableCell>{cout.utm_source}</TableCell>
                    <TableCell>{cout.utm_campaign || "—"}</TableCell>
                    <TableCell>{cout.mois}</TableCell>
                    <TableCell>{formatEuros(cout.cout)}</TableCell>
                    <TableCell className="text-muted-foreground">{cout.notes || "—"}</TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive"
                        disabled={supprimerMutation.isPending}
                        onClick={() => handleDelete(cout)}
                      >
                        <Trash2 className="h-4 w-4" />
                        <span className="sr-only">Supprimer</span>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </section>
  );
}
