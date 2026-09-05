"use client";

import { Bell } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyMedia, EmptyTitle, EmptyDescription } from "@/components/ui/empty";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

export function NotificationPopover() {
  return (
    <Popover>
      <PopoverTrigger render={<Button variant="header" size="header-icon" aria-label="Notifications" />}>
        <Bell data-icon="inline-start" />
      </PopoverTrigger>
      <PopoverContent align="end" className="p-3">
        <Empty className="border-transparent p-4">
          <EmptyMedia>
            <Bell />
          </EmptyMedia>
          <EmptyContent>
            <EmptyTitle>No notifications</EmptyTitle>
            <EmptyDescription>You are all caught up.</EmptyDescription>
          </EmptyContent>
        </Empty>
      </PopoverContent>
    </Popover>
  );
}