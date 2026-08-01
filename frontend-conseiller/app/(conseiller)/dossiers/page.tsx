"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { AlertTriangle } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { DataTable } from "@/components/ui/data-table";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { clientsResource } from "@/lib/hooks/useClients";
import { dossiersResource, useDossiersStagnants } from "@/lib/hooks/useDossiers";
import { LABELS_STATUT_DOSSIER, STATUTS_DOSSIER, statutDossierBadgeClass } from "@/lib/dossierStatuts";
import type { Dossier } from "@/lib/types";

const TOUS_LES_STATUTS = "__tous__";

export default function DossiersPage() {
  const router = useRouter();
  const [statutFiltre, setStatutFiltre] = useState<string>(TOUS_LES_STATUTS);

  const dossiersQuery = dossiersResource.useList(
    statutFiltre === TOUS_LES_STATUTS ? undefined : { statut: statutFiltre }
  );
  const clientsQuery = clientsResource.useList();
  const stagnantsQuery = useDossiersStagnants();

  const clientsParId = useMemo(() => {
    const map = new Map<number, string>();
    for (const client of clientsQuery.data ?? []) {
      map.set(client.id, `${client.prenom ?? ""} ${client.nom ?? ""}`.trim());
    }
    return map;
  }, [clientsQuery.data]);

  const idsStagnants = useMemo(
    () => new Set((stagnantsQuery.data ?? []).map((d) => d.id)),
    [stagnantsQuery.data]
  );

  const columns = useMemo<ColumnDef<Dossier>[]>(
    () => [
      {
        id: "client",
        header: "Client",
        accessorFn: (dossier) => clientsParId.get(dossier.client_id) || `#${dossier.client_id}`,
      },
      { accessorKey: "univers", header: "Type" },
      {
        id: "statut",
        header: "État",
        cell: ({ row }) => (
          <div className="flex items-center gap-2">
            <Badge variant="outline" className={statutDossierBadgeClass(row.original.statut)}>
              {LABELS_STATUT_DOSSIER[row.original.statut as keyof typeof LABELS_STATUT_DOSSIER] ?? row.original.statut}
            </Badge>
            {idsStagnants.has(row.original.id) && <AlertTriangle className="h-4 w-4 text-amber-500" />}
          </div>
        ),
      },
      { accessorKey: "date_derniere_transition", header: "Dernière transition" },
    ],
    [clientsParId, idsStagnants]
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-primary">Dossiers</h1>
        <Select value={statutFiltre} onValueChange={setStatutFiltre}>
          <SelectTrigger className="w-64">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={TOUS_LES_STATUTS}>Tous les statuts</SelectItem>
            {STATUTS_DOSSIER.map((statut) => (
              <SelectItem key={statut} value={statut}>
                {LABELS_STATUT_DOSSIER[statut]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {!!stagnantsQuery.data?.length && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>{stagnantsQuery.data.length} dossier(s) stagnant(s)</AlertTitle>
          <AlertDescription>
            {stagnantsQuery.data.map((dossier, index) => (
              <span key={dossier.id}>
                {index > 0 && ", "}
                <Link href={`/dossiers/${dossier.id}`} className="underline">
                  #{dossier.id} ({clientsParId.get(dossier.client_id) || `client #${dossier.client_id}`})
                </Link>
              </span>
            ))}
          </AlertDescription>
        </Alert>
      )}

      {dossiersQuery.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : (
        <DataTable
          columns={columns}
          data={dossiersQuery.data ?? []}
          globalFilterPlaceholder="Rechercher un dossier…"
          emptyMessage="Aucun dossier pour le moment."
          onRowClick={(dossier) => router.push(`/dossiers/${dossier.id}`)}
          rowActions={(dossier) => (
            <DropdownMenuItem onSelect={() => router.push(`/dossiers/${dossier.id}`)}>
              Voir la fiche
            </DropdownMenuItem>
          )}
        />
      )}
    </div>
  );
}
