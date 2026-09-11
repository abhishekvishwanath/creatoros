"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createCreator, ApiError } from "@/lib/api";
import { setSession, isAuthenticated, onAuthReady } from "@/lib/session";
import { supabase } from "@/lib/supabase";
import { Button } from "@/components/ui/button";

export default function OnboardingPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [niche, setNiche] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    // Real mode requires signing in first (identity comes from the session,
    // not a typed email) — dev mode has no such concept, this page itself
    // is the bootstrap.
    if (!supabase) return;
    onAuthReady(() => {
      if (!isAuthenticated()) router.replace("/login");
    });
  }, [router]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const creator = await createCreator({ email: supabase ? undefined : email, name, niche: niche || undefined });
      setSession({ userId: creator.user_id, creatorId: creator.id, creatorName: creator.name });
      router.replace("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-lg font-semibold text-ink">Creator Intelligence OS</h1>
          <p className="mt-2 text-sm text-subtle">
            Tell us who you are. We&apos;ll start building your Creator DNA.
          </p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-border bg-white p-6 shadow-card">
          {!supabase && (
            <div>
              <label className="mb-1 block text-sm font-medium text-ink">Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-accent"
                placeholder="you@example.com"
              />
            </div>
          )}
          <div>
            <label className="mb-1 block text-sm font-medium text-ink">Name</label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-accent"
              placeholder="Your name or brand"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-ink">Niche (optional)</label>
            <input
              type="text"
              value={niche}
              onChange={(e) => setNiche(e.target.value)}
              className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-accent"
              placeholder="e.g. AI productivity for students"
            />
          </div>
          {error && <p className="text-sm text-bad">{error}</p>}
          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? "Setting up…" : "Get started"}
          </Button>
        </form>
      </div>
    </div>
  );
}
