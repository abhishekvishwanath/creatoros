"use client";

import { useState } from "react";
import { Dna, Mic, Users, Target, Shield, Sparkles, HeartHandshake } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ConfidenceBadge } from "@/components/ui/confidence-badge";
import { ContentLibraryCard } from "@/components/content-library-card";
import { MemorySearchCard } from "@/components/memory-search-card";
import { CommercialProfileCard } from "@/components/commercial-profile-card";
import { useCreatorState } from "@/lib/use-creator-state";
import { getSession } from "@/lib/session";
import { analyzeCreator, analyzeAudience, ApiError } from "@/lib/api";
import { SkeletonText } from "@/components/ui/skeleton";

export default function CreatorDnaPage() {
  const { state, loading, refetch } = useCreatorState();
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [analyzeWarnings, setAnalyzeWarnings] = useState<string[]>([]);
  const [analyzingAudience, setAnalyzingAudience] = useState(false);
  const [audienceError, setAudienceError] = useState<string | null>(null);
  const [audienceWarnings, setAudienceWarnings] = useState<string[]>([]);

  async function handleAnalyze() {
    const session = getSession();
    if (!session) return;
    setAnalyzing(true);
    setAnalyzeError(null);
    setAnalyzeWarnings([]);
    try {
      const result = await analyzeCreator(session.creatorId);
      setAnalyzeWarnings(result.warnings);
      await refetch();
    } catch (err) {
      setAnalyzeError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setAnalyzing(false);
    }
  }

  async function handleAnalyzeAudience() {
    const session = getSession();
    if (!session) return;
    setAnalyzingAudience(true);
    setAudienceError(null);
    setAudienceWarnings([]);
    try {
      const result = await analyzeAudience(session.creatorId);
      setAudienceWarnings(result.warnings);
      await refetch();
    } catch (err) {
      setAudienceError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setAnalyzingAudience(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Creator DNA"
        description="What the system has learned about you — inspect and correct it any time."
        action={
          <div className="flex flex-col items-end gap-1.5">
            <Button onClick={handleAnalyze} disabled={analyzing}>
              <Sparkles className="h-4 w-4" />
              {analyzing ? "Analyzing…" : state?.positioning ? "Re-analyze" : "Build my Creator DNA"}
            </Button>
            {analyzeError && <p className="max-w-xs text-right text-xs text-bad">{analyzeError}</p>}
            {!analyzeError && analyzeWarnings.length > 0 && (
              <p className="max-w-xs text-right text-xs text-warn">{analyzeWarnings.join(" ")}</p>
            )}
          </div>
        }
      />
      <div className="grid grid-cols-1 gap-4 p-8 lg:grid-cols-2">
        <ContentLibraryCard recentContent={state?.recent_content ?? []} onIngested={refetch} />
        <MemorySearchCard />

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Target className="h-4 w-4 text-accent" /> Positioning
            </CardTitle>
            <CardDescription>Identity, expertise, and how you're positioned.</CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <SkeletonText lines={2} />
            ) : state?.positioning ? (
              <div className="space-y-2">
                <ConfidenceBadge confidence={state.positioning.confidence} />
                <p className="text-sm text-ink">{state.positioning.positioning_statement}</p>
              </div>
            ) : (
              <EmptyState
                icon={Target}
                title="Not analyzed yet"
                description="The Creator Intelligence Agent builds this from your historical content and onboarding answers."
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Mic className="h-4 w-4 text-accent" /> Voice
            </CardTitle>
            <CardDescription>Tone, pacing, personality, signature phrases.</CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <SkeletonText lines={2} />
            ) : state?.voice ? (
              <div className="space-y-2">
                <ConfidenceBadge confidence={state.voice.confidence} />
                <p className="text-sm text-ink">{state.voice.tone}</p>
              </div>
            ) : (
              <EmptyState
                icon={Mic}
                title="Not analyzed yet"
                description="Voice is inferred from your past scripts and captions — connect or upload content to build this."
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-start justify-between gap-3">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Users className="h-4 w-4 text-accent" /> Audience
                </CardTitle>
                <CardDescription>Who you're speaking to.</CardDescription>
              </div>
              <div className="flex flex-col items-end gap-1">
                <Button variant="secondary" onClick={handleAnalyzeAudience} disabled={analyzingAudience}>
                  {analyzingAudience ? "Analyzing…" : state?.audience ? "Re-analyze" : "Analyze audience"}
                </Button>
                {audienceError && <p className="max-w-[14rem] text-right text-xs text-bad">{audienceError}</p>}
                {!audienceError && audienceWarnings.length > 0 && (
                  <p className="max-w-[14rem] text-right text-xs text-warn">{audienceWarnings.join(" ")}</p>
                )}
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <SkeletonText lines={2} />
            ) : state?.audience ? (
              <div className="space-y-2">
                <ConfidenceBadge confidence={state.audience.confidence} />
                <p className="text-sm text-ink">{state.audience.knowledge_level}</p>
              </div>
            ) : (
              <EmptyState
                icon={Users}
                title="Not analyzed yet"
                description="Add audience signals in Research (comments, questions, feedback), then analyze here."
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <HeartHandshake className="h-4 w-4 text-accent" /> Audience segments
            </CardTitle>
            <CardDescription>The Audience Problem Graph — recurring problems, desires, and objections.</CardDescription>
          </CardHeader>
          <CardContent>
            {state?.audience_segments && state.audience_segments.length > 0 ? (
              <ul className="space-y-4">
                {state.audience_segments.map((s) => (
                  <li key={s.id}>
                    <div className="mb-1.5 flex items-center gap-2">
                      <p className="text-sm font-medium text-ink">{s.name}</p>
                      <ConfidenceBadge confidence={s.confidence} />
                    </div>
                    <div className="space-y-1.5">
                      {s.problems && s.problems.length > 0 && (
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="text-xs text-subtle">Problems:</span>
                          {s.problems.map((p, i) => (
                            <Badge key={`${s.id}-problem-${i}`} tone="neutral">{p}</Badge>
                          ))}
                        </div>
                      )}
                      {s.desires && s.desires.length > 0 && (
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="text-xs text-subtle">Desires:</span>
                          {s.desires.map((d, i) => (
                            <Badge key={`${s.id}-desire-${i}`} tone="accent">{d}</Badge>
                          ))}
                        </div>
                      )}
                      {s.objections && s.objections.length > 0 && (
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="text-xs text-subtle">Objections:</span>
                          {s.objections.map((o, i) => (
                            <Badge key={`${s.id}-objection-${i}`} tone="warn">{o}</Badge>
                          ))}
                        </div>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState
                icon={HeartHandshake}
                title="No segments yet"
                description="Segments emerge once at least 3 audience signals have been ingested and analyzed."
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Dna className="h-4 w-4 text-accent" /> Content pillars
            </CardTitle>
            <CardDescription>The recurring topics you own.</CardDescription>
          </CardHeader>
          <CardContent>
            {state?.content_pillars && state.content_pillars.length > 0 ? (
              <ul className="space-y-3">
                {state.content_pillars.map((p) => (
                  <li key={p.id}>
                    <p className="text-sm font-medium text-ink">{p.name}</p>
                    {p.description && <p className="text-sm text-subtle">{p.description}</p>}
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState
                icon={Dna}
                title="No pillars yet"
                description="Pillars emerge once at least 3 pieces of content with transcripts have been ingested and analyzed."
              />
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-accent" /> Boundaries
            </CardTitle>
            <CardDescription>Topics you avoid, claims you won't make, tone you reject.</CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <SkeletonText lines={2} />
            ) : state?.positioning?.prohibited_topics?.length ? (
              <ul className="list-inside list-disc text-sm text-ink">
                {state.positioning.prohibited_topics.map((t) => (
                  <li key={t}>{t}</li>
                ))}
              </ul>
            ) : (
              <EmptyState
                icon={Shield}
                title="No boundaries set"
                description="Set the topics, claims, and tones that are off-limits so nothing generated for you ever crosses them."
              />
            )}
          </CardContent>
        </Card>

        <CommercialProfileCard profile={state?.commercial_profile ?? null} onSaved={refetch} />
      </div>
    </div>
  );
}
