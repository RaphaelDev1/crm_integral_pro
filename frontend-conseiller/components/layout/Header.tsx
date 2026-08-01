"use client";

import { Breadcrumbs } from "@/components/layout/Breadcrumbs";
import { NotificationsBell } from "@/components/layout/NotificationsBell";
import { UserMenu } from "@/components/layout/UserMenu";

export function Header() {
  return (
    <header className="h-14 shrink-0 bg-white border-b border-slate-200 flex items-center justify-between gap-4 px-6">
      <Breadcrumbs />
      <div className="flex items-center gap-2">
        <NotificationsBell />
        <UserMenu />
      </div>
    </header>
  );
}
