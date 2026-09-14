"use client";

import Link from "next/link";
import { KeyRound, LogOut, Monitor, Moon, Sun, Users } from "lucide-react";
import { useTheme } from "next-themes";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ADMIN_ROLE, ROLE_LABELS, type BackendUser } from "@/lib/auth-client";
import { themeOptions as preferenceThemeOptions, updateUserPreferences } from "@/lib/settings-preferences";

const themeIcons = { light: Sun, dark: Moon, system: Monitor } as const;

async function signOut() {
  await fetch("/api/logout", { method: "POST" });
  window.location.href = "/login";
}

function userInitials(email: string) {
  const localPart = email.split("@")[0] ?? "";
  const parts = localPart.split(/[.\-_]+/).filter(Boolean);
  const letters = parts.map((part) => part[0] ?? "").join("").slice(0, 2);
  return (letters || "?").toUpperCase();
}

type UserMenuProps = {
  user: BackendUser;
};

export function UserMenu({ user }: UserMenuProps) {
  const { theme, setTheme } = useTheme();
  const initials = userInitials(user.email);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={<Button variant="header" size="header-icon" aria-label="Account menu" />}
      >
        <Avatar size="lg">
          <AvatarFallback>{initials}</AvatarFallback>
        </Avatar>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <div className="flex items-center gap-3 px-2 py-2">
          <Avatar size="lg">
            <AvatarFallback>{initials}</AvatarFallback>
          </Avatar>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-foreground">{user.email}</p>
            <span className="mt-0.5 inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              {ROLE_LABELS[user.role] ?? user.role}
            </span>
          </div>
        </div>

        <DropdownMenuSeparator />

        <DropdownMenuGroup>
          <DropdownMenuLabel>Theme</DropdownMenuLabel>
          {preferenceThemeOptions.map(({ value, label }) => {
            const Icon = themeIcons[value];
            return (
              <DropdownMenuItem
                key={value}
                onClick={() => {
                  setTheme(value);
                  void updateUserPreferences({ theme: value }).catch(() => undefined);
                }}
                className={theme === value ? "bg-accent text-accent-foreground" : undefined}
              >
                <Icon data-icon="inline-start" />
                {label}
              </DropdownMenuItem>
            );
          })}
        </DropdownMenuGroup>

        <DropdownMenuSeparator />

        {user.role === ADMIN_ROLE ? (
          <DropdownMenuItem render={<Link href="/settings/users" />}>
            <Users data-icon="inline-start" />
            Users
          </DropdownMenuItem>
        ) : null}
        <DropdownMenuItem render={<Link href="/settings/password" />}>
          <KeyRound data-icon="inline-start" />
          Change password
        </DropdownMenuItem>

        <DropdownMenuSeparator />

        <DropdownMenuItem variant="destructive" onClick={signOut}>
          <LogOut data-icon="inline-start" />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
