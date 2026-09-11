"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import clsx from "clsx";
import { AnimatePresence, motion } from "framer-motion";
import { Menu, X, LogOut } from "lucide-react";
import { supabase } from "@/lib/supabase";
import { clearSession } from "@/lib/session";
import { NAV_ITEMS } from "@/lib/nav-items";
import { ThemeToggle } from "./theme-toggle";

export function MobileNav() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const router = useRouter();

  async function handleSignOut() {
    if (supabase) await supabase.auth.signOut();
    clearSession();
    router.replace("/login");
  }

  return (
    <>
      <header className="sticky top-0 z-40 flex items-center justify-between border-b border-border bg-canvas-raised px-4 py-3 lg:hidden">
        <span className="text-sm font-semibold tracking-tight text-ink">Creator Intelligence OS</span>
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Open menu"
          className="flex h-9 w-9 items-center justify-center rounded-lg text-ink hover:bg-ink/5"
        >
          <Menu className="h-5 w-5" strokeWidth={1.75} />
        </button>
      </header>

      <AnimatePresence>
        {open && (
          <>
            <motion.div
              key="overlay"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="fixed inset-0 z-50 bg-black/40 lg:hidden"
              onClick={() => setOpen(false)}
            />
            <motion.aside
              key="drawer"
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "spring", stiffness: 380, damping: 38 }}
              className="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col bg-canvas-raised px-3 py-4 shadow-elevated lg:hidden"
            >
              <div className="mb-6 flex items-center justify-between px-2">
                <span className="text-sm font-semibold tracking-tight text-ink">Creator Intelligence OS</span>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  aria-label="Close menu"
                  className="flex h-8 w-8 items-center justify-center rounded-lg text-subtle hover:bg-ink/5 hover:text-ink"
                >
                  <X className="h-4 w-4" strokeWidth={1.75} />
                </button>
              </div>
              <nav className="flex flex-1 flex-col gap-0.5">
                {NAV_ITEMS.map((item) => {
                  const active = pathname === item.href;
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setOpen(false)}
                      className={clsx(
                        "flex items-center gap-2.5 rounded-lg px-2.5 py-2.5 text-sm font-medium transition-colors",
                        active ? "bg-accent-soft text-accent" : "text-subtle hover:bg-ink/5 hover:text-ink"
                      )}
                    >
                      <Icon className="h-4 w-4" strokeWidth={1.75} />
                      {item.label}
                    </Link>
                  );
                })}
              </nav>
              <div className="flex items-center justify-between px-1 pt-2">
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
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
