import { CalendarDays } from "lucide-react";
import { PlaceholderPage } from "@/components/placeholder-page";

export default function CalendarPage() {
  return (
    <PlaceholderPage
      icon={CalendarDays}
      title="Calendar"
      description="Your content portfolio, production status, and capacity."
      emptyTitle="Nothing scheduled yet"
      emptyDescription="Content moves through IDEA → APPROVED → BRIEFED → SCRIPTED → RECORDED → EDITING → REVIEW → SCHEDULED → PUBLISHED → ANALYZING → LEARNED. Approve an opportunity in Opportunities to start filling this in."
    />
  );
}
