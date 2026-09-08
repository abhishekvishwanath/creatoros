import { Badge } from "@/components/ui/badge";

export function ConfidenceBadge({ confidence }: { confidence: number }) {
  if (confidence >= 0.75) return <Badge tone="good">high confidence</Badge>;
  if (confidence >= 0.4) return <Badge tone="warn">medium confidence</Badge>;
  return <Badge tone="neutral">low confidence</Badge>;
}
