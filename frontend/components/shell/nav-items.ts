import { Building2, CircleUserRound, Inbox, UserRoundSearch, type LucideIcon } from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

export const navItems: NavItem[] = [
  { href: "/contacts", label: "Contacts", icon: UserRoundSearch },
  { href: "/companies", label: "Companies", icon: Building2 },
  { href: "/inbox", label: "Inbox", icon: Inbox },
];

// Sits next to the account menu rather than in the main nav.
export const profileNavItem: NavItem = { href: "/profile", label: "Profile", icon: CircleUserRound };
