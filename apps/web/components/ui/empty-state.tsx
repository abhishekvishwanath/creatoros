"use client";

import { LucideIcon } from "lucide-react";
import { motion } from "framer-motion";

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border px-6 py-12 text-center"
    >
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-ink/8">
        <Icon className="h-5 w-5 text-subtle" strokeWidth={1.75} />
      </div>
      <p className="text-sm font-medium text-ink">{title}</p>
      <p className="mt-1 max-w-sm text-sm text-subtle">{description}</p>
      {action && <div className="mt-4">{action}</div>}
    </motion.div>
  );
}
