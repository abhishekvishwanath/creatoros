"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { FlaskConical, ArrowLeft, Plus } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { getSession } from "@/lib/session";
import {
  createExperiment,
  listExperiments,
  getExperimentDetail,
  updateExperimentStatus,
  addExperimentResult,
  evaluateExperiment,
  ApiError,
} from "@/lib/api";
import type { ExperimentDetailRead, ExperimentRead, ExperimentStatus } from "@/lib/types";

function statusTone(status: string): "good" | "warn" | "bad" | "neutral" | "accent" {
  if (status === "completed") return "good";
  if (status === "running") return "accent";
  if (status === "abandoned") return "bad";
  return "neutral";
}

export default function ExperimentsPage() {
  return (
    <Suspense
      fallback={
        <div>
          <PageHeader title="Experiments" description="Formulate a hypothesis, test it, and see if it holds up." />
          <div className="p-8 text-sm text-subtle">Loading…</div>
        </div>
      }
    >
      <ExperimentsPageInner />
    </Suspense>
  );
}

function ExperimentsPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [experiments, setExperiments] = useState<ExperimentRead[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(searchParams.get("id"));
  const [detail, setDetail] = useState<ExperimentDetailRead | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [busy, setBusy] = useState<"create" | "status" | "result" | "evaluate" | null>(null);

  const [hypothesis, setHypothesis] = useState("");
  const [variable, setVariable] = useState("");
  const [controlReference, setControlReference] = useState("");

  const [resultContentItemId, setResultContentItemId] = useState("");
  const [resultMetricName, setResultMetricName] = useState("");
  const [resultMetricValue, setResultMetricValue] = useState("");
  const [resultGroup, setResultGroup] = useState<"test" | "control">("test");

  const refetchList = useCallback(async () => {
    const session = getSession();
    if (!session) {
      setLoadingList(false);
      return;
    }
    setLoadingList(true);
    try {
      setExperiments(await listExperiments(session.creatorId));
    } finally {
      setLoadingList(false);
    }
  }, []);

  useEffect(() => {
    refetchList();
  }, [refetchList]);

  const refetchDetail = useCallback(async (id: string) => {
    const session = getSession();
    if (!session) return;
    setLoadingDetail(true);
    try {
      setDetail(await getExperimentDetail(session.creatorId, id));
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  useEffect(() => {
    if (selectedId) refetchDetail(selectedId);
  }, [selectedId, refetchDetail]);

  function selectExperiment(id: string | null) {
    setSelectedId(id);
    setDetail(null);
    setError(null);
    setWarnings([]);
    setResultContentItemId("");
    setResultMetricName("");
    setResultMetricValue("");
    setResultGroup("test");
    router.replace(id ? `/experiments?id=${id}` : "/experiments");
  }

  const paramId = searchParams.get("id");
  useEffect(() => {
    if (paramId !== selectedId) selectExperiment(paramId);
  }, [paramId]);

  async function handleCreate() {
    const session = getSession();
    if (!session || !hypothesis.trim()) return;
    setBusy("create");
    setError(null);
    try {
      const experiment = await createExperiment(session.creatorId, {
        hypothesis: hypothesis.trim(),
        variable: variable.trim() || undefined,
        control_reference: controlReference.trim() || undefined,
      });
      setHypothesis("");
      setVariable("");
      setControlReference("");
      await refetchList();
      selectExperiment(experiment.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setBusy(null);
    }
  }

  async function handleStatusChange(status: ExperimentStatus) {
    const session = getSession();
    if (!session || !selectedId) return;
    setBusy("status");
    setError(null);
    try {
      await updateExperimentStatus(session.creatorId, selectedId, status);
      await refetchDetail(selectedId);
      await refetchList();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setBusy(null);
    }
  }

  async function handleAddResult() {
    const session = getSession();
    if (!session || !selectedId || !resultMetricName.trim() || resultMetricValue === "") return;
    setBusy("result");
    setError(null);
    try {
      await addExperimentResult(session.creatorId, selectedId, {
        content_item_id: resultContentItemId.trim() || undefined,
        metric_name: resultMetricName.trim(),
        metric_value: Number(resultMetricValue),
        group: resultGroup,
      });
      setResultContentItemId("");
      setResultMetricValue("");
      await refetchDetail(selectedId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setBusy(null);
    }
  }

  async function handleEvaluate() {
    const session = getSession();
    if (!session || !selectedId) return;
    setBusy("evaluate");
    setError(null);
    setWarnings([]);
    try {
      const result = await evaluateExperiment(session.creatorId, selectedId);
      setWarnings(result.warnings);
      await refetchDetail(selectedId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setBusy(null);
    }
  }

  if (selectedId) {
    const experiment = detail?.experiment;
    const results = detail?.results ?? [];

    return (
      <div>
        <PageHeader
          title={experiment?.hypothesis ?? "Experiment"}
          description="Test/control results, evaluated against your own data — never a guessed number."
          action={
            <Button variant="ghost" onClick={() => selectExperiment(null)}>
              <ArrowLeft className="h-4 w-4" /> Back
            </Button>
          }
        />
        <div className="grid grid-cols-1 gap-4 p-8">
          {error && <p className="text-sm text-bad">{error}</p>}
          {!error && warnings.length > 0 && <p className="text-sm text-warn">{warnings.join(" ")}</p>}

          {loadingDetail || !experiment ? (
            <p className="text-sm text-subtle">Loading…</p>
          ) : (
            <>
              <Card>
                <CardHeader>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <CardTitle>Setup</CardTitle>
                      {experiment.variable && <CardDescription>Variable: {experiment.variable}</CardDescription>}
                    </div>
                    <Badge tone={statusTone(experiment.status)}>{experiment.status}</Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  {experiment.control_reference && (
                    <p className="text-sm text-subtle">
                      <span className="font-medium text-ink">Control:</span> {experiment.control_reference}
                    </p>
                  )}
                  <div className="flex gap-2">
                    {experiment.status === "planned" && (
                      <Button variant="secondary" disabled={busy !== null} onClick={() => handleStatusChange("running")}>
                        Start running
                      </Button>
                    )}
                    {(experiment.status === "planned" || experiment.status === "running") && (
                      <Button variant="ghost" disabled={busy !== null} onClick={() => handleStatusChange("abandoned")}>
                        Abandon
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Results</CardTitle>
                  <CardDescription>Log a metric value for one piece, tagged test or control.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex flex-wrap items-end gap-2">
                    <div>
                      <label className="block text-xs text-subtle" htmlFor="result-content-item">Content item id (optional)</label>
                      <input
                        id="result-content-item"
                        type="text"
                        value={resultContentItemId}
                        onChange={(e) => setResultContentItemId(e.target.value)}
                        placeholder="cnt_…"
                        className="rounded-md border border-border bg-transparent px-2 py-1.5 text-sm text-ink"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-subtle" htmlFor="result-metric-name">Metric</label>
                      <input
                        id="result-metric-name"
                        type="text"
                        value={resultMetricName}
                        onChange={(e) => setResultMetricName(e.target.value)}
                        placeholder="retention"
                        className="rounded-md border border-border bg-transparent px-2 py-1.5 text-sm text-ink"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-subtle" htmlFor="result-metric-value">Value</label>
                      <input
                        id="result-metric-value"
                        type="number"
                        value={resultMetricValue}
                        onChange={(e) => setResultMetricValue(e.target.value)}
                        className="w-24 rounded-md border border-border bg-transparent px-2 py-1.5 text-sm text-ink"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-subtle" htmlFor="result-group">Group</label>
                      <select
                        id="result-group"
                        value={resultGroup}
                        onChange={(e) => setResultGroup(e.target.value as "test" | "control")}
                        className="rounded-md border border-border bg-transparent px-2 py-1.5 text-sm text-ink"
                      >
                        <option value="test">Test</option>
                        <option value="control">Control</option>
                      </select>
                    </div>
                    <Button onClick={handleAddResult} disabled={busy !== null || !resultMetricName.trim() || resultMetricValue === ""}>
                      <Plus className="h-4 w-4" />
                      {busy === "result" ? "Adding…" : "Add result"}
                    </Button>
                  </div>

                  {results.length === 0 ? (
                    <p className="text-sm text-subtle">No results logged yet.</p>
                  ) : (
                    <ul className="divide-y divide-border">
                      {results.map((r) => (
                        <li key={r.id} className="flex items-center justify-between py-1.5 text-sm">
                          <span className="text-ink">
                            {r.metric_name}: {r.metric_value}
                            {r.content_item_id && <span className="text-subtle"> · {r.content_item_id}</span>}
                          </span>
                          <Badge tone={r.group === "test" ? "accent" : "neutral"}>{r.group}</Badge>
                        </li>
                      ))}
                    </ul>
                  )}

                  <Button onClick={handleEvaluate} disabled={busy !== null || results.length === 0}>
                    <FlaskConical className="h-4 w-4" />
                    {busy === "evaluate" ? "Evaluating…" : "Evaluate"}
                  </Button>

                  {experiment.results && Object.keys(experiment.results).length > 0 && (
                    <div className="space-y-2">
                      {Object.entries(experiment.results).map(([metric, s]) => (
                        <div key={metric} className="rounded-lg border border-border p-3 text-sm">
                          <p className="font-medium text-ink">{metric}</p>
                          <p className="text-subtle">
                            test median {s.test_median ?? "—"} (n={s.test_n}) vs control median {s.control_median ?? "—"} (n={s.control_n})
                            {typeof s.delta === "number" && ` · delta ${s.delta.toFixed(2)}`}
                            {!s.adequate_evidence && " · not enough evidence yet"}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}

                  {experiment.conclusion && (
                    <div className="space-y-1 rounded-lg border border-border p-3">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-ink">Conclusion</p>
                        {experiment.confidence && <Badge tone="neutral">{experiment.confidence} confidence</Badge>}
                      </div>
                      <p className="text-sm text-ink">{experiment.conclusion}</p>
                      {experiment.next_action && (
                        <p className="text-xs text-subtle">
                          <span className="font-medium text-ink">Next:</span> {experiment.next_action}
                        </p>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="Experiments" description="Formulate a hypothesis, test it, and see if it holds up (CLAUDE.md §30)." />
      <div className="grid grid-cols-1 gap-4 p-8 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Active and past experiments</CardTitle>
            <CardDescription>Every strategic hypothesis worth testing.</CardDescription>
          </CardHeader>
          <CardContent>
            {loadingList ? (
              <p className="text-sm text-subtle">Loading…</p>
            ) : experiments.length === 0 ? (
              <EmptyState icon={FlaskConical} title="No experiments yet" description="Start one from a hypothesis on the right." />
            ) : (
              <ul className="divide-y divide-border">
                {experiments.map((e) => (
                  <li key={e.id} className="flex items-center justify-between gap-3 py-2">
                    <span className="truncate text-sm text-ink">{e.hypothesis}</span>
                    <div className="flex items-center gap-2">
                      <Badge tone={statusTone(e.status)}>{e.status}</Badge>
                      <Button variant="ghost" onClick={() => selectExperiment(e.id)}>Open</Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>New experiment</CardTitle>
            <CardDescription>A hypothesis worth testing against real results.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {error && <p className="text-xs text-bad">{error}</p>}
            <div>
              <label className="block text-xs text-subtle" htmlFor="new-hypothesis">Hypothesis</label>
              <textarea
                id="new-hypothesis"
                value={hypothesis}
                onChange={(e) => setHypothesis(e.target.value)}
                placeholder="Contrarian hooks improve early retention."
                rows={2}
                className="w-full rounded-md border border-border bg-transparent px-2 py-1.5 text-sm text-ink"
              />
            </div>
            <div>
              <label className="block text-xs text-subtle" htmlFor="new-variable">Variable (optional)</label>
              <input
                id="new-variable"
                type="text"
                value={variable}
                onChange={(e) => setVariable(e.target.value)}
                placeholder="hook_type"
                className="w-full rounded-md border border-border bg-transparent px-2 py-1.5 text-sm text-ink"
              />
            </div>
            <div>
              <label className="block text-xs text-subtle" htmlFor="new-control">Control represents (optional)</label>
              <input
                id="new-control"
                type="text"
                value={controlReference}
                onChange={(e) => setControlReference(e.target.value)}
                placeholder="Posts with a standard, non-contrarian hook"
                className="w-full rounded-md border border-border bg-transparent px-2 py-1.5 text-sm text-ink"
              />
            </div>
            <Button onClick={handleCreate} disabled={busy !== null || !hypothesis.trim()}>
              <Plus className="h-4 w-4" />
              {busy === "create" ? "Creating…" : "Create experiment"}
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
