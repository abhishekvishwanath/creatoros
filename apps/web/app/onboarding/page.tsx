"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createCreator, importYoutubeChannel, analyzeCreator, ApiError } from "@/lib/api";
import { setSession, isAuthenticated, onAuthReady } from "@/lib/session";
import { supabase } from "@/lib/supabase";
import { Button } from "@/components/ui/button";

type Step = "profile" | "connect" | "building";

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
  const [importSummary, setImportSummary] = useState<string | null>(null);
  const [buildingLabel, setBuildingLabel] = useState("Building your Creator DNA…");

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

  async function finishToApp() {
    if (!creatorId) return;
    setStep("building");
    setBuildingLabel("Building your Creator DNA…");
    try {
      await analyzeCreator(creatorId);
    } catch {
      // Non-fatal — the Creator DNA page has its own retry button. Don't
      // block getting into the app over an analysis hiccup.
    }
    router.replace("/creator-dna");
  }

  async function handleImport(e: FormEvent) {
    e.preventDefault();
    if (!creatorId) return;
    setError(null);
    setSubmitting(true);
    try {
      const result = await importYoutubeChannel(creatorId, youtubeUrl);
      const bits = [`Imported ${result.imported_count} video(s) from ${result.channel_name}.`];
      if (result.transcript_count > 0) bits.push(`${result.transcript_count} had transcripts we can learn your voice from.`);
      setImportSummary(bits.join(" "));
      setBuildingLabel(`Analyzing ${result.channel_name}'s content…`);
      await new Promise((r) => setTimeout(r, 900)); // let the creator read the summary
      await finishToApp();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't import that channel. Check the link and try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (step === "building") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
        <div className="w-full max-w-sm text-center">
          <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          <p className="text-sm text-subtle">{buildingLabel}</p>
        </div>
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
              Paste your YouTube channel link and we&apos;ll pull your recent videos — titles, descriptions, and
              transcripts where available — to seed your Creator DNA instead of you typing it all in by hand.
            </p>
          </div>
          <form onSubmit={handleImport} className="space-y-4 rounded-xl border border-border bg-white p-6 shadow-card">
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
            {importSummary && <p className="text-sm text-good">{importSummary}</p>}
            {error && <p className="text-sm text-bad">{error}</p>}
            <Button type="submit" disabled={submitting} className="w-full">
              {submitting ? "Importing…" : "Import & build my Creator DNA"}
            </Button>
            <button
              type="button"
              onClick={finishToApp}
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
