"use client";

import { useEffect, useRef, useState } from "react";
import { Check, Loader2, X, Minus } from "lucide-react";
import { getPipelineRun, ApiError } from "@/lib/api";
import type { PipelineRunRead, PipelineStageName } from "@/lib/types";

const STAGE_LABELS: Record<PipelineStageName, string> = {
  import: "Importing your content",
  creator_dna: "Building your Creator DNA",
  research: "Researching your niche",
  trends: "Analyzing trends",
  opportunities: "Scoring opportunities",
  strategy: "Building your strategy",
};

const POLL_INTERVAL_MS = 1500;

export function PipelineProgress({
  creatorId,
  runId,
  onComplete,
}: {
  creatorId: string;
  runId: string;
  onComplete: (run: PipelineRunRead) => void;
}) {
  const [run, setRun] = useState<PipelineRunRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    async function poll() {
      try {
        const result = await getPipelineRun(creatorId, runId);
        if (cancelled) return;
        setRun(result);
        if (result.status === "completed" || result.status === "failed") {
          onCompleteRef.current(result);
          return;
        }
        timer = setTimeout(poll, POLL_INTERVAL_MS);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Lost connection while checking progress.");
        timer = setTimeout(poll, POLL_INTERVAL_MS);
      }
    }

    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [creatorId, runId]);

  const stages = run?.stages ?? [];

  return (
    <div className="w-full max-w-sm">
      <div className="mb-8 text-center">
        <h1 className="text-lg font-semibold text-ink">Starting your engines</h1>
        <p className="mt-2 text-sm text-subtle">Real research, real analysis — this takes a minute or two.</p>
      </div>
      <div className="space-y-1 rounded-xl border border-border bg-white p-6 shadow-card">
        {stages.length === 0 ? (
          <div className="flex items-center gap-3 py-2 text-sm text-subtle">
            <Loader2 className="h-4 w-4 animate-spin text-accent" /> Connecting…
          </div>
        ) : (
          stages.map((stage) => (
            <div key={stage.name} className="flex items-start gap-3 py-2">
              <div className="mt-0.5 shrink-0">
                {stage.status === "success" && (
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-good/15">
                    <Check className="h-3.5 w-3.5 text-good" />
                  </span>
                )}
                {stage.status === "failed" && (
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-bad/15">
                    <X className="h-3.5 w-3.5 text-bad" />
                  </span>
                )}
                {stage.status === "skipped" && (
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-canvas">
                    <Minus className="h-3.5 w-3.5 text-subtle" />
                  </span>
                )}
                {stage.status === "running" && <Loader2 className="h-5 w-5 animate-spin text-accent" />}
                {stage.status === "pending" && (
                  <span className="flex h-5 w-5 items-center justify-center rounded-full border border-border" />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <p
                  className={
                    stage.status === "pending" ? "text-sm text-subtle" : "text-sm font-medium text-ink"
                  }
                >
                  {STAGE_LABELS[stage.name]}
                </p>
                {stage.summary && <p className="mt-0.5 text-xs text-subtle">{stage.summary}</p>}
              </div>
            </div>
          ))
        )}
      </div>
      {error && <p className="mt-3 text-center text-xs text-bad">{error}</p>}
    </div>
  );
}
