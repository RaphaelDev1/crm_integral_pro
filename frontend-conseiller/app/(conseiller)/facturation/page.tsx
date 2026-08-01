"use client";

import type { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { AnalyseFactureForm } from "@/components/factures/AnalyseFactureForm";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { DataTable } from "@/components/ui/data-table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { clientsResource } from "@/lib/hooks/useClients";
import { dossiersResource } from "@/lib/hooks/useDossiers";
import { useMandatsHonorairesListe, useMarquerSigneHonoraires } from "@/lib/hooks/useHonoraires";
import type { MandatHonoraires } from "@/lib/types";

export default function FacturationPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-primary">Facturation</h1>
      <Tabs defaultValue="honoraires">
        <TabsList>
          <TabsTrigger value="honoraires">Devis d&apos;honoraires</TabsTrigger>
          <TabsTrigger value="factures">Analyse de factures</TabsTrigger>
        </TabsList>
        <TabsContent value="honoraires">
          <DevisHonorairesTab />
        </TabsContent>
        <TabsContent value="factures">
          <AnalyseFactureForm />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function DevisHonorairesTab() {
  const [signerCible, setSignerCible] = useState<MandatHonoraires | null>(null);
  const [signataire, setSignataire] = useState("");

  const mandatsQuery = useMandatsHonorairesListe();
  const dossiersQuery = dossiersResource.useList();
  const clientsQuery = clientsResource.useList();
  const signerMutation = useMarquerSigneHonoraires();

  const dossiersParId = useMemo(() => {
    const map = new Map<number, { client_id: number; univers: string }>();
    for (const dossier of dossiersQuery.data ?? []) {
      map.set(dossier.id, { client_id: dossier.client_id, univers: dossier.univers });
    }
    return map;
  }, [dossiersQuery.data]);

  const clientsParId = useMemo(() => {
    const map = new Map<number, string>();
    for (const client of clientsQuery.data ?? []) {
      map.set(client.id, `${client.prenom ?? ""} ${client.nom ?? ""}`.trim());
    }
    return map;
  }, [clientsQuery.data]);

  const handleSigner = () => {
    if (!signerCible) return;
    signerMutation.mutate(
      { dossierId: signerCible.dossier_id, signataire },
      {
        onSuccess: () => {
          toast.success("Mandat marqué comme signé.");
          setSignerCible(null);
          setSignataire("");
        },
      }
    );
  };

  const columns = useMemo<ColumnDef<MandatHonoraires>[]>(
    () => [
      {
        id: "client",
        header: "Client",
        accessorFn: (m) => clientsParId.get(dossiersParId.get(m.dossier_id)?.client_id ?? -1) || "—",
      },
      { id: "univers", header: "Univers", accessorFn: (m) => dossiersParId.get(m.dossier_id)?.univers || "—" },
      { accessorKey: "montant", header: "Montant (€)" },
      { accessorKey: "taux", header: "Taux (%)" },
      {
        id: "statut",
        header: "Statut",
        cell: ({ row }) => (
          <Badge variant={row.original.statut === "signe" ? "default" : "secondary"}>{row.original.statut}</Badge>
        ),
      },
    ],
    [clientsParId, dossiersParId]
  );

  return (
    <Card>
      <CardContent className="pt-6">
        {mandatsQuery.isLoading ? (
          <Skeleton className="h-64 w-full" />
        ) : (
          <DataTable
            columns={columns}
            data={mandatsQuery.data ?? []}
            emptyMessage="Aucun mandat d'honoraires pour le moment."
            rowActions={(mandat) => (
              <>
                <DropdownMenuItem asChild>
                  <Link href={`/dossiers/${mandat.dossier_id}`}>Voir le dossier</Link>
                </DropdownMenuItem>
                {mandat.statut !== "signe" && (
                  <DropdownMenuItem onSelect={() => setSignerCible(mandat)}>Marquer signé</DropdownMenuItem>
                )}
              </>
            )}
          />
        )}

        <Dialog open={signerCible !== null} onOpenChange={(open) => !open && setSignerCible(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Marquer le mandat comme signé</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Signataire</Label>
                <Input value={signataire} onChange={(e) => setSignataire(e.target.value)} />
              </div>
              <div className="flex justify-end">
                <Button onClick={handleSigner} disabled={signerMutation.isPending || !signataire}>
                  {signerMutation.isPending ? "Enregistrement…" : "Confirmer"}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
}
