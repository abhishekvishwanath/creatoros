"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { NavSidebar } from "./nav-sidebar";
import { MobileNav } from "./mobile-nav";
import { PageTransition } from "./page-transition";
import { getSession, isAuthenticated, onAuthReady, onAuthChange } from "@/lib/session";
import { Skeleton } from "@/components/ui/skeleton";

const PUBLIC_PATHS = new Set(["/onboarding", "/login", "/welcome"]);

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);

  const isPublic = PUBLIC_PATHS.has(pathname);

  useEffect(() => {
    let cancelled = false;

    function evaluate() {
      if (cancelled) return;
      if (isPublic) {
        setReady(true);
        return;
      }
      // Two independent gates: signed in at all (Supabase session, or the
      // dev-mode placeholder identity), and a creator actually picked/
      // created (our own concept, cached separately — see lib/session.ts).
      if (!isAuthenticated()) {
        // The bare root is where a signed-out visitor lands cold (a
        // shared link, a bookmark) — send them to the marketing page, not
        // straight to a bare login form. A deep link to a specific
        // protected page skips that detour; they clearly want the app.
        router.replace(pathname === "/" ? "/welcome" : "/login");
        return;
      }
      const session = getSession();
      if (!session) {
        router.replace("/onboarding");
        return;
      }
      setReady(true);
    }

    onAuthReady(evaluate);
    const unsubscribe = onAuthChange(evaluate);
    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, [isPublic, pathname, router]);

  if (isPublic) {
    return <>{children}</>;
  }

  if (!ready) {
    return <div className="flex h-screen items-center justify-center"><Skeleton className="h-8 w-40" /></div>;
  }

  return (
    <div className="flex min-h-screen flex-col lg:flex-row">
      <NavSidebar />
      <MobileNav />
      <main className="min-h-screen flex-1 bg-canvas">
        <PageTransition pathname={pathname}>{children}</PageTransition>
      </main>
    </div>
  );
}
