import { BarChart3 } from "lucide-react";
import { PlaceholderPage } from "@/components/placeholder-page";

export default function AnalyticsPage() {
  return (
    <PlaceholderPage
      icon={BarChart3}
      title="Analytics"
      description="What changed, why it may have changed, and what to test next."
      emptyTitle="No performance data yet"
      emptyDescription="Once content is published and metrics sync, diagnoses will appear here compared against your own baseline — never raw numbers without interpretation."
    />
  );
}
