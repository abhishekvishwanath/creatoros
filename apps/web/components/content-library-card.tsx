"use client";

import { FormEvent, useState } from "react";
import { Library } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { getSession } from "@/lib/session";
import { ingestContent, ApiError } from "@/lib/api";
import type { RecentContentSummary } from "@/lib/types";

export function ContentLibraryCard({
  recentContent,
  onIngested,
}: {
  recentContent: RecentContentSummary[];
  onIngested: () => Promise<unknown>;
}) {
  const [title, setTitle] = useState("");
  const [platform, setPlatform] = useState("");
  const [transcript, setTranscript] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const session = getSession();
    if (!session) return;
    setSubmitting(true);
    setError(null);
    try {
      await ingestContent(session.creatorId, {
        title,
        platform: platform || undefined,
        transcript: transcript || undefined,
      });
      setTitle("");
      setPlatform("");
      setTranscript("");
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
          <Library className="h-4 w-4 text-accent" /> Content library
        </CardTitle>
        <CardDescription>
          Paste in past scripts, captions, or transcripts — this is what voice and topic analysis reads from.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="mb-4 grid grid-cols-1 gap-2 sm:grid-cols-[1fr_140px_auto]">
          <input
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Title (e.g. 5 productivity hacks)"
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
            <option value="linkedin">LinkedIn</option>
            <option value="other">Other</option>
          </select>
          <textarea
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
            placeholder="Script, caption, or transcript text (optional but recommended)"
            rows={2}
            className="rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-accent sm:col-span-3"
          />
          <div className="sm:col-span-3">
            <Button type="submit" variant="secondary" disabled={submitting}>
              {submitting ? "Adding…" : "Add content"}
            </Button>
            {error && <span className="ml-3 text-xs text-bad">{error}</span>}
          </div>
        </form>

        {recentContent.length === 0 ? (
          <EmptyState
            icon={Library}
            title="No content ingested yet"
            description="Add a few past posts above so the Creator Intelligence Agent has real material instead of onboarding fields alone."
          />
        ) : (
          <ul className="divide-y divide-border">
            {recentContent.map((c) => (
              <li key={c.id} className="flex items-center justify-between py-2 text-sm">
                <span className="text-ink">{c.title}</span>
                <span className="text-xs text-subtle">
                  {c.platform ?? "—"}
                  {c.has_transcript ? " · has transcript" : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
