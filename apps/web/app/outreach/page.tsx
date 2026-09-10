"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Send, Building2 } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { getSession } from "@/lib/session";
import {
  approveOutreachMessage,
  draftOutreachFollowUp,
  getOutreachThread,
  listOutreachPipeline,
  markOutreachMessageSent,
  ApiError,
} from "@/lib/api";
import type { OutreachMessageRead, OutreachPipelineItem, OutreachThreadDetail } from "@/lib/types";

function statusTone(status: string): "good" | "warn" | "neutral" | "bad" {
  if (status === "sent" || status === "won") return "good";
  if (status === "lost" || status === "archived") return "bad";
  if (status === "drafting") return "neutral";
  return "warn";
}

export default function OutreachPage() {
  return (
    <Suspense
      fallback={
        <div>
          <PageHeader title="Outreach" description="Draft-only — you review, approve, and send every message yourself." />
          <div className="p-8 text-sm text-subtle">Loading…</div>
        </div>
      }
    >
      <OutreachPageInner />
    </Suspense>
  );
}

function MessageCard({
  message,
  onApprove,
  onMarkSent,
  busy,
}: {
  message: OutreachMessageRead;
  onApprove: (id: string) => void;
  onMarkSent: (id: string) => void;
  busy: boolean;
}) {
  const isInbound = message.direction === "inbound";
  return (
    <div className={`rounded-lg border border-border p-3 ${isInbound ? "bg-zinc-50" : "bg-white"}`}>
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-subtle">
          {isInbound ? "Brand reply" : message.kind.replace("_", " ")}
        </span>
        {message.status && <Badge tone={message.status === "sent" ? "good" : "neutral"}>{message.status}</Badge>}
      </div>
      {message.subject && <p className="text-sm font-medium text-ink">{message.subject}</p>}
      <p className="whitespace-pre-wrap text-sm text-ink">{message.body}</p>
      {!isInbound && (
        <div className="mt-2 flex items-center gap-2">
          {message.status === "draft" && (
            <Button variant="secondary" onClick={() => onApprove(message.id)} disabled={busy}>
              Approve
            </Button>
          )}
          {message.status === "approved" && (
            <Button onClick={() => onMarkSent(message.id)} disabled={busy}>
              I sent this
            </Button>
          )}
          {message.status === "sent" && message.sent_at && (
            <p className="text-xs text-subtle">Marked sent {new Date(message.sent_at).toLocaleString()}</p>
          )}
        </div>
      )}
    </div>
  );
}

function OutreachPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [threads, setThreads] = useState<OutreachPipelineItem[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(searchParams.get("thread"));
  const [detail, setDetail] = useState<OutreachThreadDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [busyMessageId, setBusyMessageId] = useState<string | null>(null);
  const [draftingFollowUp, setDraftingFollowUp] = useState(false);
  const [followUpWarnings, setFollowUpWarnings] = useState<string[]>([]);

  const refetchThreads = useCallback(async () => {
    const session = getSession();
    if (!session) {
      setLoadingList(false);
      return;
    }
    setLoadingList(true);
    try {
      setThreads(await listOutreachPipeline(session.creatorId));
    } finally {
      setLoadingList(false);
    }
  }, []);

  useEffect(() => {
    refetchThreads();
  }, [refetchThreads]);

  const selectThread = useCallback(
    (id: string | null) => {
      setSelectedId(id);
      setDetail(null);
      setDetailError(null);
      setFollowUpWarnings([]);
      router.replace(id ? `/outreach?thread=${id}` : "/outreach");
    },
    [router]
  );

  // Split select-vs-fetch, same reasoning as app/brands/page.tsx: selectedId's
  // useState initializer already reads the query param at mount, so a direct
  // load of /outreach?thread=X needs this separate effect to actually fetch.
  useEffect(() => {
    if (!selectedId) return;
    const session = getSession();
    if (!session) return;
    let cancelled = false;
    setLoadingDetail(true);
    setDetailError(null);
    getOutreachThread(session.creatorId, selectedId)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch((err) => {
        if (!cancelled) setDetailError(err instanceof ApiError ? err.message : "Couldn't load this thread.");
      })
      .finally(() => {
        if (!cancelled) setLoadingDetail(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  const paramThread = searchParams.get("thread");
  useEffect(() => {
    if (paramThread !== selectedId) selectThread(paramThread);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramThread]);

  const selectedIdRef = useRef(selectedId);
  useEffect(() => {
    selectedIdRef.current = selectedId;
  }, [selectedId]);

  async function refreshDetail() {
    const session = getSession();
    if (!session || !selectedId) return;
    const d = await getOutreachThread(session.creatorId, selectedId);
    if (selectedIdRef.current === selectedId) setDetail(d);
  }

  async function handleApprove(messageId: string) {
    const session = getSession();
    if (!session || !selectedId) return;
    setBusyMessageId(messageId);
    try {
      await approveOutreachMessage(session.creatorId, selectedId, messageId);
      await Promise.all([refreshDetail(), refetchThreads()]);
    } catch (err) {
      setDetailError(err instanceof ApiError ? err.message : "Couldn't approve this message.");
    } finally {
      setBusyMessageId(null);
    }
  }

  async function handleMarkSent(messageId: string) {
    const session = getSession();
    if (!session || !selectedId) return;
    setBusyMessageId(messageId);
    try {
      await markOutreachMessageSent(session.creatorId, selectedId, messageId);
      await Promise.all([refreshDetail(), refetchThreads()]);
    } catch (err) {
      setDetailError(err instanceof ApiError ? err.message : "Couldn't mark this message sent.");
    } finally {
      setBusyMessageId(null);
    }
  }

  async function handleDraftFollowUp() {
    const session = getSession();
    if (!session || !selectedId) return;
    setDraftingFollowUp(true);
    setFollowUpWarnings([]);
    try {
      const result = await draftOutreachFollowUp(session.creatorId, selectedId);
      setFollowUpWarnings(result.warnings);
      if (result.message) await refreshDetail();
    } catch (err) {
      setDetailError(err instanceof ApiError ? err.message : "Couldn't draft a follow-up.");
    } finally {
      setDraftingFollowUp(false);
    }
  }

  // Mirrors the backend precondition in draft_follow_up_route (the pitch
  // must have actually gone out — thread.status === "sent"; this also
  // correctly hides the button once Phase 7 adds terminal states like
  // won/lost/archived), plus a client-side check that there isn't already
  // an undealt-with draft sitting in the thread — no stacking a second
  // follow-up on top of one the creator hasn't approved or sent yet.
  const latestOutbound = detail?.messages.filter((m) => m.direction === "outbound").slice(-1)[0];
  const canDraftFollowUp = detail?.thread.status === "sent" && latestOutbound?.status === "sent";

  return (
    <div>
      <PageHeader title="Outreach" description="Draft-only — you review, approve, and send every message yourself." />
      <div className="grid grid-cols-1 gap-4 p-8 lg:grid-cols-[1fr_1.6fr]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Send className="h-4 w-4 text-accent" /> Pipeline
            </CardTitle>
            <CardDescription>{threads.length} outreach thread{threads.length === 1 ? "" : "s"}</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            {loadingList ? (
              <p className="p-4 text-sm text-subtle">Loading…</p>
            ) : threads.length === 0 ? (
              <div className="p-4">
                <EmptyState
                  icon={Send}
                  title="No outreach yet"
                  description="Score a brand and draft a campaign pitch on the Brands page, then start outreach from there."
                />
              </div>
            ) : (
              <ul className="divide-y divide-border">
                {threads.map(({ thread, brand }) => (
                  <li key={thread.id}>
                    <button
                      onClick={() => selectThread(thread.id)}
                      className={`flex w-full items-center justify-between px-4 py-3 text-left hover:bg-zinc-50 ${
                        selectedId === thread.id ? "bg-accent-soft" : ""
                      }`}
                    >
                      <div>
                        <p className="text-sm font-medium text-ink">{brand.name}</p>
                        <p className="text-xs text-subtle">{new Date(thread.created_at).toLocaleDateString()}</p>
                      </div>
                      <Badge tone={statusTone(thread.status)}>{thread.status}</Badge>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <div>
          {!selectedId ? (
            <Card>
              <CardContent className="p-8">
                <EmptyState
                  icon={Send}
                  title="Select a thread"
                  description="Pick an outreach thread from the pipeline to review its draft and messages."
                />
              </CardContent>
            </Card>
          ) : loadingDetail || !detail ? (
            <Card>
              <CardContent className="p-8 text-sm text-subtle">{detailError ?? "Loading…"}</CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        <Building2 className="h-4 w-4 text-accent" /> {detail.brand.name}
                      </CardTitle>
                      <CardDescription>{detail.brand.category ?? "No category set"}</CardDescription>
                    </div>
                    <Badge tone={statusTone(detail.thread.status)}>{detail.thread.status}</Badge>
                  </div>
                </CardHeader>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Messages</CardTitle>
                  <CardDescription>Every message here is a draft until you approve and send it yourself.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {detailError && <p className="text-sm text-bad">{detailError}</p>}
                  {detail.messages.map((message) => (
                    <MessageCard
                      key={message.id}
                      message={message}
                      onApprove={handleApprove}
                      onMarkSent={handleMarkSent}
                      busy={busyMessageId === message.id}
                    />
                  ))}
                  {canDraftFollowUp && (
                    <div className="pt-1">
                      <Button variant="secondary" onClick={handleDraftFollowUp} disabled={draftingFollowUp}>
                        {draftingFollowUp ? "Drafting…" : "Draft a follow-up"}
                      </Button>
                      {followUpWarnings.length > 0 && (
                        <p className="mt-2 text-sm text-warn">{followUpWarnings.join(" ")}</p>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
