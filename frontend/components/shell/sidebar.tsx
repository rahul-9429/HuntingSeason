"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { type NavItem, navItems, profileNavItem } from "@/components/shell/nav-items";
import { UserMenu } from "@/components/shell/user-menu";
import { useCredits } from "@/lib/queries/account";
import { useContacts } from "@/lib/queries/contacts";
import { useThreads } from "@/lib/queries/threads";
import { cn } from "@/lib/utils";

function BrandMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        "grid size-7 place-items-center rounded-[2px] border-2 border-accent-600 bg-accent-300 text-[15px] font-bold leading-none text-ink",
        className,
      )}
    >
      H
    </span>
  );
}

function isActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

function SidebarLink({ item, pathname, count }: { item: NavItem; pathname: string; count?: number }) {
  const active = isActive(pathname, item.href);
  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group relative flex h-9 items-center gap-2.5 rounded-[2px] pl-3.5 pr-2.5 font-mono text-micro font-semibold uppercase tracking-[0.1em] outline-none transition-colors focus-visible:ring-2 focus-visible:ring-accent-500/40",
        active
          ? "bg-accent-100 font-bold text-ink"
          : "text-ink-2 hover:bg-sunken hover:text-ink",
      )}
    >
      {active && <span aria-hidden className="absolute inset-y-0 left-0 w-1 bg-accent-500" />}
      <item.icon className={cn("size-4", active ? "text-accent-700" : "text-ink-3 group-hover:text-ink-2")} />
      {item.label}
      {count ? (
        <span
          className={cn(
            "ml-auto tabular-nums",
            active ? "text-accent-700" : "text-ink-3",
          )}
        >
          {count}
        </span>
      ) : null}
    </Link>
  );
}

function MobileLink({ item, pathname }: { item: NavItem; pathname: string }) {
  const active = isActive(pathname, item.href);
  return (
    <Link
      href={item.href}
      aria-label={item.label}
      aria-current={active ? "page" : undefined}
      className={cn(
        "grid size-8 place-items-center rounded-[2px] border-2 transition-colors",
        active
          ? "border-accent-500 bg-accent-200 text-ink"
          : "border-transparent text-ink-3 hover:bg-sunken",
      )}
    >
      <item.icon className="size-4" />
    </Link>
  );
}

function CreditsMeter() {
  const { data: credits } = useCredits();

  if (!credits) {
    return <div aria-hidden className="h-[80px] animate-pulse rounded-[2px] border-2 border-line-strong bg-surface" />;
  }

  const creditsLeft = credits.total - credits.used;
  const empty = creditsLeft === 0;
  const segments = 10;
  const filled = credits.total > 0 ? Math.round((creditsLeft / credits.total) * segments) : 0;

  return (
    <div className="rounded-[2px] border-2 border-line-strong bg-surface p-3">
      <div className="flex items-center justify-between font-mono text-micro font-semibold uppercase tracking-[0.1em]">
        <span className="text-ink-2">Credits</span>
        <span className="tabular-nums text-ink">
          {creditsLeft}
          <span className="text-ink-3">/{credits.total}</span>
        </span>
      </div>
      <div className="mt-2 flex gap-0.5" aria-hidden>
        {Array.from({ length: segments }, (_, i) => (
          <span
            key={i}
            data-on={i < filled}
            className={cn(
              "h-2 flex-1 rounded-[1px] bg-sunken",
              empty ? "data-[on=true]:bg-amber-500" : "data-[on=true]:bg-accent-500",
            )}
          />
        ))}
      </div>
      <p className="mt-2 text-micro text-ink-3">
        {empty ? (
          <span className="font-semibold text-amber-700 dark:text-amber-300">
            Out of credits — searches paused
          </span>
        ) : (
          "Roll over · never expire"
        )}
      </p>
    </div>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const { data: contacts } = useContacts("all");
  const { data: threads } = useThreads("all", "");
  const counts: Record<string, number | undefined> = {
    "/contacts": contacts?.pages[0]?.counts.all,
    "/inbox": threads?.unread,
  };

  return (
    <aside className="hidden w-[248px] shrink-0 flex-col border-r-2 border-line-strong bg-canvas md:flex">
      <div className="flex h-14 items-center gap-2.5 border-b-2 border-line-strong px-5">
        <BrandMark />
        <span className="text-[15px] font-bold tracking-[-0.02em] text-ink">Hunting Season</span>
      </div>

      <p className="px-5 pb-2 pt-5 font-mono text-micro font-semibold uppercase tracking-[0.18em] text-ink-3">
        Pipeline
      </p>
      <nav aria-label="Main" className="space-y-1 px-3">
        {navItems.map((item) => (
          <SidebarLink key={item.href} item={item} pathname={pathname} count={counts[item.href]} />
        ))}
      </nav>

      <div className="mt-auto space-y-2 p-3">
        <CreditsMeter />

        <div className="space-y-1">
          <SidebarLink item={profileNavItem} pathname={pathname} />
          <UserMenu />
        </div>
      </div>
    </aside>
  );
}

export function MobileNav() {
  const pathname = usePathname();

  return (
    <header className="flex h-12 shrink-0 items-center gap-1 border-b-2 border-line-strong bg-canvas px-3 md:hidden">
      <BrandMark className="mr-2 size-6 text-[13px]" />
      <nav aria-label="Main" className="flex items-center gap-0.5">
        {navItems.map((item) => (
          <MobileLink key={item.href} item={item} pathname={pathname} />
        ))}
      </nav>
      <span className="ml-auto flex items-center gap-1">
        <MobileLink item={profileNavItem} pathname={pathname} />
        <UserMenu compact />
      </span>
    </header>
  );
}
