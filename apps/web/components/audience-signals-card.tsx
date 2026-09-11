"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Users } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { getSession } from "@/lib/session";
import { createAudienceSignal, listAudienceSignals, ApiError } from "@/lib/api";
import type { AudienceSignalRead } from "@/lib/types";
import { SkeletonText } from "@/components/ui/skeleton";

export function AudienceSignalsCard() {
  const [signals, setSignals] = useState<AudienceSignalRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [text, setText] = useState("");
  const [platform, setPlatform] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    const session = getSession();
    if (!session) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      setSignals(await listAudienceSignals(session.creatorId));
    } catch (err) {
      // A failed load must not look identical to "zero signals exist" — the
      // list is left as-is (not cleared) and an explicit error is shown
      // instead of silently rendering the empty state.
      setLoadError(err instanceof ApiError ? err.message : "Couldn't load audience signals. Is the API running?");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const session = getSession();
    if (!session) return;
    setSubmitting(true);
    setError(null);
    try {
      await createAudienceSignal(session.creatorId, { text, source_platform: platform || undefined });
      setText("");
      setPlatform("");
      await refetch();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Users className="h-4 w-4 text-accent" /> Audience voice
        </CardTitle>
        <CardDescription>
          Paste in a comment, question, or piece of feedback your audience left — no comments/analytics API is
          connected yet, so this is manual for now. This is what the Audience Intelligence Agent reads.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="mb-4 grid grid-cols-1 gap-2 sm:grid-cols-[1fr_140px_auto]">
          <textarea
            required
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="e.g. 'How do I even start budgeting on a tight income?'"
            rows={2}
            className="rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-accent sm:col-span-2"
          />
          <select
            value={platform}
            onChange={(e) => setPlatform(e.target.value)}
            className="rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-accent"
          >
            <option value="">Platform</option>
            <option value="youtube">YouTube</option>
            <option value="instagram">Instagram</option>
            <option value="x">X</option>
            <option value="tiktok">TikTok</option>
            <option value="email">Email/DM</option>
            <option value="other">Other</option>
          </select>
          <div className="sm:col-span-3">
            <Button type="submit" variant="secondary" disabled={submitting}>
              {submitting ? "Adding…" : "Add signal"}
            </Button>
            {error && <span className="ml-3 text-xs text-bad">{error}</span>}
          </div>
        </form>

        {loading ? (
          <SkeletonText lines={2} />
        ) : loadError ? (
          <p className="text-sm text-bad">{loadError}</p>
        ) : signals.length === 0 ? (
          <EmptyState
            icon={Users}
            title="No audience signal ingested yet"
            description="Comments and connected analytics will populate this — for now, add what you've seen directly."
          />
        ) : (
          <ul className="divide-y divide-border">
            {signals.map((s) => (
              <li key={s.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                <span className="text-ink">{s.text}</span>
                <span className="shrink-0 text-xs text-subtle">{s.source_platform ?? "—"}</span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
