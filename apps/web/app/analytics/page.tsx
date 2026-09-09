"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { BarChart3 } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { getSession } from "@/lib/session";
import { getPerformanceOverview, ApiError } from "@/lib/api";
import type { PerformanceOverviewItem } from "@/lib/types";

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

export default function AnalyticsPage() {
  const [overview, setOverview] = useState<PerformanceOverviewItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    const session = getSession();
    if (!session) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setOverview(await getPerformanceOverview(session.creatorId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return (
    <div>
      <PageHeader title="Analytics" description="What changed, why it may have changed, and what to test next." />
      <div className="p-8">
        {loading ? (
          <p className="text-sm text-subtle">Loading…</p>
        ) : error ? (
          <p className="text-sm text-bad">{error}</p>
        ) : overview.length === 0 ? (
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
      </div>
    </div>
  );
}
