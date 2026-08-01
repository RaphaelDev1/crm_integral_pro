import { Compass, Folder, LayoutDashboard, Receipt, Settings, UserCheck, Users, type LucideIcon } from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

// Source unique pour Sidebar, Breadcrumbs et CommandPalette : les trois ont
// besoin de la même correspondance route → libellé/icône.
export const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Tableau de bord", icon: LayoutDashboard },
  { href: "/diagnostic", label: "Nouveau diagnostic", icon: Compass },
  { href: "/prospects", label: "Prospects", icon: Users },
  { href: "/clients", label: "Clients & contrats", icon: UserCheck },
  { href: "/dossiers", label: "Dossiers", icon: Folder },
  { href: "/facturation", label: "Facturation", icon: Receipt },
];

export const ADMIN_NAV_ITEM: NavItem = { href: "/admin", label: "Admin", icon: Settings };
