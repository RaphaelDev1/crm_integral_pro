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
import { prospectsResource } from "@/lib/hooks/useProspects";
import type { ProspectCreateInput } from "@/lib/schemas/prospect";
import type { Prospect } from "@/lib/types";

type Filtre = "chauds" | "relances_jour" | "non_convertis";

function scoreBadgeClass(score: number | null): string {
  if (score == null) return "bg-slate-100 text-slate-600 hover:bg-slate-100";
  if (score >= 70) return "bg-emerald-100 text-emerald-800 hover:bg-emerald-100";
  if (score >= 40) return "bg-amber-100 text-amber-800 hover:bg-amber-100";
  return "bg-red-100 text-red-800 hover:bg-red-100";
}

export default function ProspectsPage() {
  const router = useRouter();
  const [createOpen, setCreateOpen] = useState(false);
  const [filtresActifs, setFiltresActifs] = useState<Set<Filtre>>(new Set());

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

  const toggleFiltre = (filtre: Filtre) => {
    setFiltresActifs((prev) => {
      const next = new Set(prev);
      if (next.has(filtre)) next.delete(filtre);
      else next.add(filtre);
      return next;
    });
  };

  const aujourdHui = new Date().toISOString().slice(0, 10);

  const data = useMemo(() => {
    let prospects = prospectsQuery.data ?? [];
    if (filtresActifs.has("chauds")) prospects = prospects.filter((p) => (p.score ?? 0) >= 70);
    if (filtresActifs.has("relances_jour")) prospects = prospects.filter((p) => p.date_relance === aujourdHui);
    if (filtresActifs.has("non_convertis")) prospects = prospects.filter((p) => p.client_id == null);
    return prospects;
  }, [prospectsQuery.data, filtresActifs, aujourdHui]);

  const columns = useMemo<ColumnDef<Prospect>[]>(
    () => [
      {
        id: "nom",
        header: "Nom",
        accessorFn: (prospect) => `${prospect.prenom ?? ""} ${prospect.nom ?? ""}`.trim(),
      },
      { accessorKey: "origine", header: "Origine" },
      {
        id: "score",
        header: "Score",
        cell: ({ row }) => (
          <Badge variant="outline" className={scoreBadgeClass(row.original.score)}>
            {row.original.score != null ? row.original.score.toFixed(0) : "—"}
          </Badge>
        ),
      },
      { accessorKey: "date_relance", header: "Date relance" },
      {
        id: "statut",
        header: "Statut",
        cell: ({ row }) => <Badge variant="secondary">{row.original.statut || "—"}</Badge>,
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

      <div className="flex gap-2">
        <Button
          variant={filtresActifs.has("chauds") ? "default" : "outline"}
          size="sm"
          onClick={() => toggleFiltre("chauds")}
        >
          Chauds uniquement
        </Button>
        <Button
          variant={filtresActifs.has("relances_jour") ? "default" : "outline"}
          size="sm"
          onClick={() => toggleFiltre("relances_jour")}
        >
          Relances aujourd&apos;hui
        </Button>
        <Button
          variant={filtresActifs.has("non_convertis") ? "default" : "outline"}
          size="sm"
          onClick={() => toggleFiltre("non_convertis")}
        >
          Non convertis
        </Button>
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
