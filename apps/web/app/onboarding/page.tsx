"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createCreator, startPipelineRun, ApiError } from "@/lib/api";
import { setSession, isAuthenticated, onAuthReady } from "@/lib/session";
import { supabase } from "@/lib/supabase";
import { Button } from "@/components/ui/button";
import { PipelineProgress } from "@/components/pipeline-progress";
import type { PipelineRunRead } from "@/lib/types";

type Step = "profile" | "connect" | "running";

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("profile");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [niche, setNiche] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [creatorId, setCreatorId] = useState<string | null>(null);
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [runId, setRunId] = useState<string | null>(null);

  useEffect(() => {
    // Real mode requires signing in first (identity comes from the session,
    // not a typed email) — dev mode has no such concept, this page itself
    // is the bootstrap.
    if (!supabase) return;
    onAuthReady(() => {
      if (!isAuthenticated()) router.replace("/login");
    });
  }, [router]);

  async function handleCreateProfile(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const creator = await createCreator({ email: supabase ? undefined : email, name, niche: niche || undefined });
      setSession({ userId: creator.user_id, creatorId: creator.id, creatorName: creator.name });
      setCreatorId(creator.id);
      setStep("connect");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setSubmitting(false);
    }
  }

  async function startEngines(url?: string) {
    if (!creatorId) return;
    setError(null);
    setSubmitting(true);
    try {
      const run = await startPipelineRun(creatorId, url || undefined);
      setRunId(run.id);
      setStep("running");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't start — is the API running?");
    } finally {
      setSubmitting(false);
    }
  }

  function handlePipelineComplete(run: PipelineRunRead) {
    void run;
    router.replace("/creator-dna");
  }

  if (step === "running" && creatorId && runId) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
        <PipelineProgress creatorId={creatorId} runId={runId} onComplete={handlePipelineComplete} />
      </div>
    );
  }

  if (step === "connect") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
        <div className="w-full max-w-sm">
          <div className="mb-8 text-center">
            <h1 className="text-lg font-semibold text-ink">Connect your channel</h1>
            <p className="mt-2 text-sm text-subtle">
              Paste your YouTube channel link and every engine starts: we pull your recent videos, build your
              Creator DNA, research your niche, and score real opportunities — automatically.
            </p>
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              startEngines(youtubeUrl);
            }}
            className="space-y-4 rounded-xl border border-border bg-white p-6 shadow-card"
          >
            <div>
              <label className="mb-1 block text-sm font-medium text-ink">YouTube channel URL</label>
              <input
                type="text"
                required
                value={youtubeUrl}
                onChange={(e) => setYoutubeUrl(e.target.value)}
                className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-accent"
                placeholder="https://youtube.com/@yourhandle"
              />
            </div>
            {error && <p className="text-sm text-bad">{error}</p>}
            <Button type="submit" disabled={submitting} className="w-full">
              {submitting ? "Starting…" : "Start the engines"}
            </Button>
            <button
              type="button"
              onClick={() => startEngines()}
              disabled={submitting}
              className="w-full text-center text-sm text-subtle underline underline-offset-2 hover:text-ink"
            >
              Skip for now
            </button>
          </form>
        </div>
      </div>
    );
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
        <form onSubmit={handleCreateProfile} className="space-y-4 rounded-xl border border-border bg-white p-6 shadow-card">
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
            {submitting ? "Setting up…" : "Continue"}
          </Button>
        </form>
      </div>
    </div>
  );
}
