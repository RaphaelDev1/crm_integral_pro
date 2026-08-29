"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { useAuth } from "@/contexts/AuthContext";
import { NAV_ITEMS, RESPONSABLE_NAV_ITEMS } from "@/lib/nav";

// Palette globale (Cmd+K / Ctrl+K). Pour l'instant limitée à la navigation
// transverse (lib/nav.ts) : les groupes de recherche clients/prospects/
// dossiers viendront s'y ajouter (CommandGroup dédiés) une fois ces listes
// consommées via React Query, plutôt que d'inventer ici un endpoint de
// recherche qui n'existe pas encore côté backend.
export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const { estAdmin } = useAuth();

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "k" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        setOpen((value) => !value);
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  function goTo(href: string) {
    setOpen(false);
    router.push(href);
  }

  const items = estAdmin() ? [...NAV_ITEMS, ...RESPONSABLE_NAV_ITEMS] : NAV_ITEMS;

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Rechercher une section…" />
      <CommandList>
        <CommandEmpty>Aucun résultat.</CommandEmpty>
        <CommandGroup heading="Navigation">
          {items.map(({ href, label, icon: Icon }) => (
            <CommandItem key={href} value={label} onSelect={() => goTo(href)}>
              <Icon />
              {label}
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
