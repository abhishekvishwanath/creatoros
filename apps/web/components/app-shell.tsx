"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { NavSidebar } from "./nav-sidebar";
import { getSession } from "@/lib/session";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);

  const isOnboarding = pathname === "/onboarding";

  useEffect(() => {
    if (isOnboarding) {
      setReady(true);
      return;
    }
    const session = getSession();
    if (!session) {
      router.replace("/onboarding");
      return;
    }
    setReady(true);
  }, [isOnboarding, pathname, router]);

  if (isOnboarding) {
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
