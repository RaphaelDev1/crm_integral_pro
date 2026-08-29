"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { ProspectForm } from "@/components/prospects/ProspectForm";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDateRelance, sortingFnDateRelance } from "@/lib/dateRelance";
import { prospectsResource } from "@/lib/hooks/useProspects";
import type { ProspectCreateInput } from "@/lib/schemas/prospect";
import type { Prospect } from "@/lib/types";

type Filtre = "chauds" | "relances_jour" | "non_convertis";

const OPTIONS_FILTRE: { valeur: Filtre; label: string }[] = [
  { valeur: "chauds", label: "Chauds uniquement" },
  { valeur: "relances_jour", label: "Relances aujourd'hui" },
  { valeur: "non_convertis", label: "Non convertis" },
];

function scoreBadgeClass(score: number | null): string {
  if (score == null) return "bg-slate-100 text-slate-600 hover:bg-slate-100";
  if (score >= 70) return "bg-emerald-100 text-emerald-800 hover:bg-emerald-100";
  if (score >= 40) return "bg-amber-100 text-amber-800 hover:bg-amber-100";
  return "bg-red-100 text-red-800 hover:bg-red-100";
}

export default function ProspectsPage() {
  const router = useRouter();
  const [createOpen, setCreateOpen] = useState(false);
  const [filtreActif, setFiltreActif] = useState<Filtre | null>(null);
  // Numéros non vérifiés (Twilio Lookup, telephone_verifie === false) masqués
  // par défaut — case à décocher pour les faire réapparaître, car un faux
  // négatif ne doit jamais faire perdre un vrai lead (voir P2.2).
  const [masquerNonVerifies, setMasquerNonVerifies] = useState(true);

  const prospectsQuery = prospectsResource.useList();
  const createMutation = prospectsResource.useCreate({
    onSuccess: (prospect) => {
      toast.success("Prospect créé.");
      setCreateOpen(false);
      router.push(`/prospects/${prospect.id}`);
    },
  });
  const deleteMutation = prospectsResource.useDelete({
    onSuccess: () => toast.success("Prospect supprimé."),
  });

  const aujourdHui = new Date().toISOString().slice(0, 10);

  const data = useMemo(() => {
    let prospects = prospectsQuery.data ?? [];
    if (masquerNonVerifies) prospects = prospects.filter((p) => p.telephone_verifie !== false);
    if (filtreActif === "chauds") return prospects.filter((p) => (p.score ?? 0) >= 70);
    if (filtreActif === "relances_jour") return prospects.filter((p) => p.date_relance === aujourdHui);
    if (filtreActif === "non_convertis") return prospects.filter((p) => p.client_id == null);
    return prospects;
  }, [prospectsQuery.data, filtreActif, aujourdHui, masquerNonVerifies]);

  const columns = useMemo<ColumnDef<Prospect>[]>(
    () => [
      {
        id: "ref",
        header: "Référence",
        accessorFn: (prospect) => prospect.ref || "—",
      },
      {
        id: "nom",
        header: "Nom",
        accessorFn: (prospect) => `${prospect.prenom ?? ""} ${prospect.nom ?? ""}`.trim(),
        cell: ({ row }) => (
          <div className="flex items-center gap-2">
            <span>{`${row.original.prenom ?? ""} ${row.original.nom ?? ""}`.trim() || "—"}</span>
            {row.original.telephone_verifie === false && (
              <Badge variant="outline" className="bg-amber-100 text-amber-800 hover:bg-amber-100">
                ⚠️ Numéro non vérifié
              </Badge>
            )}
          </div>
        ),
      },
      {
        id: "score",
        header: "Score",
        cell: ({ row }) => (
          <Badge variant="outline" className={scoreBadgeClass(row.original.score)}>
            {row.original.score != null ? row.original.score.toFixed(0) : "—"}
          </Badge>
        ),
      },
      {
        id: "economie_estimee_an",
        header: "Économie estimée",
        accessorFn: (prospect) => prospect.economie_estimee_an ?? 0,
        cell: ({ row }) =>
          row.original.economie_estimee_an != null ? `${row.original.economie_estimee_an.toFixed(0)} €/an` : "—",
      },
      {
        id: "prochaine_relance",
        header: "Prochaine relance",
        // Inclut le statut dans la valeur de recherche globale (affiché en
        // dessous de la date dans la cellule) — voir la demande de recherche
        // sur SCORE / DATE RELANCE / nom / prénom / ÉCONOMIE / STATUT.
        accessorFn: (prospect) => `${prospect.date_relance ?? ""} ${prospect.statut ?? ""}`.trim(),
        sortingFn: sortingFnDateRelance,
        cell: ({ row }) => (
          <div className="space-y-0.5">
            <div>{formatDateRelance(row.original.date_relance)}</div>
            {row.original.statut && <div className="text-xs text-muted-foreground">{row.original.statut}</div>}
          </div>
        ),
      },
    ],
    []
  );

  const handleDelete = (prospect: Prospect) => {
    if (!window.confirm(`Supprimer ${prospect.prenom ?? ""} ${prospect.nom ?? ""} ?`)) return;
    deleteMutation.mutate(prospect.id);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-primary">Prospects</h1>
        <Button onClick={() => setCreateOpen(true)}>Nouveau prospect</Button>
      </div>

      <div className="flex items-center gap-2">
        <Button variant={filtreActif === null ? "default" : "outline"} size="sm" onClick={() => setFiltreActif(null)}>
          Tous
        </Button>
        {OPTIONS_FILTRE.map((option) => (
          <Button
            key={option.valeur}
            variant={filtreActif === option.valeur ? "default" : "outline"}
            size="sm"
            onClick={() => setFiltreActif((prev) => (prev === option.valeur ? null : option.valeur))}
          >
            {option.label}
          </Button>
        ))}
        <label className="ml-2 flex cursor-pointer items-center gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={masquerNonVerifies}
            onChange={(e) => setMasquerNonVerifies(e.target.checked)}
            className="h-4 w-4 rounded border-slate-300"
          />
          Masquer les numéros non vérifiés
        </label>
      </div>

      {prospectsQuery.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : (
        <DataTable
          columns={columns}
          data={data}
          globalFilterPlaceholder="Rechercher un prospect…"
          emptyMessage="Aucun prospect pour le moment."
          defaultSorting={[{ id: "prochaine_relance", desc: false }]}
          onRowClick={(prospect) => router.push(`/prospects/${prospect.id}`)}
          rowActions={(prospect) => (
            <>
              <DropdownMenuItem onSelect={() => router.push(`/prospects/${prospect.id}`)}>
                Voir la fiche
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => handleDelete(prospect)} className="text-destructive">
                Supprimer
              </DropdownMenuItem>
            </>
          )}
        />
      )}

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nouveau prospect</DialogTitle>
          </DialogHeader>
          <ProspectForm
            mode="create"
            defaultValues={{ prenom: "", nom: "", telephone: "", email: "", ville: "", origine: "Manuel" } as ProspectCreateInput}
            onSubmit={(values) => createMutation.mutate(values as ProspectCreateInput)}
            submitError={createMutation.error}
            submitLabel="Créer"
            isSubmitting={createMutation.isPending}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}
