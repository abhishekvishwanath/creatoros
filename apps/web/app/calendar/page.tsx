"use client";

import { useCallback, useEffect, useState } from "react";
import { CalendarDays, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ConfidenceBadge } from "@/components/ui/confidence-badge";
import { getSession } from "@/lib/session";
import { generateStrategy, listStrategies, updateStrategyStatus, ApiError } from "@/lib/api";
import type { StrategyItemRead, StrategyRead } from "@/lib/types";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

const ROLE_TONES: Record<string, "good" | "warn" | "bad" | "accent" | "neutral"> = {
  reach: "accent",
  authority: "good",
  community: "warn",
  story: "neutral",
  conversion: "bad",
  experimental: "warn",
};

function itemsByDay(items: StrategyItemRead[]): Map<number, StrategyItemRead> {
  const map = new Map<number, StrategyItemRead>();
  for (const item of items) {
    if (item.day_of_week !== null) map.set(item.day_of_week, item);
  }
  return map;
}

export default function CalendarPage() {
  const [strategy, setStrategy] = useState<StrategyRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [activating, setActivating] = useState(false);
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
      const strategies = await listStrategies(session.creatorId);
      setStrategy(strategies[0] ?? null);
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
      const result = await generateStrategy(session.creatorId);
      setWarnings(result.warnings);
      if (result.strategy) setStrategy(result.strategy);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setGenerating(false);
    }
  }

  async function handleActivate() {
    const session = getSession();
    if (!session || !strategy) return;
    setActivating(true);
    setError(null);
    try {
      const updated = await updateStrategyStatus(session.creatorId, strategy.id, "active");
      setStrategy(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setActivating(false);
    }
  }

  const byDay = strategy ? itemsByDay(strategy.items) : new Map<number, StrategyItemRead>();

  return (
    <div>
      <PageHeader
        title="Calendar"
        description="Your content portfolio, production status, and capacity."
        action={
          <div className="flex flex-col items-end gap-1.5">
            <Button onClick={handleGenerate} disabled={generating}>
              <Sparkles className="h-4 w-4" />
              {generating ? "Generating…" : "Generate this week's strategy"}
            </Button>
            {error && <p className="max-w-xs text-right text-xs text-bad">{error}</p>}
            {!error && warnings.length > 0 && (
              <p className="max-w-xs text-right text-xs text-warn">{warnings.join(" ")}</p>
            )}
          </div>
        }
      />
      <div className="p-8">
        {loading ? (
          <p className="text-sm text-subtle">Loading…</p>
        ) : !strategy ? (
          <EmptyState
            icon={CalendarDays}
            title="Nothing scheduled yet"
            description="Content moves through IDEA → APPROVED → BRIEFED → SCRIPTED → RECORDED → EDITING → REVIEW → SCHEDULED → PUBLISHED → ANALYZING → LEARNED. Approve or save an opportunity in Opportunities, then generate a weekly strategy here."
          />
        ) : (
          <Card>
            <CardHeader>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle>This week's portfolio</CardTitle>
                  {strategy.summary && <CardDescription>{strategy.summary}</CardDescription>}
                </div>
                <div className="flex items-center gap-2">
                  {strategy.confidence !== null && <ConfidenceBadge confidence={strategy.confidence} />}
                  <Badge tone={strategy.status === "active" ? "good" : strategy.status === "completed" ? "neutral" : "warn"}>
                    {strategy.status}
                  </Badge>
                  {strategy.status === "draft" && (
                    <Button variant="secondary" onClick={handleActivate} disabled={activating}>
                      {activating ? "Activating…" : "Activate"}
                    </Button>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-7">
                {DAYS.map((day, index) => {
                  const item = byDay.get(index);
                  return (
                    <div key={day} className="rounded-lg border border-border p-3">
                      <p className="mb-2 text-xs font-medium text-subtle">{day}</p>
                      {item ? (
                        <div className="space-y-2">
                          <p className="text-sm text-ink">{item.opportunity_topic ?? "Untitled"}</p>
                          {item.portfolio_role && (
                            <Badge tone={ROLE_TONES[item.portfolio_role] ?? "neutral"}>{item.portfolio_role}</Badge>
                          )}
                        </div>
                      ) : (
                        <p className="text-xs text-subtle">—</p>
                      )}
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
