"use client";

import { Breadcrumbs } from "@/components/layout/Breadcrumbs";
import { NotificationsBell } from "@/components/layout/NotificationsBell";
import { ThemeToggle } from "@/components/layout/ThemeToggle";
import { UserMenu } from "@/components/layout/UserMenu";

export function Header() {
  return (
    <header className="h-14 shrink-0 bg-white border-b border-slate-200 flex items-center justify-between gap-4 px-6 dark:bg-card dark:border-border">
      <Breadcrumbs />
      <div className="flex items-center gap-2">
        <ThemeToggle />
        <NotificationsBell />
        <UserMenu />
      </div>
    </header>
  );
}
