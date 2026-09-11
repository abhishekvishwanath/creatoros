"use client";

import { useCallback, useEffect, useState } from "react";
import { TrendingUp, Sparkles } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfidenceBadge } from "@/components/ui/confidence-badge";
import { EmptyState } from "@/components/ui/empty-state";
import { getSession } from "@/lib/session";
import { listTrendInsights, analyzeTrends, ApiError } from "@/lib/api";
import type { TrendInsightRead } from "@/lib/types";
import { SkeletonText } from "@/components/ui/skeleton";

function momentumTone(momentum: string): "good" | "warn" | "bad" | "accent" {
  if (momentum === "rising" || momentum === "new") return "good";
  if (momentum === "declining") return "bad";
  return "warn";
}

function levelTone(level: string | null): "good" | "warn" | "bad" | "neutral" {
  if (level === "low") return "good";
  if (level === "medium") return "warn";
  if (level === "high") return "bad";
  return "neutral";
}

export function TrendsCard() {
  const [insights, setInsights] = useState<TrendInsightRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
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
      setInsights(await listTrendInsights(session.creatorId));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  async function handleAnalyze() {
    const session = getSession();
    if (!session) return;
    setAnalyzing(true);
    setError(null);
    setWarnings([]);
    try {
      const result = await analyzeTrends(session.creatorId);
      setWarnings(result.warnings);
      await refetch();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setAnalyzing(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-accent" /> Emerging topics
            </CardTitle>
            <CardDescription>
              Momentum, saturation, and relevance — computed from your own research signals, never equated with
              trendiness alone.
            </CardDescription>
          </div>
          <Button onClick={handleAnalyze} disabled={analyzing}>
            <Sparkles className="h-4 w-4" />
            {analyzing ? "Analyzing…" : "Analyze trends"}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {error && <p className="mb-2 text-xs text-bad">{error}</p>}
        {!error && warnings.length > 0 && <p className="mb-2 text-xs text-warn">{warnings.join(" ")}</p>}

        {loading ? (
          <SkeletonText lines={2} />
        ) : insights.length === 0 ? (
          <EmptyState
            icon={TrendingUp}
            title="No trend analysis yet"
            description="Add a few research signals with a shared topic, then analyze to see momentum, saturation, and how relevant each topic is to you specifically."
          />
        ) : (
          <ul className="space-y-3">
            {insights.map((t) => (
              <li key={t.id} className="border-b border-border pb-3 last:border-0 last:pb-0">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm font-medium text-ink">{t.topic}</p>
                  {t.confidence !== null && <ConfidenceBadge confidence={t.confidence} />}
                </div>
                {t.reasoning && <p className="mt-1 text-xs text-subtle">{t.reasoning}</p>}
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <Badge tone={momentumTone(t.momentum)}>{t.momentum}</Badge>
                  {t.saturation_estimate && (
                    <Badge tone={levelTone(t.saturation_estimate)}>{t.saturation_estimate} saturation</Badge>
                  )}
                  {t.durability && <Badge tone="neutral">{t.durability.replace("_", " ")}</Badge>}
                  {t.relevance_to_creator && (
                    <Badge tone={t.relevance_to_creator === "high" ? "good" : t.relevance_to_creator === "low" ? "bad" : "warn"}>
                      {t.relevance_to_creator} relevance
                    </Badge>
                  )}
                  <Badge tone="neutral">{t.signal_count} signal{t.signal_count === 1 ? "" : "s"}</Badge>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
