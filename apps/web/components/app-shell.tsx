"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { NavSidebar } from "./nav-sidebar";
import { getSession, isAuthenticated, onAuthReady, onAuthChange } from "@/lib/session";

const PUBLIC_PATHS = new Set(["/onboarding", "/login"]);

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
        router.replace("/login");
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
    return <div className="flex h-screen items-center justify-center text-sm text-subtle">Loading…</div>;
  }

  return (
    <div className="flex">
      <NavSidebar />
      <main className="min-h-screen flex-1 bg-canvas">{children}</main>
    </div>
  );
}
