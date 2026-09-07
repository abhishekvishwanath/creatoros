"use client";

import Link from "next/link";
import { AlertTriangle, ArrowRight, Sparkles, TrendingUp, Target } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { useCreatorState } from "@/lib/use-creator-state";

export default function HomePage() {
  const { state, loading } = useCreatorState();

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
            <EmptyState
              icon={Sparkles}
              title="Opportunity engine not connected yet"
              description="Once research and audience intelligence are wired up, ranked opportunities with evidence will show up here."
              action={
                <Link href="/opportunities" className="inline-flex items-center gap-1 text-sm font-medium text-accent">
                  View opportunities <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              }
            />
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
            <EmptyState
              icon={TrendingUp}
              title="No performance data yet"
              description="Connect content and publish history to start seeing baseline comparisons."
            />
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Current strategy</CardTitle>
            <CardDescription>This week's content portfolio.</CardDescription>
          </CardHeader>
          <CardContent>
            <EmptyState
              icon={Sparkles}
              title="No active strategy"
              description="A weekly strategy will appear here once the Strategy Agent has enough creator, audience, and research signal to work with."
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
