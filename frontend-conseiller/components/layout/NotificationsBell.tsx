"use client";

import { Bell } from "lucide-react";
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
    router.push(`/dossiers/${notification.dossier_id}`);
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
              className="flex flex-col items-start gap-0.5 whitespace-normal py-2"
            >
              <span className={notification.lu ? "text-muted-foreground" : "font-medium"}>
                {notification.message}
              </span>
              {notification.date_creation && (
                <span className="text-xs text-muted-foreground">{notification.date_creation}</span>
              )}
            </DropdownMenuItem>
          ))
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
