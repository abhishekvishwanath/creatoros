"use client";

import { useState } from "react";
import { Check, X, Bookmark } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfidenceBadge } from "@/components/ui/confidence-badge";
import { ApiError } from "@/lib/api";
import type { OpportunityRead, OpportunityStatus } from "@/lib/types";

const COMPONENT_LABELS: Record<string, string> = {
  audience_fit: "Audience fit",
  creator_fit: "Creator fit",
  demand: "Demand",
  novelty: "Novelty",
  evidence: "Evidence",
};

function levelTone(level: string | null): "good" | "warn" | "bad" | "neutral" {
  if (level === "low") return "good";
  if (level === "medium") return "warn";
  if (level === "high") return "bad";
  return "neutral";
}

export function OpportunityCard({
  opportunity,
  onStatusChange,
}: {
  opportunity: OpportunityRead;
  onStatusChange: (id: string, status: OpportunityStatus) => Promise<unknown>;
}) {
  const [updating, setUpdating] = useState<OpportunityStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleStatus(status: OpportunityStatus) {
    setUpdating(status);
    setError(null);
    try {
      await onStatusChange(opportunity.id, status);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save that — is the API running?");
    } finally {
      setUpdating(null);
    }
  }

  const isDecided = opportunity.status !== "pending";

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle>{opportunity.topic}</CardTitle>
            {opportunity.subtopic && <CardDescription>{opportunity.subtopic}</CardDescription>}
          </div>
          {opportunity.confidence !== null && <ConfidenceBadge confidence={opportunity.confidence} />}
        </div>
      </CardHeader>
      <CardContent>
        {opportunity.angle && <p className="mb-3 text-sm text-ink">{opportunity.angle}</p>}

        {opportunity.score_components && (
          <div className="mb-3 grid grid-cols-2 gap-x-4 gap-y-1.5 sm:grid-cols-5">
            {Object.entries(opportunity.score_components).map(([key, value]) => (
              <div key={key}>
                <p className="text-xs text-subtle">{COMPONENT_LABELS[key] ?? key}</p>
                <div className="mt-0.5 h-1.5 w-full overflow-hidden rounded-full bg-ink/8">
                  <div className="h-full rounded-full bg-accent" style={{ width: `${Math.round(value * 100)}%` }} />
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="mb-4 flex flex-wrap gap-1.5">
          {opportunity.format && <Badge tone="neutral">{opportunity.format}</Badge>}
          {opportunity.competition_level && (
            <Badge tone={levelTone(opportunity.competition_level)}>{opportunity.competition_level} competition</Badge>
          )}
          {opportunity.saturation_estimate && (
            <Badge tone={levelTone(opportunity.saturation_estimate)}>{opportunity.saturation_estimate} saturation</Badge>
          )}
          {opportunity.production_complexity && (
            <Badge tone={levelTone(opportunity.production_complexity)}>
              {opportunity.production_complexity} complexity
            </Badge>
          )}
          {opportunity.recommended_time_window && <Badge tone="accent">{opportunity.recommended_time_window}</Badge>}
        </div>

        {isDecided ? (
          <Badge tone={opportunity.status === "approved" ? "good" : opportunity.status === "rejected" ? "bad" : "neutral"}>
            {opportunity.status.replace("_", " ")}
          </Badge>
        ) : (
          <div>
            <div className="flex gap-2">
              <Button variant="secondary" disabled={!!updating} onClick={() => handleStatus("approved")}>
                <Check className="h-4 w-4" /> {updating === "approved" ? "…" : "Approve"}
              </Button>
              <Button variant="secondary" disabled={!!updating} onClick={() => handleStatus("rejected")}>
                <X className="h-4 w-4" /> {updating === "rejected" ? "…" : "Reject"}
              </Button>
              <Button variant="ghost" disabled={!!updating} onClick={() => handleStatus("saved_for_later")}>
                <Bookmark className="h-4 w-4" /> {updating === "saved_for_later" ? "…" : "Save"}
              </Button>
            </div>
            {error && <p className="mt-2 text-xs text-bad">{error}</p>}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
