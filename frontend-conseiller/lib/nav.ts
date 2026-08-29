import { BarChart3, Compass, Folder, LayoutDashboard, Receipt, Settings, Sparkles, UserCheck, Users, type LucideIcon } from "lucide-react";

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
  { href: "/ia-conseil/clients", label: "IA Conseil", icon: Sparkles },
  { href: "/ia-conseil/dashboard", label: "Dashboard IA Conseil", icon: BarChart3 },
  { href: "/prospects", label: "Prospects", icon: Users },
  { href: "/clients", label: "Clients & contrats", icon: UserCheck },
  { href: "/dossiers", label: "Dossiers", icon: Folder },
  { href: "/facturation", label: "Facturation", icon: Receipt },
];

export const ADMIN_NAV_ITEM: NavItem = { href: "/admin", label: "Responsable", icon: Settings };

// Réservé aux Admin ("Responsable" affiché) — voir backend/routers/dashboard_utm.py
// (require_role("Admin")) et components/layout/AdminGuard.tsx.
export const UTM_NAV_ITEM: NavItem = { href: "/dashboard/utm", label: "Dashboard UTM", icon: BarChart3 };

export const RESPONSABLE_NAV_ITEMS: NavItem[] = [UTM_NAV_ITEM, ADMIN_NAV_ITEM];
