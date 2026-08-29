"use client";

import { Bell, Check } from "lucide-react";
import { useRouter } from "next/navigation";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useMarquerNotificationLue, useNotifications } from "@/lib/hooks/useNotifications";
import type { Notification } from "@/lib/types";

export function NotificationsBell() {
  const router = useRouter();
  const notificationsQuery = useNotifications();
  const marquerLuMutation = useMarquerNotificationLue();

  const notifications = notificationsQuery.data ?? [];
  const nonLues = notifications.filter((n) => !n.lu).length;

  const handleClick = (notification: Notification) => {
    if (!notification.lu) marquerLuMutation.mutate(notification.id);
    // `lien` (IA Conseil) prime sur `dossier_id` (CRM) — voir
    // backend/models/notification.py, les deux ne sont jamais renseignés
    // ensemble en pratique.
    if (notification.lien) {
      router.push(notification.lien);
    } else if (notification.dossier_id != null) {
      router.push(`/dossiers/${notification.dossier_id}`);
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          className="relative flex h-9 w-9 items-center justify-center rounded-md text-slate-600 hover:bg-slate-100"
          title="Notifications"
        >
          <Bell size={18} />
          {nonLues > 0 && (
            <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 text-[10px] font-medium text-white">
              {nonLues > 99 ? "99+" : nonLues}
            </span>
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80">
        <DropdownMenuLabel>Notifications</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {notifications.length === 0 ? (
          <p className="px-2 py-3 text-sm text-muted-foreground">Aucune notification.</p>
        ) : (
          notifications.slice(0, 20).map((notification) => (
            <DropdownMenuItem
              key={notification.id}
              onSelect={() => handleClick(notification)}
              className="flex items-start gap-2 whitespace-normal py-2"
            >
              <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center">
                {notification.lu ? (
                  <Check size={14} className="text-emerald-600" />
                ) : (
                  <span className="flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 text-[10px] font-medium text-white">
                    1
                  </span>
                )}
              </span>
              <span className="flex flex-1 flex-col items-start gap-0.5">
                <span className={notification.lu ? "text-muted-foreground" : "font-medium"}>
                  {notification.message}
                </span>
                {notification.date_creation && (
                  <span className="text-xs text-muted-foreground">{notification.date_creation}</span>
                )}
              </span>
            </DropdownMenuItem>
          ))
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
