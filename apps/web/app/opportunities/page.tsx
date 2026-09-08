"use client";

import { useCallback, useEffect, useState } from "react";
import { Lightbulb, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";
import { OpportunityCard } from "@/components/opportunity-card";
import { getSession } from "@/lib/session";
import { generateOpportunities, listOpportunities, updateOpportunityStatus, ApiError } from "@/lib/api";
import type { OpportunityRead, OpportunityStatus } from "@/lib/types";

export default function OpportunitiesPage() {
  const [opportunities, setOpportunities] = useState<OpportunityRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);

  const refetch = useCallback(async () => {
    const session = getSession();
    if (!session) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      setOpportunities(await listOpportunities(session.creatorId));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  async function handleGenerate() {
    const session = getSession();
    if (!session) return;
    setGenerating(true);
    setError(null);
    setWarnings([]);
    try {
      const result = await generateOpportunities(session.creatorId);
      setWarnings(result.warnings);
      await refetch();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setGenerating(false);
    }
  }

  async function handleStatusChange(id: string, status: OpportunityStatus) {
    const session = getSession();
    if (!session) return;
    const updated = await updateOpportunityStatus(session.creatorId, id, status);
    setOpportunities((prev) => prev.map((o) => (o.id === id ? updated : o)));
  }

  return (
    <div>
      <PageHeader
        title="Opportunities"
        description="The strongest things you should make next, ranked and explained — never a single opaque score."
        action={
          <div className="flex flex-col items-end gap-1.5">
            <Button onClick={handleGenerate} disabled={generating}>
              <Sparkles className="h-4 w-4" />
              {generating ? "Generating…" : "Generate opportunities"}
            </Button>
            {error && <p className="max-w-xs text-right text-xs text-bad">{error}</p>}
            {!error && warnings.length > 0 && (
              <p className="max-w-xs text-right text-xs text-warn">{warnings.join(" ")}</p>
            )}
          </div>
        }
      />
      <div className="grid grid-cols-1 gap-4 p-8 lg:grid-cols-2">
        {loading ? (
          <p className="text-sm text-subtle">Loading…</p>
        ) : opportunities.length === 0 ? (
          <div className="lg:col-span-2">
            <EmptyState
              icon={Lightbulb}
              title="No opportunities yet"
              description="Opportunities are generated from creator fit, audience fit, demand, novelty, and evidence against your ingested research signals. Add signals in Research, then generate here."
            />
          </div>
        ) : (
          opportunities.map((o) => (
            <OpportunityCard key={o.id} opportunity={o} onStatusChange={handleStatusChange} />
          ))
        )}
      </div>
    </div>
  );
}
