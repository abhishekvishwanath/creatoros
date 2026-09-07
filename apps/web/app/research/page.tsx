import { Compass, Users, TrendingUp, LayoutGrid, Bookmark, Radar } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";

const SECTIONS = [
  {
    title: "Market pulse",
    description: "What's moving across your niche right now.",
    icon: TrendingUp,
    empty: "Live web research isn't connected yet.",
  },
  {
    title: "Competitor radar",
    description: "What comparable creators are publishing and how it's landing.",
    icon: Radar,
    empty: "Add competitors in Creator DNA to start tracking them here.",
  },
  {
    title: "Audience voice",
    description: "Problems, desires, and questions your audience keeps raising.",
    icon: Users,
    empty: "No audience signal ingested yet — comments and connected analytics will populate this.",
  },
  {
    title: "Emerging topics",
    description: "Momentum building before it saturates.",
    icon: Compass,
    empty: "Topic momentum tracking isn't connected yet.",
  },
  {
    title: "Content gaps",
    description: "What your audience wants that nobody (including you) has made yet.",
    icon: LayoutGrid,
    empty: "Needs both audience and competitor signal before gaps can be identified.",
  },
  {
    title: "Saved signals",
    description: "Research you've bookmarked for later.",
    icon: Bookmark,
    empty: "Nothing saved yet.",
  },
];

export default function ResearchPage() {
  return (
    <div>
      <PageHeader title="Research" description="What matters right now — for this creator, this audience, this niche." />
      <div className="grid grid-cols-1 gap-4 p-8 md:grid-cols-2">
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
