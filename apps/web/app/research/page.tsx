"use client";

import { TrendingUp, LayoutGrid } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ResearchSignalsCard } from "@/components/research-signals-card";
import { AudienceSignalsCard } from "@/components/audience-signals-card";
import { TrendsCard } from "@/components/trends-card";
import { useCreatorState } from "@/lib/use-creator-state";

const SECTIONS = [
  {
    title: "Market pulse",
    description: "What's moving across your niche right now.",
    icon: TrendingUp,
    empty: "Live web research isn't connected yet.",
  },
  {
    title: "Content gaps",
    description: "What your audience wants that nobody (including you) has made yet.",
    icon: LayoutGrid,
    empty: "Needs both audience and competitor signal before gaps can be identified.",
  },
];

export default function ResearchPage() {
  const { state, refetch } = useCreatorState();

  return (
    <div>
      <PageHeader title="Research" description="What matters right now — for this creator, this audience, this niche." />
      <div className="grid grid-cols-1 gap-4 p-8 md:grid-cols-2">
        <ResearchSignalsCard signals={state?.current_research_signals ?? []} onIngested={refetch} />
        <AudienceSignalsCard />
        <TrendsCard />

        {SECTIONS.map((s) => (
          <Card key={s.title}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <s.icon className="h-4 w-4 text-accent" /> {s.title}
              </CardTitle>
              <CardDescription>{s.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <EmptyState icon={s.icon} title="Not connected yet" description={s.empty} />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
