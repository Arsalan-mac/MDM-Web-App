"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { OrganizationSwitcher, UserButton } from "@clerk/nextjs";
import { BarChart3, LayoutGrid, Settings, Sparkles, Users } from "lucide-react";
import clsx from "clsx";
import { type ReactNode } from "react";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Projects", icon: LayoutGrid, match: (p: string) => p === "/dashboard" },
  {
    href: "/dashboard/leadership",
    label: "Leadership Rollup",
    icon: BarChart3,
    match: (p: string) => p.startsWith("/dashboard/leadership"),
  },
  { href: "/dashboard/team", label: "Team", icon: Users, match: (p: string) => p.startsWith("/dashboard/team") },
  {
    href: "/dashboard/settings",
    label: "Settings",
    icon: Settings,
    match: (p: string) => p.startsWith("/dashboard/settings"),
  },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? "";

  return (
    <div className="min-h-screen bg-ink-50">
      <aside className="fixed inset-y-0 left-0 z-20 flex w-60 flex-col border-r border-ink-200 bg-ink-950">
        <div className="flex h-16 items-center gap-2 px-5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600">
            <Sparkles className="h-4.5 w-4.5 text-white" />
          </div>
          <span className="text-sm font-semibold text-white">MDM Migrate</span>
        </div>

        <nav className="flex-1 space-y-1 px-3 py-2">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = item.match(pathname);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={clsx(
                  "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-white/10 text-white"
                    : "text-ink-400 hover:bg-white/5 hover:text-ink-100",
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-white/10 px-4 py-4">
          <div className="mb-3 [&_.cl-organizationSwitcherTrigger]:w-full [&_.cl-organizationSwitcherTrigger]:justify-start [&_.cl-organizationSwitcherTrigger]:rounded-lg [&_.cl-organizationSwitcherTrigger]:px-2 [&_.cl-organizationSwitcherTrigger]:py-1.5 [&_.cl-organizationSwitcherTrigger]:text-white [&_.cl-organizationSwitcherTrigger:hover]:bg-white/5">
            <OrganizationSwitcher
              hidePersonal
              afterCreateOrganizationUrl="/dashboard"
              afterSelectOrganizationUrl="/dashboard"
              appearance={{ elements: { organizationSwitcherTriggerIcon: "text-ink-400" } }}
            />
          </div>
          <div className="flex items-center gap-2 px-1">
            <UserButton afterSignOutUrl="/" />
            <span className="text-xs text-ink-400">Account</span>
          </div>
        </div>
      </aside>

      <div className="pl-60">
        <main className="mx-auto max-w-6xl px-8 py-8">{children}</main>
      </div>
    </div>
  );
}
