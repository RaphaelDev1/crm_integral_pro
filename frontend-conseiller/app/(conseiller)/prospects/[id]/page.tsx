"use client";

import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { ProspectForm, prospectToFormValues } from "@/components/prospects/ProspectForm";
import { ScoringPanel } from "@/components/prospects/ScoringPanel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  prospectsResource,
  useConvertirProspect,
  useEnvoyerLienDocumentsProspect,
  useGenererLienDocumentsProspect,
  useProspectDocuments,
  useProspectHistorique,
} from "@/lib/hooks/useProspects";
import type { ProspectUpdateInput } from "@/lib/schemas/prospect";

const SEUIL_CONVERSION = 40;

export default function ProspectDetailPage() {
  const params = useParams<{ id: string }>();
  const prospectId = Number(params.id);
  const router = useRouter();

  const prospectQuery = prospectsResource.useOne(prospectId);

  if (prospectQuery.isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (!prospectQuery.data) {
    return <p className="text-sm text-slate-500">Prospect introuvable.</p>;
  }

  const prospect = prospectQuery.data;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-primary">
          {prospect.prenom} {prospect.nom}
        </h1>
        {prospect.client_id != null && <Badge variant="secondary">Converti en client</Badge>}
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Tabs defaultValue="infos">
            <TabsList>
              <TabsTrigger value="infos">Infos</TabsTrigger>
              <TabsTrigger value="scoring">Scoring</TabsTrigger>
              <TabsTrigger value="documents">Documents</TabsTrigger>
              <TabsTrigger value="historique">Historique</TabsTrigger>
            </TabsList>
            <TabsContent value="infos">
              <InfosTab prospectId={prospectId} defaultValues={prospectToFormValues(prospect)} />
            </TabsContent>
            <TabsContent value="scoring">
              <ScoringPanel prospectId={prospectId} />
            </TabsContent>
            <TabsContent value="documents">
              <DocumentsTab prospectId={prospectId} />
            </TabsContent>
            <TabsContent value="historique">
              <HistoriqueTab prospectId={prospectId} />
            </TabsContent>
          </Tabs>
        </div>
        <div className="lg:col-span-1">
          <ActionsCard
            prospectId={prospectId}
            score={prospect.score}
            dejaConverti={prospect.client_id != null}
            onSuppression={() => router.push("/prospects")}
          />
        </div>
      </div>
    </div>
  );
}

function InfosTab({ prospectId, defaultValues }: { prospectId: number; defaultValues: ProspectUpdateInput }) {
  const updateMutation = prospectsResource.useUpdate({
    onSuccess: () => toast.success("Prospect mis à jour."),
  });

  return (
    <Card>
      <CardContent className="pt-6">
        <ProspectForm
          mode="edit"
          defaultValues={defaultValues}
          onSubmit={(values) => updateMutation.mutate({ id: prospectId, values: values as ProspectUpdateInput })}
          submitError={updateMutation.error}
          submitLabel="Enregistrer"
          isSubmitting={updateMutation.isPending}
        />
      </CardContent>
    </Card>
  );
}

function DocumentsTab({ prospectId }: { prospectId: number }) {
  const documentsQuery = useProspectDocuments(prospectId);

  return (
    <Card>
      <CardContent className="space-y-2 pt-6">
        {documentsQuery.isLoading ? (
          <Skeleton className="h-48 w-full" />
        ) : !documentsQuery.data?.length ? (
          <p className="text-sm text-muted-foreground">Aucun document transmis.</p>
        ) : (
          <ul className="divide-y">
            {documentsQuery.data.map((doc) => (
              <li key={doc.id} className="flex items-center justify-between py-2 text-sm">
                <div className="space-y-0.5">
                  <p className="font-medium">{doc.type_document || doc.nom_fichier || "Document"}</p>
                  <p className="text-muted-foreground">{doc.date_upload}</p>
                </div>
                <a href={doc.url} target="_blank" rel="noreferrer" className="text-primary underline">
                  Voir
                </a>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function HistoriqueTab({ prospectId }: { prospectId: number }) {
  const historiqueQuery = useProspectHistorique(prospectId);

  return (
    <Card>
      <CardContent className="pt-6">
        {historiqueQuery.isLoading ? (
          <Skeleton className="h-48 w-full" />
        ) : !historiqueQuery.data?.length ? (
          <p className="text-sm text-muted-foreground">Aucune action enregistrée.</p>
        ) : (
          <ul className="divide-y">
            {historiqueQuery.data.map((entry) => (
              <li key={entry.id} className="py-2 text-sm">
                <div className="flex justify-between">
                  <span className="font-medium">{entry.action}</span>
                  <span className="text-muted-foreground">{entry.date_action}</span>
                </div>
                {entry.details && <p className="text-muted-foreground">{entry.details}</p>}
                {entry.auteur && <p className="text-xs text-muted-foreground">Par {entry.auteur}</p>}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function ActionsCard({
  prospectId,
  score,
  dejaConverti,
  onSuppression,
}: {
  prospectId: number;
  score: number | null;
  dejaConverti: boolean;
  onSuppression: () => void;
}) {
  const router = useRouter();
  const [convertirOpen, setConvertirOpen] = useState(false);
  const [lienOpen, setLienOpen] = useState(false);
  const [lienUrl, setLienUrl] = useState<string | null>(null);

  const convertirMutation = useConvertirProspect();
  const lienMutation = useGenererLienDocumentsProspect();
  const envoyerLienMutation = useEnvoyerLienDocumentsProspect();
  const deleteMutation = prospectsResource.useDelete();

  const scoreInsuffisant = (score ?? 0) < SEUIL_CONVERSION;

  const handleConvertir = () => {
    convertirMutation.mutate(prospectId, {
      onSuccess: (client) => {
        toast.success("Prospect converti en client.");
        setConvertirOpen(false);
        router.push(`/clients/${client.id}`);
      },
    });
  };

  const handleEnvoyerLien = () => {
    lienMutation.mutate(prospectId, {
      onSuccess: (data) => {
        setLienUrl(data.url);
        setLienOpen(true);
      },
    });
  };

  const handleEnvoyerParEmail = () => {
    envoyerLienMutation.mutate(
      { prospectId, canal: "email" },
      {
        onSuccess: (data) => {
          toast.success(data.email_envoye ? "Lien envoyé par email." : "Échec de l'envoi de l'email.");
        },
      }
    );
  };

  const handleCopier = async () => {
    if (!lienUrl) return;
    await navigator.clipboard.writeText(lienUrl);
    toast.success("Lien copié.");
  };

  const handleSupprimer = () => {
    if (!window.confirm("Supprimer définitivement ce prospect ?")) return;
    deleteMutation.mutate(prospectId, { onSuccess: onSuppression });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Actions</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <span title={scoreInsuffisant ? "Score trop faible pour convertir" : undefined} className="block">
          <Button
            className="w-full"
            onClick={() => setConvertirOpen(true)}
            disabled={scoreInsuffisant || dejaConverti}
          >
            {dejaConverti ? "Déjà converti" : "Convertir en client"}
          </Button>
        </span>
        <Button variant="outline" className="w-full" onClick={handleEnvoyerLien} disabled={lienMutation.isPending}>
          Envoyer lien collecte docs
        </Button>
        <Button variant="destructive" className="w-full" onClick={handleSupprimer} disabled={deleteMutation.isPending}>
          Supprimer
        </Button>
      </CardContent>

      <Dialog open={convertirOpen} onOpenChange={setConvertirOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Convertir ce prospect en client ?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Cette action crée un client à partir des informations du prospect et redirige vers sa fiche.
          </p>
          <div className="flex justify-end">
            <Button onClick={handleConvertir} disabled={convertirMutation.isPending}>
              {convertirMutation.isPending ? "Conversion…" : "Confirmer la conversion"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={lienOpen} onOpenChange={setLienOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Lien de collecte de documents</DialogTitle>
          </DialogHeader>
          <div className="flex gap-2">
            <Input readOnly value={lienUrl ?? ""} />
            <Button onClick={handleCopier}>Copier</Button>
          </div>
          <Button variant="outline" onClick={handleEnvoyerParEmail} disabled={envoyerLienMutation.isPending}>
            {envoyerLienMutation.isPending ? "Envoi…" : "Envoyer par email"}
          </Button>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
