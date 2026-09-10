"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { BarChart3, Lightbulb } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfidenceBadge } from "@/components/ui/confidence-badge";
import { EmptyState } from "@/components/ui/empty-state";
import { getSession } from "@/lib/session";
import { getLearnings, getPerformanceOverview, retractLearning, syncLearnings, ApiError } from "@/lib/api";
import type { LearningRead, PerformanceOverviewItem } from "@/lib/types";

function ratioTone(ratio: number): "good" | "warn" | "bad" {
  if (ratio >= 1.3) return "good";
  if (ratio >= 0.7) return "warn";
  return "bad";
}

function ViewsRatio({ snapshot }: { snapshot: PerformanceOverviewItem["latest_snapshot"] }) {
  const comparison = snapshot?.baseline_comparison as Record<string, number> | null;
  const ratio = comparison?.["views_vs_overall_median"];
  if (typeof ratio !== "number") return null;
  return <Badge tone={ratioTone(ratio)}>{ratio.toFixed(1)}x your median views</Badge>;
}

function DiagnosisSummary({ snapshot }: { snapshot: PerformanceOverviewItem["latest_snapshot"] }) {
  const comparison = snapshot?.baseline_comparison as { diagnosis?: { summary?: string } } | null;
  const summary = comparison?.diagnosis?.summary;
  if (!summary) return null;
  return <p className="mt-1 text-sm text-subtle">{summary}</p>;
}

// Both loops write into the same StrategicLearning table (CLAUDE.md Part
// II §72) — category is the only thing that distinguishes a content
// finding ("performance/...") from a commercial one ("commercial/...").
type LearningFilter = "all" | "content" | "commercial";

function isCommercialLearning(learning: LearningRead): boolean {
  return (learning.category ?? "").startsWith("commercial/");
}

export default function AnalyticsPage() {
  const [overview, setOverview] = useState<PerformanceOverviewItem[]>([]);
  const [learnings, setLearnings] = useState<LearningRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [busyLearningId, setBusyLearningId] = useState<string | null>(null);
  const [learningFilter, setLearningFilter] = useState<LearningFilter>("all");

  const refetch = useCallback(async () => {
    const session = getSession();
    if (!session) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [overviewData, learningsData] = await Promise.all([
        getPerformanceOverview(session.creatorId),
        getLearnings(session.creatorId),
      ]);
      setOverview(overviewData);
      setLearnings(learningsData);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  async function handleSync() {
    const session = getSession();
    if (!session) return;
    setSyncing(true);
    try {
      setLearnings(await syncLearnings(session.creatorId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to sync learnings.");
    } finally {
      setSyncing(false);
    }
  }

  async function handleRetract(learningId: string) {
    const session = getSession();
    if (!session) return;
    setBusyLearningId(learningId);
    try {
      await retractLearning(session.creatorId, learningId);
      setLearnings((prev) => prev.filter((l) => l.id !== learningId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to retract learning.");
    } finally {
      setBusyLearningId(null);
    }
  }

  const hasCommercialLearnings = useMemo(() => learnings.some(isCommercialLearning), [learnings]);
  const visibleLearnings = useMemo(() => {
    if (learningFilter === "all") return learnings;
    return learnings.filter((l) => isCommercialLearning(l) === (learningFilter === "commercial"));
  }, [learnings, learningFilter]);

  // If retracting the last learning in the current filter empties it out,
  // fall back to "all" instead of leaving a blank list with no visible way
  // back (the filter pills themselves disappear once hasCommercialLearnings
  // goes false, so "commercial"/"content" could otherwise become a dead end).
  useEffect(() => {
    if (learningFilter !== "all" && learnings.length > 0 && visibleLearnings.length === 0) {
      setLearningFilter("all");
    }
  }, [learningFilter, learnings, visibleLearnings]);

  return (
    <div>
      <PageHeader title="Analytics" description="What changed, why it may have changed, and what to test next." />
      <div className="p-8 space-y-8">
        {loading ? (
          <p className="text-sm text-subtle">Loading…</p>
        ) : error ? (
          <p className="text-sm text-bad">{error}</p>
        ) : (
          <>
            <section>
              {overview.length === 0 ? (
                <EmptyState
                  icon={BarChart3}
                  title="No performance data yet"
                  description="Once content is published, log its metrics from the Create page and diagnoses will appear here compared against your own baseline — never raw numbers without interpretation."
                />
              ) : (
                <Card>
                  <CardContent className="p-0">
                    <ul className="divide-y divide-border">
                      {overview.map((row) => (
                        <li key={row.content_item_id} className="p-4">
                          <Link href={`/create?item=${row.content_item_id}`} className="block">
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <p className="text-sm font-medium text-ink">{row.title ?? row.topic ?? "Untitled"}</p>
                                <p className="text-xs text-subtle">
                                  {row.format ?? "—"}
                                  {row.platform ? ` · ${row.platform}` : ""}
                                </p>
                              </div>
                              <div className="flex items-center gap-2">
                                {row.latest_snapshot ? (
                                  <>
                                    <ViewsRatio snapshot={row.latest_snapshot} />
                                    {row.latest_snapshot.views !== null && (
                                      <Badge tone="neutral">{row.latest_snapshot.views.toLocaleString()} views</Badge>
                                    )}
                                  </>
                                ) : (
                                  <Badge tone="neutral">No metrics logged</Badge>
                                )}
                              </div>
                            </div>
                            <DiagnosisSummary snapshot={row.latest_snapshot} />
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              )}
            </section>

            <section>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-semibold text-ink">Strategic learnings</h2>
                <Button variant="secondary" onClick={handleSync} disabled={syncing}>
                  {syncing ? "Syncing…" : "Re-sync from diagnoses"}
                </Button>
              </div>
              {learnings.length === 0 ? (
                <EmptyState
                  icon={Lightbulb}
                  title="No learnings yet"
                  description="Once at least two diagnosed posts point to the same factor (e.g. a hook type or pacing pattern), or two resolved deals point to the same brand category, it becomes a persistent learning here — and future strategy, briefs, and brand scoring will take it into account."
                />
              ) : (
                <>
                  {hasCommercialLearnings && (
                    <div className="mb-2 flex gap-1.5">
                      {(["all", "content", "commercial"] as const).map((f) => (
                        <button
                          key={f}
                          onClick={() => setLearningFilter(f)}
                          className={`rounded-full border px-2.5 py-1 text-xs capitalize ${
                            learningFilter === f
                              ? "border-accent bg-accent-soft text-accent"
                              : "border-border text-subtle hover:text-ink"
                          }`}
                        >
                          {f}
                        </button>
                      ))}
                    </div>
                  )}
                  <Card>
                    <CardContent className="p-0">
                      <ul className="divide-y divide-border">
                        {visibleLearnings.map((learning) => {
                          const commercial = isCommercialLearning(learning);
                          return (
                            <li key={learning.id} className="p-4 flex items-start justify-between gap-3">
                              <div>
                                <p className="text-sm text-ink">{learning.statement}</p>
                                <div className="mt-1 flex items-center gap-2">
                                  <ConfidenceBadge confidence={learning.confidence} />
                                  <Badge tone="neutral">{learning.scope}</Badge>
                                  <Badge tone="neutral">
                                    {learning.evidence_ids.length} {commercial ? "deals" : "posts"}
                                  </Badge>
                                  {commercial && <Badge tone="accent">commercial</Badge>}
                                </div>
                              </div>
                              <Button
                                variant="ghost"
                                onClick={() => handleRetract(learning.id)}
                                disabled={busyLearningId === learning.id}
                              >
                                Not accurate
                              </Button>
                            </li>
                          );
                        })}
                      </ul>
                    </CardContent>
                  </Card>
                </>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
}
