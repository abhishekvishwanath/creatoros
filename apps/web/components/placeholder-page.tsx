import { LucideIcon } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/ui/empty-state";

export function PlaceholderPage({
  title,
  description,
  icon,
  emptyTitle,
  emptyDescription,
}: {
  title: string;
  description: string;
  icon: LucideIcon;
  emptyTitle: string;
  emptyDescription: string;
}) {
  return (
    <div>
      <PageHeader title={title} description={description} />
      <div className="p-8">
        <EmptyState icon={icon} title={emptyTitle} description={emptyDescription} />
      </div>
    </div>
  );
}
