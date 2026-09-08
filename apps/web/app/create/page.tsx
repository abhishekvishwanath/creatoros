"use client";

import { useCallback, useEffect, useState } from "react";
import { PenSquare, Sparkles, ArrowLeft, Lightbulb } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { getSession } from "@/lib/session";
import {
  listOpportunities,
  listContentItems,
  createContentFromOpportunity,
  getContentDetail,
  generateBrief,
  generateScript,
  reviewScript,
  ApiError,
} from "@/lib/api";
import type { ContentDetailRead, ContentItemRead, OpportunityRead } from "@/lib/types";

const IN_PROGRESS_STATUSES = new Set(["APPROVED", "BRIEFED", "SCRIPTED", "REVIEW"]);

function severityTone(severity: string): "good" | "warn" | "bad" {
  if (severity === "high") return "bad";
  if (severity === "medium") return "warn";
  return "good";
}

export default function CreatePage() {
  const [opportunities, setOpportunities] = useState<OpportunityRead[]>([]);
  const [contentItems, setContentItems] = useState<ContentItemRead[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ContentDetailRead | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [starting, setStarting] = useState<string | null>(null);
  const [busy, setBusy] = useState<"brief" | "script" | "review" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);

  const refetchLists = useCallback(async () => {
    const session = getSession();
    if (!session) {
      setLoadingList(false);
      return;
    }
    setLoadingList(true);
    try {
      const [opps, items] = await Promise.all([
        listOpportunities(session.creatorId),
        listContentItems(session.creatorId),
      ]);
      setOpportunities(opps.filter((o) => o.status === "approved" || o.status === "saved_for_later"));
      setContentItems(items.filter((i) => IN_PROGRESS_STATUSES.has(i.status)));
    } finally {
      setLoadingList(false);
    }
  }, []);

  useEffect(() => {
    refetchLists();
  }, [refetchLists]);

  const refetchDetail = useCallback(async (id: string) => {
    const session = getSession();
    if (!session) return;
    setLoadingDetail(true);
    try {
      setDetail(await getContentDetail(session.creatorId, id));
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  useEffect(() => {
    if (selectedId) refetchDetail(selectedId);
  }, [selectedId, refetchDetail]);

  // A stale error/warning from one item or view must never leak into an
  // unrelated one — navigating always clears them, and every action clears
  // them again before it starts.
  function selectItem(id: string | null) {
    setSelectedId(id);
    setDetail(null);
    setError(null);
    setWarnings([]);
  }

  async function handleStart(opportunityId: string) {
    const session = getSession();
    if (!session) return;
    setStarting(opportunityId);
    setError(null);
    try {
      const item = await createContentFromOpportunity(session.creatorId, opportunityId);
      await refetchLists();
      selectItem(item.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setStarting(null);
    }
  }

  async function handleGenerateBrief() {
    const session = getSession();
    if (!session || !selectedId) return;
    setBusy("brief");
    setError(null);
    setWarnings([]);
    try {
      const result = await generateBrief(session.creatorId, selectedId);
      setWarnings(result.warnings);
      await refetchDetail(selectedId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setBusy(null);
    }
  }

  async function handleGenerateScript() {
    const session = getSession();
    if (!session || !selectedId) return;
    setBusy("script");
    setError(null);
    setWarnings([]);
    try {
      const result = await generateScript(session.creatorId, selectedId);
      setWarnings(result.warnings);
      await refetchDetail(selectedId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setBusy(null);
    }
  }

  async function handleReview(scriptId: string) {
    const session = getSession();
    if (!session || !selectedId) return;
    setBusy("review");
    setError(null);
    setWarnings([]);
    try {
      const result = await reviewScript(session.creatorId, selectedId, scriptId);
      setWarnings(result.warnings);
      await refetchDetail(selectedId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setBusy(null);
    }
  }

  if (selectedId) {
    const item = detail?.item;
    const brief = detail?.brief ?? null;
    const scripts = detail?.scripts ?? [];
    const latestScript = scripts.length > 0 ? scripts[scripts.length - 1] : null;
    const canReview = latestScript && (latestScript.status === "draft" || latestScript.status === "rewritten");

    return (
      <div>
        <PageHeader
          title={item?.topic ?? "Create"}
          description="Angle → hook → brief → script → critique → improved script."
          action={
            <Button
              variant="ghost"
              onClick={() => selectItem(null)}
            >
              <ArrowLeft className="h-4 w-4" /> Back
            </Button>
          }
        />
        <div className="grid grid-cols-1 gap-4 p-8">
          {error && <p className="text-sm text-bad">{error}</p>}
          {!error && warnings.length > 0 && <p className="text-sm text-warn">{warnings.join(" ")}</p>}

          <Card>
            <CardHeader>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle>Brief</CardTitle>
                  <CardDescription>Objective, angle, hook, and structure.</CardDescription>
                </div>
                <Button onClick={handleGenerateBrief} disabled={busy !== null || loadingDetail}>
                  <Sparkles className="h-4 w-4" />
                  {busy === "brief" ? "Generating…" : brief ? "Regenerate brief" : "Generate brief"}
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {loadingDetail ? (
                <p className="text-sm text-subtle">Loading…</p>
              ) : brief ? (
                <div className="space-y-2 text-sm">
                  <p><span className="font-medium text-ink">Angle:</span> <span className="text-ink">{brief.angle}</span></p>
                  {brief.hook && (
                    <p><span className="font-medium text-ink">Hook ({brief.hook_type}):</span> <span className="text-ink">{brief.hook}</span></p>
                  )}
                  {brief.key_points && brief.key_points.length > 0 && (
                    <div>
                      <span className="font-medium text-ink">Key points:</span>
                      <ul className="ml-4 list-disc text-subtle">
                        {brief.key_points.map((k, i) => <li key={i}>{k}</li>)}
                      </ul>
                    </div>
                  )}
                  {brief.cta && <p><span className="font-medium text-ink">CTA:</span> <span className="text-subtle">{brief.cta}</span></p>}
                </div>
              ) : (
                <EmptyState icon={PenSquare} title="No brief yet" description="Generate a brief to give the Script Agent a well-defined job." />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle>Script</CardTitle>
                  <CardDescription>Platform-native, in the creator's voice.</CardDescription>
                </div>
                <Button onClick={handleGenerateScript} disabled={!brief || busy !== null || loadingDetail}>
                  <Sparkles className="h-4 w-4" />
                  {busy === "script" ? "Generating…" : latestScript ? "Regenerate script" : "Generate script"}
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {loadingDetail ? (
                <p className="text-sm text-subtle">Loading…</p>
              ) : latestScript ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <Badge tone="neutral">v{latestScript.version_number}</Badge>
                    <Badge tone={latestScript.status === "final" ? "good" : latestScript.status === "critiqued" ? "warn" : "neutral"}>
                      {latestScript.status}
                    </Badge>
                  </div>
                  <p className="whitespace-pre-wrap text-sm text-ink">{latestScript.body}</p>
                  {latestScript.hook_variants && latestScript.hook_variants.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-subtle">Alternate hooks</p>
                      <ul className="ml-4 list-disc text-sm text-subtle">
                        {latestScript.hook_variants.map((h, i) => <li key={i}>{h}</li>)}
                      </ul>
                    </div>
                  )}
                  {canReview && (
                    <Button variant="secondary" onClick={() => handleReview(latestScript.id)} disabled={busy !== null}>
                      {busy === "review" ? "Reviewing…" : "Send for editorial review"}
                    </Button>
                  )}
                  {latestScript.critic_score !== null && (
                    <div className="rounded-lg border border-border p-3">
                      <p className="mb-2 text-sm font-medium text-ink">
                        Critic score: {latestScript.critic_score}/100
                      </p>
                      {latestScript.critic_issues && latestScript.critic_issues.length > 0 && (
                        <ul className="space-y-1.5">
                          {latestScript.critic_issues.map((issue, i) => (
                            <li key={i} className="flex items-start gap-2 text-sm">
                              <Badge tone={severityTone(issue.severity)}>{issue.type}</Badge>
                              <span className="text-subtle">{issue.suggestion}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                <EmptyState icon={PenSquare} title="No script yet" description="Generate a brief first, then a script." />
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="Create" description="Angle → hook → brief → script → critique → improved script." />
      <div className="grid grid-cols-1 gap-4 p-8 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Continue in progress</CardTitle>
            <CardDescription>Pieces already started.</CardDescription>
          </CardHeader>
          <CardContent>
            {loadingList ? (
              <p className="text-sm text-subtle">Loading…</p>
            ) : contentItems.length === 0 ? (
              <EmptyState icon={PenSquare} title="Nothing in progress" description="Start from an opportunity on the right." />
            ) : (
              <ul className="divide-y divide-border">
                {contentItems.map((item) => (
                  <li key={item.id} className="flex items-center justify-between py-2">
                    <span className="text-sm text-ink">{item.topic ?? item.title}</span>
                    <div className="flex items-center gap-2">
                      <Badge tone="neutral">{item.status}</Badge>
                      <Button variant="ghost" onClick={() => selectItem(item.id)}>Open</Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Start from an opportunity</CardTitle>
            <CardDescription>Approved or saved opportunities not yet in production.</CardDescription>
          </CardHeader>
          <CardContent>
            {error && <p className="mb-2 text-xs text-bad">{error}</p>}
            {loadingList ? (
              <p className="text-sm text-subtle">Loading…</p>
            ) : opportunities.length === 0 ? (
              <EmptyState
                icon={Lightbulb}
                title="Pick an opportunity to start creating"
                description="Approve an opportunity in Opportunities and it will show up here."
              />
            ) : (
              <ul className="divide-y divide-border">
                {opportunities.map((o) => (
                  <li key={o.id} className="flex items-center justify-between py-2">
                    <span className="text-sm text-ink">{o.topic}</span>
                    <Button variant="secondary" onClick={() => handleStart(o.id)} disabled={starting !== null}>
                      {starting === o.id ? "Starting…" : "Start creating"}
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
