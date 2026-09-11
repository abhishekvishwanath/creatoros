"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import {
  Home,
  Compass,
  Lightbulb,
  PenSquare,
  CalendarDays,
  BarChart3,
  Dna,
  Building2,
  Send,
  FlaskConical,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/", label: "Home", icon: Home },
  { href: "/research", label: "Research", icon: Compass },
  { href: "/opportunities", label: "Opportunities", icon: Lightbulb },
  { href: "/create", label: "Create", icon: PenSquare },
  { href: "/calendar", label: "Calendar", icon: CalendarDays },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/experiments", label: "Experiments", icon: FlaskConical },
  { href: "/brands", label: "Brands", icon: Building2 },
  { href: "/outreach", label: "Outreach", icon: Send },
  { href: "/creator-dna", label: "Creator DNA", icon: Dna },
];

export function NavSidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-56 flex-col border-r border-border bg-white px-3 py-4">
      <div className="mb-6 px-2">
        <span className="text-sm font-semibold tracking-tight text-ink">
          Creator Intelligence OS
        </span>
      </div>
      <nav className="flex flex-1 flex-col gap-0.5">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-accent-soft text-accent"
                  : "text-subtle hover:bg-zinc-100 hover:text-ink"
              )}
            >
              <Icon className="h-4 w-4" strokeWidth={1.75} />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
