"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/contexts/AuthContext";
import { ADMIN_NAV_ITEM, NAV_ITEMS } from "@/lib/nav";

export function Sidebar() {
  const pathname = usePathname();
  const { estAdmin } = useAuth();

  return (
    <aside className="w-60 shrink-0 bg-white border-r border-slate-200 flex flex-col">
      <div className="px-4 py-5 border-b border-slate-200">
        <span className="text-lg font-bold text-primary">IA Conseil</span>
      </div>
      <nav className="flex-1 px-2 py-4 space-y-1">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const actif = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                actif ? "bg-primary/10 text-primary" : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              <Icon size={18} />
              {label}
            </Link>
          );
        })}
        {estAdmin() && (
          <Link
            href={ADMIN_NAV_ITEM.href}
            className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
              pathname.startsWith(ADMIN_NAV_ITEM.href) ? "bg-primary/10 text-primary" : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            <ADMIN_NAV_ITEM.icon size={18} />
            {ADMIN_NAV_ITEM.label}
          </Link>
        )}
      </nav>
    </aside>
  );
}
