"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CalendarDays, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ConfidenceBadge } from "@/components/ui/confidence-badge";
import { getSession } from "@/lib/session";
import {
  generateStrategy,
  listStrategies,
  updateStrategyStatus,
  listCalendarEvents,
  listBottlenecks,
  getCapacity,
  setCapacity,
  ApiError,
} from "@/lib/api";
import type { BottleneckRead, CalendarEventRead, StrategyItemRead, StrategyRead } from "@/lib/types";
import { SkeletonText } from "@/components/ui/skeleton";

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
  const [events, setEvents] = useState<CalendarEventRead[]>([]);
  const [bottlenecks, setBottlenecks] = useState<BottleneckRead[]>([]);
  const [capacity, setCapacityState] = useState<number | null>(null);
  const [capacityInput, setCapacityInput] = useState("");
  const [savingCapacity, setSavingCapacity] = useState(false);
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
      const [strategies, calendarEvents, bottleneckList, capacityRead] = await Promise.all([
        listStrategies(session.creatorId),
        listCalendarEvents(session.creatorId),
        listBottlenecks(session.creatorId),
        getCapacity(session.creatorId),
      ]);
      setStrategy(strategies[0] ?? null);
      setEvents(calendarEvents);
      setBottlenecks(bottleneckList);
      setCapacityState(capacityRead.items_per_week);
      setCapacityInput(capacityRead.items_per_week?.toString() ?? "");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  async function handleSaveCapacity() {
    const session = getSession();
    const parsed = Number(capacityInput);
    if (!session || !Number.isInteger(parsed) || parsed < 1) return;
    setSavingCapacity(true);
    setError(null);
    try {
      const result = await setCapacity(session.creatorId, parsed);
      setCapacityState(result.items_per_week);
      const freshBottlenecks = await listBottlenecks(session.creatorId);
      setBottlenecks(freshBottlenecks);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setSavingCapacity(false);
    }
  }

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
      <div className="space-y-4 p-8">
        {loading ? (
          <SkeletonText lines={2} />
        ) : (
          <>
            {bottlenecks.length > 0 && (
              <div className="space-y-2">
                {bottlenecks.map((b) => (
                  <div key={b.type} className="flex items-start gap-2 rounded-lg border border-warn/30 bg-warn/5 p-3">
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warn" />
                    <p className="text-sm text-ink">{b.message}</p>
                  </div>
                ))}
              </div>
            )}

            <Card>
              <CardHeader>
                <CardTitle>Weekly capacity</CardTitle>
                <CardDescription>
                  How many pieces you can realistically produce in a week — used to flag when scheduling exceeds it.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-end gap-2">
                  <div>
                    <label className="block text-xs text-subtle" htmlFor="capacity-input">Items per week</label>
                    <input
                      id="capacity-input"
                      type="number"
                      min={1}
                      max={50}
                      value={capacityInput}
                      onChange={(e) => setCapacityInput(e.target.value)}
                      className="w-24 rounded-md border border-border bg-transparent px-2 py-1.5 text-sm text-ink"
                    />
                  </div>
                  <Button variant="secondary" onClick={handleSaveCapacity} disabled={savingCapacity || !capacityInput}>
                    {savingCapacity ? "Saving…" : capacity !== null ? "Update" : "Set capacity"}
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Scheduled & published</CardTitle>
                <CardDescription>Content that has moved past review into production operations.</CardDescription>
              </CardHeader>
              <CardContent>
                {events.length === 0 ? (
                  <EmptyState
                    icon={CalendarDays}
                    title="Nothing scheduled yet"
                    description="Once a piece passes editorial review, schedule it from the Create page and it will show up here."
                  />
                ) : (
                  <ul className="divide-y divide-border">
                    {events.map((event) => (
                      <li key={event.id} className="flex items-center justify-between py-2">
                        <div>
                          <p className="text-sm text-ink">{event.content_title ?? "Untitled"}</p>
                          <p className="text-xs text-subtle">
                            {event.scheduled_at ? new Date(event.scheduled_at).toLocaleString() : "No date"}
                            {event.platform ? ` · ${event.platform}` : ""}
                          </p>
                        </div>
                        <Badge tone={event.status === "published" ? "good" : event.status === "missed" ? "bad" : "accent"}>
                          {event.status}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            {!strategy ? (
              <EmptyState
                icon={CalendarDays}
                title="No weekly strategy yet"
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
                      <Badge
                        tone={strategy.status === "active" ? "good" : strategy.status === "completed" ? "neutral" : "warn"}
                      >
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
          </>
        )}
      </div>
    </div>
  );
}
