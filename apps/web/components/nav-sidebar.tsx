"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import clsx from "clsx";
import { motion } from "framer-motion";
import { LogOut } from "lucide-react";
import { supabase } from "@/lib/supabase";
import { clearSession } from "@/lib/session";
import { NAV_ITEMS } from "@/lib/nav-items";
import { ThemeToggle } from "./theme-toggle";

export function NavSidebar() {
  const pathname = usePathname();
  const router = useRouter();

  async function handleSignOut() {
    if (supabase) await supabase.auth.signOut();
    clearSession();
    router.replace("/login");
  }

  return (
    <aside className="sticky top-0 hidden h-screen w-56 shrink-0 flex-col border-r border-border bg-canvas-raised px-3 py-4 lg:flex">
      <div className="mb-6 flex items-center justify-between px-2">
        <span className="text-sm font-semibold tracking-tight text-ink">Creator Intelligence OS</span>
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
                "relative flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors",
                active ? "text-accent" : "text-subtle hover:bg-ink/5 hover:text-ink"
              )}
            >
              {active && (
                <motion.span
                  layoutId="nav-active-pill"
                  className="absolute inset-0 rounded-lg bg-accent-soft"
                  transition={{ type: "spring", stiffness: 500, damping: 35 }}
                />
              )}
              <Icon className="relative z-10 h-4 w-4" strokeWidth={1.75} />
              <span className="relative z-10">{item.label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="flex items-center justify-between px-1">
        {supabase && (
          <button
            onClick={handleSignOut}
            className="flex items-center gap-2.5 rounded-lg px-2 py-2 text-sm font-medium text-subtle transition-colors hover:bg-ink/5 hover:text-ink"
          >
            <LogOut className="h-4 w-4" strokeWidth={1.75} />
            Sign out
          </button>
        )}
        <ThemeToggle />
      </div>
    </aside>
  );
}
