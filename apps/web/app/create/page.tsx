import { PenSquare } from "lucide-react";
import { PlaceholderPage } from "@/components/placeholder-page";

export default function CreatePage() {
  return (
    <PlaceholderPage
      icon={PenSquare}
      title="Create"
      description="Angle → hook → brief → script → critique → improved script."
      emptyTitle="Pick an opportunity to start creating"
      emptyDescription="Approve an opportunity and this workspace will walk it through a brief, hook options, a first script draft, an editorial critique, and a rewrite — with every evidence reference kept alongside it."
    />
  );
}
