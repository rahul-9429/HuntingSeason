"use client";

import { useClerk, useUser } from "@clerk/nextjs";
import { ChevronsUpDown, LogOut, Monitor, Moon, Sun, SunMoon } from "lucide-react";
import { useTheme } from "next-themes";
import { Avatar } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSegmentedGroup,
  DropdownMenuSegmentedItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip } from "@/components/ui/tooltip";
import { SIGN_IN_URL } from "@/lib/auth";
import { cn } from "@/lib/utils";

const THEMES = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
];

export function UserMenu({ compact = false }: { compact?: boolean }) {
  const { isLoaded, user } = useUser();
  const { signOut } = useClerk();
  const { theme, setTheme } = useTheme();

  if (!isLoaded || !user) {
    return compact ? (
      <span aria-hidden className="size-7 animate-pulse rounded-full bg-sunken" />
    ) : (
      <div aria-hidden className="flex animate-pulse items-center gap-2.5 p-1.5">
        <span className="size-8 rounded-full bg-sunken" />
        <span className="flex-1 space-y-1.5">
          <span className="block h-2.5 w-24 rounded bg-sunken" />
          <span className="block h-2 w-32 rounded bg-sunken" />
        </span>
      </div>
    );
  }

  const email = user.primaryEmailAddress?.emailAddress ?? "";
  const name = user.fullName || user.username || email.split("@")[0] || "Account";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="Account menu"
        className={cn(
          "cursor-pointer outline-none transition focus-visible:ring-2 focus-visible:ring-accent-500/30",
          compact
            ? "grid size-8 place-items-center rounded-full"
            : "flex w-full items-center gap-2.5 rounded-md p-1.5 text-left hover:bg-sunken",
        )}
      >
        <Avatar name={name} hue="ink" size={compact ? "sm" : "md"} />
        {!compact && (
          <>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-ui font-medium text-ink">{name}</span>
              <span className="block truncate text-micro text-ink-3">{email}</span>
            </span>
            <ChevronsUpDown className="size-3.5 text-ink-3" />
          </>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent side={compact ? "bottom" : "top"} align={compact ? "end" : "start"} className="w-60">
        <DropdownMenuLabel className="truncate">Signed in as {email}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <div className="flex h-8 items-center gap-2 pl-2 pr-0.5 text-ui text-ink">
          <SunMoon className="size-3.5 shrink-0 text-ink-3" />
          Theme
          <DropdownMenuSegmentedGroup value={theme} onValueChange={setTheme} aria-label="Theme" className="ml-auto">
            {THEMES.map(({ value, label, icon: Icon }) => (
              <Tooltip key={value} content={label}>
                {/* Stay open so the switch is visible in place. */}
                <DropdownMenuSegmentedItem value={value} aria-label={label} onSelect={(event) => event.preventDefault()}>
                  <Icon />
                </DropdownMenuSegmentedItem>
              </Tooltip>
            ))}
          </DropdownMenuSegmentedGroup>
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => signOut({ redirectUrl: SIGN_IN_URL })}>
          <LogOut /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
