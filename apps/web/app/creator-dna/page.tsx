"use client";

import { useState } from "react";
import { Dna, Mic, Users, Target, Shield, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ContentLibraryCard } from "@/components/content-library-card";
import { useCreatorState } from "@/lib/use-creator-state";
import { getSession } from "@/lib/session";
import { analyzeCreator, ApiError } from "@/lib/api";

function ConfidenceBadge({ confidence }: { confidence: number }) {
  if (confidence >= 0.75) return <Badge tone="good">high confidence</Badge>;
  if (confidence >= 0.4) return <Badge tone="warn">medium confidence</Badge>;
  return <Badge tone="neutral">low confidence</Badge>;
}

export default function CreatorDnaPage() {
  const { state, loading, refetch } = useCreatorState();
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [analyzeWarnings, setAnalyzeWarnings] = useState<string[]>([]);

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

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Target className="h-4 w-4 text-accent" /> Positioning
            </CardTitle>
            <CardDescription>Identity, expertise, and how you're positioned.</CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-sm text-subtle">Loading…</p>
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
              <p className="text-sm text-subtle">Loading…</p>
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
            <CardTitle className="flex items-center gap-2">
              <Users className="h-4 w-4 text-accent" /> Audience
            </CardTitle>
            <CardDescription>Who you're speaking to.</CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-sm text-subtle">Loading…</p>
            ) : state?.audience ? (
              <div className="space-y-2">
                <ConfidenceBadge confidence={state.audience.confidence} />
                <p className="text-sm text-ink">{state.audience.knowledge_level}</p>
              </div>
            ) : (
              <EmptyState
                icon={Users}
                title="Not analyzed yet"
                description="Audience problems, desires, and objections are built from comments and connected analytics."
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
              <p className="text-sm text-subtle">Loading…</p>
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
      </div>
    </div>
  );
}
