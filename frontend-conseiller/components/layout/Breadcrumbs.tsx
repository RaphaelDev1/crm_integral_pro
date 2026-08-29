"use client";

import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Fragment } from "react";

import { NAV_ITEMS, RESPONSABLE_NAV_ITEMS } from "@/lib/nav";

const KNOWN_ITEMS = [...NAV_ITEMS, ...RESPONSABLE_NAV_ITEMS];

// Parsé depuis usePathname plutôt que déclaré page par page : un segment
// connu (voir lib/nav.ts) prend son libellé métier, un segment inconnu (ex.
// futur /clients/[id]) s'affiche tel quel en attendant que ces pages
// fournissent leur propre libellé.
export function Breadcrumbs() {
  const pathname = usePathname();
  const segments = pathname.split("/").filter(Boolean);

  if (segments.length === 0) {
    return null;
  }

  const crumbs = segments.map((segment, index) => {
    const href = "/" + segments.slice(0, index + 1).join("/");
    const known = KNOWN_ITEMS.find((item) => item.href === href);
    return { href, label: known?.label ?? decodeURIComponent(segment) };
  });

  return (
    <nav aria-label="Fil d'Ariane" className="flex items-center gap-1.5 text-sm text-slate-500">
      {crumbs.map((crumb, index) => {
        const isLast = index === crumbs.length - 1;
        return (
          <Fragment key={crumb.href}>
            {index > 0 && <ChevronRight size={14} className="text-slate-300" />}
            {isLast ? (
              <span className="font-medium text-slate-700">{crumb.label}</span>
            ) : (
              <Link href={crumb.href} className="hover:text-slate-700">
                {crumb.label}
              </Link>
            )}
          </Fragment>
        );
      })}
    </nav>
  );
}
