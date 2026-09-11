"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ArrowRight, Sparkles, TrendingUp, Target, Handshake } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ConfidenceBadge } from "@/components/ui/confidence-badge";
import { EmptyState } from "@/components/ui/empty-state";
import { useCreatorState } from "@/lib/use-creator-state";
import { getSession } from "@/lib/session";
import { listOpportunities, listStrategies, getPerformanceOverview, listBrandRadar } from "@/lib/api";
import type { OpportunityRead, StrategyRead, PerformanceOverviewItem, BrandRadarItem } from "@/lib/types";

function ratioTone(ratio: number): "good" | "warn" | "bad" {
  if (ratio >= 1.3) return "good";
  if (ratio >= 0.7) return "warn";
  return "bad";
}

export default function HomePage() {
  const { state, loading } = useCreatorState();
  const [opportunities, setOpportunities] = useState<OpportunityRead[]>([]);
  const [strategy, setStrategy] = useState<StrategyRead | null>(null);
  const [performance, setPerformance] = useState<PerformanceOverviewItem[]>([]);
  const [brandRadar, setBrandRadar] = useState<BrandRadarItem[]>([]);
  const [widgetsLoading, setWidgetsLoading] = useState(true);

  const loadWidgets = useCallback(async () => {
    const session = getSession();
    if (!session) {
      setWidgetsLoading(false);
      return;
    }
    setWidgetsLoading(true);
    try {
      const [opps, strategies, perf, radar] = await Promise.all([
        listOpportunities(session.creatorId),
        listStrategies(session.creatorId),
        getPerformanceOverview(session.creatorId),
        listBrandRadar(session.creatorId),
      ]);
      setOpportunities(opps);
      setStrategy(strategies.find((s) => s.status === "active") ?? strategies[0] ?? null);
      setPerformance(perf);
      setBrandRadar(radar);
    } finally {
      setWidgetsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadWidgets();
  }, [loadWidgets]);

  if (loading) {
    return <div className="p-8 text-sm text-subtle">Loading…</div>;
  }

  if (!state) {
    return <div className="p-8 text-sm text-bad">Couldn&apos;t load your creator profile. Is the API running?</div>;
  }

  const blockers: string[] = [];
  if (!state.positioning) blockers.push("Creator DNA hasn't been built yet — positioning is unknown.");
  if (!state.voice) blockers.push("Voice profile hasn't been built yet — content will lack a distinct voice.");
  if (!state.audience) blockers.push("Audience profile hasn't been built yet — recommendations can't be audience-fit.");
  if (state.active_goals.length === 0) blockers.push("No active goals set — strategy can't be prioritized against a business objective.");

  const topOpportunities = opportunities
    .filter((o) => o.status === "pending")
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
    .slice(0, 5);

  const recentWithSnapshot = performance.filter((p) => p.latest_snapshot);
  const topBrandOpportunity = brandRadar
    .filter((r) => !r.opportunity.prohibited_conflict)
    .sort((a, b) => (b.opportunity.score ?? 0) - (a.opportunity.score ?? 0))[0];

  return (
    <div>
      <PageHeader
        title={`Welcome back, ${state.creator.name}`}
        description="What matters this week?"
      />
      <div className="grid grid-cols-1 gap-4 p-8 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Target className="h-4 w-4 text-accent" /> Next best opportunities
            </CardTitle>
            <CardDescription>The strongest things you should make next, and why.</CardDescription>
          </CardHeader>
          <CardContent>
            {widgetsLoading ? (
              <p className="text-sm text-subtle">Loading…</p>
            ) : topOpportunities.length === 0 ? (
              <EmptyState
                icon={Sparkles}
                title="No pending opportunities"
                description="Add research signals and generate opportunities to see ranked, evidence-backed ideas here."
                action={
                  <Link href="/opportunities" className="inline-flex items-center gap-1 text-sm font-medium text-accent">
                    Go to Opportunities <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                }
              />
            ) : (
              <ul className="space-y-3">
                {topOpportunities.map((o) => (
                  <li key={o.id} className="flex items-start justify-between gap-3 border-b border-line pb-3 last:border-0 last:pb-0">
                    <div>
                      <p className="text-sm font-medium text-ink">{o.topic}</p>
                      {o.angle && <p className="mt-0.5 text-xs text-subtle">{o.angle}</p>}
                      <div className="mt-1.5 flex flex-wrap gap-1.5">
                        {o.format && <Badge tone="neutral">{o.format}</Badge>}
                        {o.recommended_time_window && <Badge tone="accent">{o.recommended_time_window}</Badge>}
                      </div>
                    </div>
                    {o.confidence !== null && <ConfidenceBadge confidence={o.confidence} />}
                  </li>
                ))}
                <Link href="/opportunities" className="inline-flex items-center gap-1 text-sm font-medium text-accent">
                  View all opportunities <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-warn" /> Blockers
            </CardTitle>
            <CardDescription>What's standing between you and a working strategy.</CardDescription>
          </CardHeader>
          <CardContent>
            {blockers.length === 0 ? (
              <p className="text-sm text-subtle">No blockers detected.</p>
            ) : (
              <ul className="space-y-2">
                {blockers.map((b) => (
                  <li key={b} className="flex items-start gap-2 text-sm text-ink">
                    <Badge tone="warn" className="mt-0.5 shrink-0">
                      open
                    </Badge>
                    <span>{b}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-good" /> Growth movement
            </CardTitle>
            <CardDescription>How this week compares to your baseline.</CardDescription>
          </CardHeader>
          <CardContent>
            {widgetsLoading ? (
              <p className="text-sm text-subtle">Loading…</p>
            ) : recentWithSnapshot.length === 0 ? (
              <EmptyState
                icon={TrendingUp}
                title="No performance data yet"
                description="Log metrics on a published piece to start seeing baseline comparisons."
                action={
                  <Link href="/analytics" className="inline-flex items-center gap-1 text-sm font-medium text-accent">
                    Go to Analytics <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                }
              />
            ) : (
              <ul className="space-y-3">
                {recentWithSnapshot.slice(0, 4).map((p) => {
                  const comparison = p.latest_snapshot?.baseline_comparison as Record<string, number> | null;
                  const ratio = comparison?.["views_vs_overall_median"];
                  return (
                    <li key={p.content_item_id} className="flex items-center justify-between gap-3">
                      <p className="truncate text-sm text-ink">{p.title ?? p.topic ?? "Untitled"}</p>
                      {typeof ratio === "number" && <Badge tone={ratioTone(ratio)}>{ratio.toFixed(1)}x median</Badge>}
                    </li>
                  );
                })}
                <Link href="/analytics" className="inline-flex items-center gap-1 text-sm font-medium text-accent">
                  View analytics <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </ul>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Current strategy</CardTitle>
            <CardDescription>This week's content portfolio.</CardDescription>
          </CardHeader>
          <CardContent>
            {widgetsLoading ? (
              <p className="text-sm text-subtle">Loading…</p>
            ) : !strategy ? (
              <EmptyState
                icon={Sparkles}
                title="No active strategy"
                description="Approve or save opportunities, then generate a weekly strategy in Calendar."
                action={
                  <Link href="/calendar" className="inline-flex items-center gap-1 text-sm font-medium text-accent">
                    Go to Calendar <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                }
              />
            ) : (
              <div>
                {strategy.summary && <p className="mb-3 text-sm text-ink">{strategy.summary}</p>}
                <div className="mb-3 flex items-center gap-2">
                  <Badge tone={strategy.status === "active" ? "good" : "neutral"}>{strategy.status}</Badge>
                  {strategy.confidence !== null && <ConfidenceBadge confidence={strategy.confidence} />}
                </div>
                <ul className="space-y-1.5">
                  {strategy.items.map((item) => (
                    <li key={item.id} className="flex items-center justify-between text-sm">
                      <span className="text-ink">{item.opportunity_topic ?? "Untitled"}</span>
                      {item.portfolio_role && <Badge tone="neutral">{item.portfolio_role}</Badge>}
                    </li>
                  ))}
                </ul>
                <Link href="/calendar" className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-accent">
                  View calendar <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </div>
            )}
          </CardContent>
        </Card>

        {(widgetsLoading || topBrandOpportunity) && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Handshake className="h-4 w-4 text-accent" /> Top brand fit
              </CardTitle>
              <CardDescription>Strongest sponsorship opportunity right now.</CardDescription>
            </CardHeader>
            <CardContent>
              {widgetsLoading ? (
                <p className="text-sm text-subtle">Loading…</p>
              ) : topBrandOpportunity ? (
                <div>
                  <p className="text-sm font-medium text-ink">{topBrandOpportunity.brand.name}</p>
                  {topBrandOpportunity.opportunity.reasons && (
                    <p className="mt-1 text-xs text-subtle">{topBrandOpportunity.opportunity.reasons}</p>
                  )}
                  <div className="mt-2 flex items-center gap-2">
                    {topBrandOpportunity.opportunity.score !== null && (
                      <Badge tone="accent">{Math.round(topBrandOpportunity.opportunity.score * 100)} fit</Badge>
                    )}
                    <ConfidenceBadge confidence={topBrandOpportunity.opportunity.confidence} />
                  </div>
                  <Link href="/brands" className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-accent">
                    View brand radar <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </div>
              ) : null}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
