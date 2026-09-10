"use client";

import { FormEvent, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Send, Building2, MessageSquareText } from "lucide-react";
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
  recordBrandReply,
  recordOutreachDecision,
  ApiError,
} from "@/lib/api";
import type { CreatorDecision, OutreachMessageRead, OutreachPipelineItem, OutreachThreadDetail } from "@/lib/types";

const inputClass = "w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-accent";

const DECISION_OPTIONS: { value: CreatorDecision; label: string; variant: "primary" | "secondary" }[] = [
  { value: "accept", label: "Accept", variant: "primary" },
  { value: "negotiate", label: "Negotiate", variant: "secondary" },
  { value: "need_more_info", label: "Need more info", variant: "secondary" },
  { value: "decline", label: "Decline", variant: "secondary" },
  { value: "archive", label: "Archive", variant: "secondary" },
];

function sentimentTone(sentiment: string): "good" | "warn" | "bad" {
  if (sentiment === "interested") return "good";
  if (sentiment === "declining") return "bad";
  return "warn";
}

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
      {isInbound && message.extracted_data && (
        <div className="mt-2 space-y-1.5 rounded-lg border border-border bg-white p-2.5">
          <div className="flex items-center gap-2">
            <Badge tone={sentimentTone(message.extracted_data.sentiment)}>{message.extracted_data.sentiment}</Badge>
          </div>
          {message.extracted_data.summary && <p className="text-xs text-subtle">{message.extracted_data.summary}</p>}
          {(message.extracted_data.budget_mentioned || message.extracted_data.timeline_mentioned) && (
            <p className="text-xs text-ink">
              {message.extracted_data.budget_mentioned && <>Budget: {message.extracted_data.budget_mentioned} </>}
              {message.extracted_data.timeline_mentioned && <>· Timeline: {message.extracted_data.timeline_mentioned}</>}
            </p>
          )}
          {message.extracted_data.next_steps_from_brand && (
            <p className="text-xs text-ink">
              <span className="text-subtle">Next step: </span>
              {message.extracted_data.next_steps_from_brand}
            </p>
          )}
          {message.extracted_data.open_questions.length > 0 && (
            <p className="text-xs text-ink">
              <span className="text-subtle">Asked: </span>
              {message.extracted_data.open_questions.join(" · ")}
            </p>
          )}
          {message.extracted_data.flags.length > 0 && (
            <p className="text-xs text-bad">{message.extracted_data.flags.join(" · ")}</p>
          )}
        </div>
      )}
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

function PasteReplyForm({ onSubmit }: { onSubmit: (body: string, subject?: string) => Promise<boolean> }) {
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!body.trim()) return;
    setSubmitting(true);
    try {
      // Only clear on success — a failed save (network error, 400, 404)
      // must leave the creator's pasted text in place, not silently lose
      // work they'd have to go find and re-paste.
      const saved = await onSubmit(body, subject || undefined);
      if (saved) {
        setSubject("");
        setBody("");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-2">
      <input
        value={subject}
        onChange={(e) => setSubject(e.target.value)}
        placeholder="Subject (optional)"
        className={inputClass}
      />
      <textarea
        required
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder="Paste the brand's reply here, verbatim…"
        rows={4}
        className={inputClass}
      />
      <Button type="submit" variant="secondary" disabled={submitting}>
        {submitting ? "Saving…" : "Save reply"}
      </Button>
    </form>
  );
}

function DecisionCard({
  thread,
  onDecide,
  deciding,
}: {
  thread: OutreachThreadDetail["thread"];
  onDecide: (decision: CreatorDecision, note?: string) => Promise<void>;
  deciding: boolean;
}) {
  const [note, setNote] = useState("");

  if (thread.creator_decision) {
    return (
      <div className="rounded-lg border border-border bg-zinc-50 p-3 text-sm">
        <p className="text-ink">
          Decision recorded: <span className="font-medium">{thread.creator_decision.replace(/_/g, " ")}</span>
        </p>
        {thread.creator_decision_note && <p className="mt-1 text-subtle">{thread.creator_decision_note}</p>}
        {thread.decided_at && (
          <p className="mt-1 text-xs text-subtle">{new Date(thread.decided_at).toLocaleString()}</p>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Optional note to yourself about this decision…"
        rows={2}
        className={inputClass}
      />
      <div className="flex flex-wrap gap-2">
        {DECISION_OPTIONS.map((opt) => (
          <Button
            key={opt.value}
            variant={opt.variant}
            disabled={deciding}
            onClick={() => onDecide(opt.value, note || undefined)}
          >
            {opt.label}
          </Button>
        ))}
      </div>
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
  const [replyWarnings, setReplyWarnings] = useState<string[]>([]);
  const [deciding, setDeciding] = useState(false);

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

  // Returns whether the save actually succeeded so PasteReplyForm knows
  // whether it's safe to clear the creator's pasted text — this function
  // handles its own errors (shown via detailError) rather than throwing,
  // so a plain try/catch in the caller wouldn't see a failure at all.
  async function handleRecordReply(body: string, subject?: string): Promise<boolean> {
    const session = getSession();
    if (!session || !selectedId) return false;
    setReplyWarnings([]);
    try {
      const result = await recordBrandReply(session.creatorId, selectedId, body, subject);
      setReplyWarnings(result.warnings);
      await Promise.all([refreshDetail(), refetchThreads()]);
      return true;
    } catch (err) {
      setDetailError(err instanceof ApiError ? err.message : "Couldn't save this reply.");
      return false;
    }
  }

  async function handleDecide(decision: CreatorDecision, note?: string) {
    const session = getSession();
    if (!session || !selectedId) return;
    setDeciding(true);
    try {
      await recordOutreachDecision(session.creatorId, selectedId, decision, note);
      await Promise.all([refreshDetail(), refetchThreads()]);
    } catch (err) {
      setDetailError(err instanceof ApiError ? err.message : "Couldn't record this decision.");
    } finally {
      setDeciding(false);
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
  // A reply can be pasted in any time the pitch is out and the thread
  // hasn't been closed out by a creator decision — including a second or
  // third reply as correspondence continues.
  const canRecordReply =
    detail && (detail.thread.status === "sent" || detail.thread.status === "replied") && !detail.thread.creator_decision;
  // The creator can decide at any point once the pitch is out, whether or
  // not a reply has come in yet (e.g. deciding to archive a thread that
  // went quiet) — and the card stays visible after a decision is recorded
  // (status then moves to a terminal stage like "won") so the recorded
  // decision itself remains visible, not just while the buttons are live.
  const canDecide =
    detail &&
    (detail.thread.status === "sent" || detail.thread.status === "replied" || detail.thread.creator_decision);

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

              {canRecordReply && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <MessageSquareText className="h-4 w-4 text-accent" /> Paste the brand&apos;s reply
                    </CardTitle>
                    <CardDescription>
                      No inbound email is connected — paste what they sent you and we&apos;ll pull out the key points.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <PasteReplyForm onSubmit={handleRecordReply} />
                    {replyWarnings.length > 0 && <p className="mt-2 text-sm text-warn">{replyWarnings.join(" ")}</p>}
                  </CardContent>
                </Card>
              )}

              {canDecide && (
                <Card>
                  <CardHeader>
                    <CardTitle>Your decision</CardTitle>
                    <CardDescription>
                      This is always your call — nothing here is decided automatically.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <DecisionCard thread={detail.thread} onDecide={handleDecide} deciding={deciding} />
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
