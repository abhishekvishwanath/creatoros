"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { setActiveCreator, onAuthReady, isAuthenticated } from "@/lib/session";
import { listMyCreators, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"sign-in" | "sign-up">("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!supabase) {
      // Dev mode: there's no such thing as signing in, only the localStorage
      // placeholder identity minted at onboarding.
      router.replace("/onboarding");
      return;
    }
    onAuthReady(async () => {
      if (!isAuthenticated()) return;
      await routeToNextStep();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function routeToNextStep() {
    try {
      const creators = await listMyCreators();
      if (creators.length > 0) {
        setActiveCreator(creators[0].id, creators[0].name);
        router.replace("/");
      } else {
        router.replace("/onboarding");
      }
    } catch {
      router.replace("/onboarding");
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!supabase) return;
    setError(null);
    setInfo(null);
    setSubmitting(true);
    try {
      if (mode === "sign-up") {
        const { data, error: signUpError } = await supabase.auth.signUp({ email, password });
        if (signUpError) throw signUpError;
        if (!data.session) {
          // Email confirmation is required on this project — signUp()
          // creates the account but doesn't return a session until it's
          // confirmed.
          setInfo("Check your email to confirm your account, then sign in.");
          setMode("sign-in");
          return;
        }
      } else {
        const { error: signInError } = await supabase.auth.signInWithPassword({ email, password });
        if (signInError) throw signInError;
      }
      await routeToNextStep();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : err instanceof Error ? err.message : "Something went wrong.");
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
            {mode === "sign-in" ? "Sign in to your account." : "Create an account to get started."}
          </p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-border bg-white p-6 shadow-card">
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
          <div>
            <label className="mb-1 block text-sm font-medium text-ink">Password</label>
            <input
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-accent"
              placeholder="••••••••"
            />
          </div>
          {error && <p className="text-sm text-bad">{error}</p>}
          {info && <p className="text-sm text-good">{info}</p>}
          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? "…" : mode === "sign-in" ? "Sign in" : "Sign up"}
          </Button>
          <button
            type="button"
            onClick={() => {
              setMode(mode === "sign-in" ? "sign-up" : "sign-in");
              setError(null);
              setInfo(null);
            }}
            className="w-full text-center text-xs text-subtle hover:text-ink"
          >
            {mode === "sign-in" ? "Don't have an account? Sign up" : "Already have an account? Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
