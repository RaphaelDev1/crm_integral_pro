"use client";

import { KeyRound, LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/contexts/AuthContext";

import { ChangePasswordDialog } from "./ChangePasswordDialog";

function initiales(nomComplet: string | undefined): string {
  if (!nomComplet) return "?";
  const mots = nomComplet.trim().split(/\s+/);
  return ((mots[0]?.[0] ?? "") + (mots[mots.length - 1]?.[0] ?? "")).toUpperCase();
}

export function UserMenu() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [changePasswordOpen, setChangePasswordOpen] = useState(false);

  async function onLogout() {
    await logout();
    router.replace("/login");
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger className="rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <Avatar>
            {/* Pas de photo de profil côté API (UserOut n'expose pas d'URL
                d'avatar) : initiales du nom complet en attendant. */}
            <AvatarFallback className="bg-primary/10 text-sm font-medium text-primary">
              {initiales(user?.nom_complet)}
            </AvatarFallback>
          </Avatar>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuLabel>
            <p className="font-medium text-slate-800">{user?.nom_complet}</p>
            <p className="text-xs font-normal text-slate-500">{user?.role}</p>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={() => setChangePasswordOpen(true)}>
            <KeyRound size={16} />
            Changer le mot de passe
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={onLogout}>
            <LogOut size={16} />
            Déconnexion
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <ChangePasswordDialog open={changePasswordOpen} onOpenChange={setChangePasswordOpen} />
    </>
  );
}
