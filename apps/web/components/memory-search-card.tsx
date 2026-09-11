"use client";

import { FormEvent, useState } from "react";
import { Search } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { getSession } from "@/lib/session";
import { searchMemory, ApiError } from "@/lib/api";
import type { MemorySearchResult } from "@/lib/types";

const SOURCE_LABEL: Record<string, string> = {
  script: "Script",
  transcript: "Video transcript",
  comment: "Audience comment",
  research: "Research signal",
  learning: "Learning",
};

export function MemorySearchCard() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<MemorySearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSearch(e: FormEvent) {
    e.preventDefault();
    const session = getSession();
    if (!session || !query.trim()) return;
    setSearching(true);
    setError(null);
    try {
      const found = await searchMemory(session.creatorId, query.trim());
      setResults(found);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setSearching(false);
    }
  }

  return (
    <Card className="lg:col-span-2">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Search className="h-4 w-4 text-accent" /> Search your memory
        </CardTitle>
        <CardDescription>
          Semantic search over everything embedded so far — scripts, transcripts, audience comments, research, and
          learnings — ranked by meaning, not keyword match.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSearch} className="mb-3 flex gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. anything about pricing objections"
            className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-accent"
          />
          <Button type="submit" variant="secondary" disabled={searching || !query.trim()}>
            {searching ? "Searching…" : "Search"}
          </Button>
        </form>
        {error && <p className="mb-2 text-xs text-bad">{error}</p>}
        {results !== null && results.length === 0 && !error && (
          <p className="text-sm text-subtle">No matches yet — nothing embedded so far is close to that query.</p>
        )}
        {results && results.length > 0 && (
          <ul className="divide-y divide-border">
            {results.map((r) => (
              <li key={r.id} className="py-2">
                <span className="mb-1 inline-block rounded bg-canvas px-1.5 py-0.5 text-xs text-subtle">
                  {SOURCE_LABEL[r.source_type] ?? r.source_type}
                </span>
                <p className="text-sm text-ink">{r.text}</p>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
