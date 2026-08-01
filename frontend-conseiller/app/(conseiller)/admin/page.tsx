"use client";

import { BookOpen, FileSearch, Settings, Users as UsersIcon, TrendingDown, type LucideIcon } from "lucide-react";
import Link from "next/link";

import { AdminGuard } from "@/components/layout/AdminGuard";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface AdminSection {
  href: string;
  label: string;
  description: string;
  icon: LucideIcon;
}

const SECTIONS: AdminSection[] = [
  {
    href: "/admin/utilisateurs",
    label: "Utilisateurs",
    description: "Gérer les comptes conseillers et administrateurs.",
    icon: UsersIcon,
  },
  {
    href: "/admin/veille",
    label: "Veille prix",
    description: "Sources surveillées, historique des prix, alertes détectées.",
    icon: TrendingDown,
  },
  {
    href: "/admin/parametres",
    label: "Paramètres",
    description: "Réglages généraux et logo utilisé dans les restitutions PDF.",
    icon: Settings,
  },
  {
    href: "/admin/ocr-facture",
    label: "OCR facture",
    description: "Analyser une facture PDF hors fiche client.",
    icon: FileSearch,
  },
  {
    href: "/admin/catalogue",
    label: "Catalogue",
    description: "Sources de découverte d'offres et validation des offres détectées.",
    icon: BookOpen,
  },
];

export default function AdminPage() {
  return (
    <AdminGuard>
      <div className="space-y-4">
        <h1 className="text-xl font-bold text-primary">Admin</h1>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {SECTIONS.map(({ href, label, description, icon: Icon }) => (
            <Link key={href} href={href}>
              <Card className="h-full transition-colors hover:border-primary/50">
                <CardHeader>
                  <Icon className="text-primary mb-2" size={24} />
                  <CardTitle>{label}</CardTitle>
                  <CardDescription>{description}</CardDescription>
                </CardHeader>
              </Card>
            </Link>
          ))}
        </div>
      </div>
    </AdminGuard>
  );
}
