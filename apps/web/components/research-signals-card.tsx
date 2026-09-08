"use client";

import { FormEvent, useState } from "react";
import { Radar } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { getSession } from "@/lib/session";
import { createResearchSignal, ApiError } from "@/lib/api";
import type { ResearchSignalSummary } from "@/lib/types";

export function ResearchSignalsCard({
  signals,
  onIngested,
}: {
  signals: ResearchSignalSummary[];
  onIngested: () => Promise<unknown>;
}) {
  const [topic, setTopic] = useState("");
  const [platform, setPlatform] = useState("");
  const [summary, setSummary] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const session = getSession();
    if (!session) return;
    setSubmitting(true);
    setError(null);
    try {
      await createResearchSignal(session.creatorId, {
        topic,
        summary,
        platform: platform || undefined,
      });
      setTopic("");
      setPlatform("");
      setSummary("");
      await onIngested();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="lg:col-span-2">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Radar className="h-4 w-4 text-accent" /> Research signals
        </CardTitle>
        <CardDescription>
          Paste in a competitor post that took off, a trend, or a recurring audience question — this is the raw
          material the Opportunity Engine scores against. No live web research is connected yet, so this is manual
          for now.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="mb-4 grid grid-cols-1 gap-2 sm:grid-cols-[1fr_140px_auto]">
          <input
            required
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="Topic (e.g. envelope budgeting)"
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
            <option value="reddit">Reddit</option>
            <option value="other">Other</option>
          </select>
          <textarea
            required
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            placeholder="What did you observe? e.g. 'A competitor's video on this got unusually high saves.'"
            rows={2}
            className="rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-accent sm:col-span-3"
          />
          <div className="sm:col-span-3">
            <Button type="submit" variant="secondary" disabled={submitting}>
              {submitting ? "Adding…" : "Add signal"}
            </Button>
            {error && <span className="ml-3 text-xs text-bad">{error}</span>}
          </div>
        </form>

        {signals.length === 0 ? (
          <EmptyState
            icon={Radar}
            title="No research signals yet"
            description="Add what you're seeing elsewhere so the Opportunity Engine has real evidence to score against."
          />
        ) : (
          <ul className="divide-y divide-border">
            {signals.map((s) => (
              <li key={s.id} className="flex items-center justify-between py-2 text-sm">
                <span className="text-ink">{s.topic}</span>
                <span className="text-xs text-subtle">{s.subtopic ?? s.format ?? "—"}</span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
