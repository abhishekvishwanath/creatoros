import { Lightbulb } from "lucide-react";
import { PlaceholderPage } from "@/components/placeholder-page";

export default function OpportunitiesPage() {
  return (
    <PlaceholderPage
      icon={Lightbulb}
      title="Opportunities"
      description="The strongest things you should make next, ranked and explained."
      emptyTitle="No opportunities yet"
      emptyDescription="Opportunities are generated from creator fit, audience fit, demand, novelty, and evidence — once Creator DNA, audience intelligence, and research are in place, ranked cards with a full 'why this, why now' breakdown will show up here (never a single opaque score)."
    />
  );
}
