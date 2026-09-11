"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
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
  repurposeContent,
  listContentDerivatives,
  markContentRecorded,
  markContentEditing,
  scheduleContent,
  publishContent,
  ingestPerformance,
  listPerformance,
  diagnosePerformance,
  ApiError,
} from "@/lib/api";
import type {
  CalendarEventRead,
  ContentDetailRead,
  ContentItemRead,
  DiagnosisRead,
  OpportunityRead,
  PerformanceSnapshotCreate,
  PerformanceSnapshotRead,
  RepurposeContentResponse,
} from "@/lib/types";
import { SkeletonText, SkeletonCard } from "@/components/ui/skeleton";

const REPURPOSE_TARGETS: { platform: string; format: string; label: string }[] = [
  { platform: "instagram", format: "reel", label: "Instagram Reel" },
  { platform: "tiktok", format: "short", label: "TikTok short" },
  { platform: "x", format: "thread", label: "X thread" },
  { platform: "instagram", format: "carousel", label: "Instagram carousel" },
  { platform: "linkedin", format: "post", label: "LinkedIn post" },
  { platform: "newsletter", format: "email", label: "Newsletter" },
];

const METRIC_FIELDS: { key: keyof PerformanceSnapshotCreate; label: string }[] = [
  { key: "views", label: "Views" },
  { key: "likes", label: "Likes" },
  { key: "comments", label: "Comments" },
  { key: "shares", label: "Shares" },
  { key: "saves", label: "Saves" },
  { key: "retention", label: "Retention %" },
  { key: "watch_time", label: "Watch time (min)" },
  { key: "avg_view_duration", label: "Avg view dur. (sec)" },
  { key: "followers_gained", label: "Followers gained" },
  { key: "profile_visits", label: "Profile visits" },
];

const IN_PROGRESS_STATUSES = new Set([
  "APPROVED",
  "BRIEFED",
  "SCRIPTED",
  "REVIEW",
  "RECORDED",
  "EDITING",
  "SCHEDULED",
]);
const SCHEDULABLE_STATUSES = new Set(["REVIEW", "RECORDED", "EDITING"]);

// The model is asked for real newlines inside its JSON string fields, but
// sometimes double-escapes them (emitting the two literal characters `\`
// and `n` instead of an actual line break) — that survives JSON parsing as
// a literal backslash-n, which `whitespace-pre-wrap` can't turn into a line
// break since it isn't one. Normalizing defensively here is harmless either
// way: a body that already has real newlines is untouched.
function normalizeScriptBody(body: string): string {
  return body.replace(/\\n/g, "\n");
}

function severityTone(severity: string): "good" | "warn" | "bad" {
  if (severity === "high") return "bad";
  if (severity === "medium") return "warn";
  return "good";
}

export default function CreatePage() {
  return (
    <Suspense
      fallback={
        <div>
          <PageHeader title="Create" description="Angle → hook → brief → script → critique → improved script." />
          <div className="grid grid-cols-1 gap-4 p-8 lg:grid-cols-3">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
        </div>
      }
    >
      <CreatePageInner />
    </Suspense>
  );
}

function CreatePageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [opportunities, setOpportunities] = useState<OpportunityRead[]>([]);
  const [contentItems, setContentItems] = useState<ContentItemRead[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(searchParams.get("item"));
  const [detail, setDetail] = useState<ContentDetailRead | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [starting, setStarting] = useState<string | null>(null);
  const [busy, setBusy] = useState<
    | "brief"
    | "script"
    | "review"
    | "recorded"
    | "editing"
    | "schedule"
    | "publish"
    | "metrics"
    | "diagnose"
    | "repurpose"
    | null
  >(null);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [scheduledAt, setScheduledAt] = useState("");
  const [platform, setPlatform] = useState("");
  const [scheduleInfo, setScheduleInfo] = useState<CalendarEventRead | null>(null);
  const [publishUrl, setPublishUrl] = useState("");
  const [publishInfo, setPublishInfo] = useState<{ url: string | null; published_at: string } | null>(null);
  const [metricsForm, setMetricsForm] = useState<Record<string, string>>({});
  const [latestSnapshot, setLatestSnapshot] = useState<PerformanceSnapshotRead | null>(null);
  const [diagnosis, setDiagnosis] = useState<DiagnosisRead | null>(null);
  const [derivatives, setDerivatives] = useState<ContentItemRead[]>([]);
  const [repurposeTarget, setRepurposeTarget] = useState(0);
  const [repurposeResult, setRepurposeResult] = useState<RepurposeContentResponse | null>(null);

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
      const [detailResult, derivativesResult] = await Promise.all([
        getContentDetail(session.creatorId, id),
        listContentDerivatives(session.creatorId, id),
      ]);
      setDetail(detailResult);
      setDerivatives(derivativesResult);
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  useEffect(() => {
    if (selectedId) refetchDetail(selectedId);
  }, [selectedId, refetchDetail]);

  const publishedItemId = detail?.item?.status === "PUBLISHED" ? selectedId : null;
  useEffect(() => {
    // Guards against a slower response for a previously-selected item
    // resolving after a faster response for the newly-selected one and
    // overwriting it with the wrong item's data (mirrors selectItem's own
    // "stale state must never leak into an unrelated item" rule above).
    let cancelled = false;
    async function loadPerformance() {
      const session = getSession();
      if (!session || !publishedItemId) return;
      const snapshots = await listPerformance(session.creatorId, publishedItemId);
      if (cancelled) return;
      setLatestSnapshot(snapshots.length > 0 ? snapshots[snapshots.length - 1] : null);
    }
    loadPerformance();
    return () => {
      cancelled = true;
    };
  }, [publishedItemId]);

  // A stale error/warning from one item or view must never leak into an
  // unrelated one — navigating always clears them, and every action clears
  // them again before it starts.
  function selectItem(id: string | null) {
    setSelectedId(id);
    setDetail(null);
    setError(null);
    setWarnings([]);
    setScheduledAt("");
    setPlatform("");
    setScheduleInfo(null);
    setPublishUrl("");
    setPublishInfo(null);
    setMetricsForm({});
    setLatestSnapshot(null);
    setDiagnosis(null);
    setDerivatives([]);
    setRepurposeResult(null);
    setRepurposeTarget(0);
    router.replace(id ? `/create?item=${id}` : "/create");
  }

  // `selectedId` only reads the `item` query param once, at mount
  // (useState initializer) — Next.js App Router reuses this component
  // instance across query-string-only navigations on the same /create
  // route (e.g. clicking a different Analytics row), so without this the
  // page would keep showing whichever item was selected first. This stays
  // a no-op loop-free with selectItem's router.replace above: once synced,
  // paramItem === selectedId and the effect doesn't fire again.
  const paramItem = searchParams.get("item");
  useEffect(() => {
    if (paramItem !== selectedId) selectItem(paramItem);
  }, [paramItem]);

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

  async function handleRepurpose() {
    const session = getSession();
    if (!session || !selectedId) return;
    const target = REPURPOSE_TARGETS[repurposeTarget];
    setBusy("repurpose");
    setError(null);
    setWarnings([]);
    setRepurposeResult(null);
    try {
      const result = await repurposeContent(session.creatorId, selectedId, {
        target_platform: target.platform,
        target_format: target.format,
      });
      setRepurposeResult(result);
      setWarnings(result.warnings);
      if (result.derivative) {
        const session2 = getSession();
        if (session2) setDerivatives(await listContentDerivatives(session2.creatorId, selectedId));
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setBusy(null);
    }
  }

  async function handleMarkRecorded() {
    const session = getSession();
    if (!session || !selectedId) return;
    setBusy("recorded");
    setError(null);
    try {
      await markContentRecorded(session.creatorId, selectedId);
      await refetchDetail(selectedId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setBusy(null);
    }
  }

  async function handleMarkEditing() {
    const session = getSession();
    if (!session || !selectedId) return;
    setBusy("editing");
    setError(null);
    try {
      await markContentEditing(session.creatorId, selectedId);
      await refetchDetail(selectedId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setBusy(null);
    }
  }

  async function handleSchedule() {
    const session = getSession();
    if (!session || !selectedId || !scheduledAt) return;
    setBusy("schedule");
    setError(null);
    try {
      const result = await scheduleContent(session.creatorId, selectedId, {
        scheduled_at: new Date(scheduledAt).toISOString(),
        platform: platform || undefined,
      });
      setScheduleInfo(result.event);
      await refetchDetail(selectedId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setBusy(null);
    }
  }

  async function handlePublish() {
    const session = getSession();
    if (!session || !selectedId) return;
    setBusy("publish");
    setError(null);
    try {
      const result = await publishContent(session.creatorId, selectedId, { url: publishUrl || undefined });
      setPublishInfo({ url: result.url, published_at: result.published_at });
      await refetchDetail(selectedId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setBusy(null);
    }
  }

  async function handleSaveMetrics() {
    const session = getSession();
    if (!session || !selectedId) return;
    setBusy("metrics");
    setError(null);
    try {
      const payload: Record<string, number> = {};
      for (const { key } of METRIC_FIELDS) {
        const raw = metricsForm[key];
        if (raw !== undefined && raw !== "") payload[key] = Number(raw);
      }
      const snapshot = await ingestPerformance(session.creatorId, selectedId, payload as PerformanceSnapshotCreate);
      setLatestSnapshot(snapshot);
      setDiagnosis(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setBusy(null);
    }
  }

  async function handleDiagnose() {
    const session = getSession();
    if (!session || !selectedId) return;
    setBusy("diagnose");
    setError(null);
    setWarnings([]);
    try {
      const result = await diagnosePerformance(session.creatorId, selectedId);
      setLatestSnapshot(result.snapshot);
      setDiagnosis(result.diagnosis);
      setWarnings(result.warnings);
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
    const hasSourceText = !!latestScript || !!item?.transcript;

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
                <SkeletonText lines={2} />
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
                <SkeletonText lines={2} />
              ) : latestScript ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <Badge tone="neutral">v{latestScript.version_number}</Badge>
                    <Badge tone={latestScript.status === "final" ? "good" : latestScript.status === "critiqued" ? "warn" : "neutral"}>
                      {latestScript.status}
                    </Badge>
                  </div>
                  <p className="whitespace-pre-wrap text-sm text-ink">{normalizeScriptBody(latestScript.body)}</p>
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

          {item && hasSourceText && (
            <Card>
              <CardHeader>
                <CardTitle>Repurpose</CardTitle>
                <CardDescription>
                  Adapt this piece's script into a platform-native derivative (CLAUDE.md §25) — a new,
                  independent content item you can critique, schedule, and publish on its own.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap items-end gap-2">
                  <div>
                    <label className="block text-xs text-subtle" htmlFor="repurpose-target">Into</label>
                    <select
                      id="repurpose-target"
                      value={repurposeTarget}
                      onChange={(e) => setRepurposeTarget(Number(e.target.value))}
                      className="rounded-md border border-border bg-transparent px-2 py-1.5 text-sm text-ink"
                    >
                      {REPURPOSE_TARGETS.map((t, i) => (
                        <option key={t.label} value={i}>{t.label}</option>
                      ))}
                    </select>
                  </div>
                  <Button onClick={handleRepurpose} disabled={busy !== null}>
                    <Sparkles className="h-4 w-4" />
                    {busy === "repurpose" ? "Adapting…" : "Repurpose"}
                  </Button>
                </div>

                {repurposeResult?.derivative && repurposeResult.script && (
                  <div className="space-y-2 rounded-lg border border-border p-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-medium text-ink">{repurposeResult.derivative.title}</p>
                      <Button variant="ghost" onClick={() => selectItem(repurposeResult.derivative!.id)}>
                        Open this piece
                      </Button>
                    </div>
                    <p className="whitespace-pre-wrap text-sm text-ink">
                      {normalizeScriptBody(repurposeResult.script.body)}
                    </p>
                    {repurposeResult.transformations.length > 0 && (
                      <div>
                        <p className="text-xs font-medium text-subtle">What changed</p>
                        <ul className="ml-4 list-disc text-sm text-subtle">
                          {repurposeResult.transformations.map((t, i) => <li key={i}>{t}</li>)}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                {derivatives.length > 0 && (
                  <div>
                    <p className="mb-1 text-xs font-medium text-subtle">Derivatives of this piece</p>
                    <ul className="divide-y divide-border">
                      {derivatives.map((d) => (
                        <li key={d.id} className="flex items-center justify-between py-2">
                          <span className="text-sm text-ink">{d.title ?? d.topic}</span>
                          <div className="flex items-center gap-2">
                            <Badge tone="neutral">{d.platform ?? d.format}</Badge>
                            <Button variant="ghost" onClick={() => selectItem(d.id)}>Open</Button>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {item && ["REVIEW", "RECORDED", "EDITING", "SCHEDULED", "PUBLISHED"].includes(item.status) && (
            <Card>
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <CardTitle>Production & scheduling</CardTitle>
                    <CardDescription>Record, edit, schedule, and publish (CLAUDE.md §26).</CardDescription>
                  </div>
                  <Badge tone={item.status === "PUBLISHED" ? "good" : item.status === "SCHEDULED" ? "accent" : "neutral"}>
                    {item.status}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {(item.status === "REVIEW" || item.status === "RECORDED") && (
                  <div className="flex gap-2">
                    {item.status === "REVIEW" && (
                      <Button variant="secondary" onClick={handleMarkRecorded} disabled={busy !== null}>
                        {busy === "recorded" ? "Marking…" : "Mark recorded"}
                      </Button>
                    )}
                    {item.status === "RECORDED" && (
                      <Button variant="secondary" onClick={handleMarkEditing} disabled={busy !== null}>
                        {busy === "editing" ? "Marking…" : "Mark editing"}
                      </Button>
                    )}
                  </div>
                )}

                {SCHEDULABLE_STATUSES.has(item.status) && (
                  <div className="space-y-2 rounded-lg border border-border p-3">
                    <p className="text-xs font-medium text-subtle">
                      Schedule this piece{item.status !== "REVIEW" ? "" : " — or skip recording/editing for text-only formats"}
                    </p>
                    <div className="flex flex-wrap items-end gap-2">
                      <div>
                        <label className="block text-xs text-subtle" htmlFor="scheduled-at">When</label>
                        <input
                          id="scheduled-at"
                          type="datetime-local"
                          value={scheduledAt}
                          onChange={(e) => setScheduledAt(e.target.value)}
                          className="rounded-md border border-border bg-transparent px-2 py-1.5 text-sm text-ink"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-subtle" htmlFor="schedule-platform">Platform</label>
                        <input
                          id="schedule-platform"
                          type="text"
                          value={platform}
                          onChange={(e) => setPlatform(e.target.value)}
                          placeholder={item.platform ?? "e.g. instagram"}
                          className="rounded-md border border-border bg-transparent px-2 py-1.5 text-sm text-ink"
                        />
                      </div>
                      <Button onClick={handleSchedule} disabled={busy !== null || !scheduledAt}>
                        {busy === "schedule" ? "Scheduling…" : "Schedule"}
                      </Button>
                    </div>
                  </div>
                )}

                {item.status === "SCHEDULED" && (
                  <div className="space-y-2 rounded-lg border border-border p-3">
                    {scheduleInfo?.scheduled_at && (
                      <p className="text-sm text-ink">
                        Scheduled for {new Date(scheduleInfo.scheduled_at).toLocaleString()}
                        {scheduleInfo.platform ? ` on ${scheduleInfo.platform}` : ""}.
                      </p>
                    )}
                    <div className="flex flex-wrap items-end gap-2">
                      <div>
                        <label className="block text-xs text-subtle" htmlFor="publish-url">Published URL (optional)</label>
                        <input
                          id="publish-url"
                          type="text"
                          value={publishUrl}
                          onChange={(e) => setPublishUrl(e.target.value)}
                          placeholder="https://…"
                          className="rounded-md border border-border bg-transparent px-2 py-1.5 text-sm text-ink"
                        />
                      </div>
                      <Button onClick={handlePublish} disabled={busy !== null}>
                        {busy === "publish" ? "Publishing…" : "Mark published"}
                      </Button>
                    </div>
                  </div>
                )}

                {item.status === "PUBLISHED" && (
                  <p className="text-sm text-good">
                    Published{publishInfo?.published_at ? ` ${new Date(publishInfo.published_at).toLocaleString()}` : ""}.
                    {publishInfo?.url && (
                      <>
                        {" "}
                        <a href={publishInfo.url} target="_blank" rel="noreferrer" className="underline">
                          {publishInfo.url}
                        </a>
                      </>
                    )}
                  </p>
                )}
              </CardContent>
            </Card>
          )}

          {item && item.status === "PUBLISHED" && (
            <Card>
              <CardHeader>
                <CardTitle>Performance</CardTitle>
                <CardDescription>Log what happened, then see it against your own baseline (CLAUDE.md §27-29).</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
                  {METRIC_FIELDS.map(({ key, label }) => (
                    <div key={key}>
                      <label className="block text-xs text-subtle" htmlFor={`metric-${key}`}>
                        {label}
                      </label>
                      <input
                        id={`metric-${key}`}
                        type="number"
                        value={metricsForm[key] ?? ""}
                        onChange={(e) => setMetricsForm((prev) => ({ ...prev, [key]: e.target.value }))}
                        className="w-full rounded-md border border-border bg-transparent px-2 py-1.5 text-sm text-ink"
                      />
                    </div>
                  ))}
                </div>
                <Button variant="secondary" onClick={handleSaveMetrics} disabled={busy !== null}>
                  {busy === "metrics" ? "Saving…" : "Save metrics"}
                </Button>

                {latestSnapshot && (
                  <div className="rounded-lg border border-border p-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-xs font-medium text-subtle">
                        Latest: {new Date(latestSnapshot.captured_at).toLocaleString()}
                      </p>
                      <Button onClick={handleDiagnose} disabled={busy !== null}>
                        <Sparkles className="h-4 w-4" />
                        {busy === "diagnose" ? "Diagnosing…" : "Diagnose"}
                      </Button>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink">
                      {latestSnapshot.views !== null && <span>{latestSnapshot.views.toLocaleString()} views</span>}
                      {latestSnapshot.likes !== null && <span>{latestSnapshot.likes.toLocaleString()} likes</span>}
                      {latestSnapshot.comments !== null && (
                        <span>{latestSnapshot.comments.toLocaleString()} comments</span>
                      )}
                      {latestSnapshot.shares !== null && <span>{latestSnapshot.shares.toLocaleString()} shares</span>}
                      {latestSnapshot.saves !== null && <span>{latestSnapshot.saves.toLocaleString()} saves</span>}
                      {latestSnapshot.retention !== null && <span>{latestSnapshot.retention}% retention</span>}
                    </div>
                  </div>
                )}

                {diagnosis && (
                  <div className="space-y-2 rounded-lg border border-border p-3">
                    <p className="text-sm text-ink">{diagnosis.summary}</p>
                    {diagnosis.associated_factors.length > 0 && (
                      <ul className="space-y-1.5">
                        {diagnosis.associated_factors.map((f, i) => (
                          <li key={i} className="flex items-start gap-2 text-sm">
                            <Badge tone="neutral">{f.confidence}</Badge>
                            <span className="text-subtle">
                              <span className="text-ink">{f.factor}:</span> {f.note}
                            </span>
                          </li>
                        ))}
                      </ul>
                    )}
                    {diagnosis.next_test && (
                      <p className="text-xs text-subtle">
                        <span className="font-medium text-ink">Next test:</span> {diagnosis.next_test}
                      </p>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
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
              <SkeletonText lines={2} />
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
              <SkeletonText lines={2} />
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
