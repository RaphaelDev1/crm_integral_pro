"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { UserForm, userToFormValues } from "@/components/admin/UserForm";
import { AdminGuard } from "@/components/layout/AdminGuard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { usersResource } from "@/lib/hooks/useUsers";
import type { UserCreateInput, UserUpdateInput } from "@/lib/schemas/user";
import type { User } from "@/lib/types";

export default function UtilisateursPage() {
  const [createOpen, setCreateOpen] = useState(false);
  const [editCible, setEditCible] = useState<User | null>(null);

  const usersQuery = usersResource.useList();
  const createMutation = usersResource.useCreate({
    onSuccess: () => {
      toast.success("Utilisateur créé.");
      setCreateOpen(false);
    },
  });
  const updateMutation = usersResource.useUpdate({
    onSuccess: () => {
      toast.success("Utilisateur mis à jour.");
      setEditCible(null);
    },
  });

  const handleToggleActif = (user: User) => {
    updateMutation.mutate({ id: user.id, values: { actif: !user.actif } });
  };

  const columns = useMemo<ColumnDef<User>[]>(
    () => [
      { accessorKey: "username", header: "Identifiant" },
      { accessorKey: "nom_complet", header: "Nom complet" },
      {
        id: "role",
        header: "Rôle",
        cell: ({ row }) => <Badge variant={row.original.role === "Admin" ? "default" : "secondary"}>{row.original.role}</Badge>,
      },
      {
        id: "actif",
        header: "Statut",
        cell: ({ row }) => (
          <Badge variant={row.original.actif ? "default" : "destructive"}>{row.original.actif ? "Actif" : "Désactivé"}</Badge>
        ),
      },
    ],
    []
  );

  return (
    <AdminGuard>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold text-primary">Utilisateurs</h1>
          <Button onClick={() => setCreateOpen(true)}>Nouvel utilisateur</Button>
        </div>

        {usersQuery.isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-64 w-full" />
          </div>
        ) : (
          <DataTable
            columns={columns}
            data={usersQuery.data ?? []}
            globalFilterPlaceholder="Rechercher un utilisateur…"
            emptyMessage="Aucun utilisateur pour le moment."
            rowActions={(user) => (
              <>
                <DropdownMenuItem onSelect={() => setEditCible(user)}>Modifier</DropdownMenuItem>
                <DropdownMenuItem onSelect={() => handleToggleActif(user)} className={user.actif ? "text-destructive" : undefined}>
                  {user.actif ? "Désactiver" : "Réactiver"}
                </DropdownMenuItem>
              </>
            )}
          />
        )}

        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Nouvel utilisateur</DialogTitle>
            </DialogHeader>
            <UserForm
              mode="create"
              defaultValues={{ username: "", nom_complet: "", password: "", role: "Conseiller", telephone: "" } as UserCreateInput}
              onSubmit={(values) => createMutation.mutate(values as UserCreateInput)}
              submitError={createMutation.error}
              submitLabel="Créer"
              isSubmitting={createMutation.isPending}
            />
          </DialogContent>
        </Dialog>

        <Dialog open={editCible !== null} onOpenChange={(open) => !open && setEditCible(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Modifier l&apos;utilisateur</DialogTitle>
            </DialogHeader>
            {editCible && (
              <UserForm
                mode="edit"
                defaultValues={userToFormValues(editCible)}
                onSubmit={(values) => updateMutation.mutate({ id: editCible.id, values: values as UserUpdateInput })}
                submitError={updateMutation.error}
                submitLabel="Enregistrer"
                isSubmitting={updateMutation.isPending}
              />
            )}
          </DialogContent>
        </Dialog>
      </div>
    </AdminGuard>
  );
}
