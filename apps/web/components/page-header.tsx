"use client";

import { motion } from "framer-motion";

export function PageHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="flex flex-col gap-3 border-b border-border bg-canvas-raised px-4 py-5 sm:flex-row sm:items-start sm:justify-between sm:px-8 sm:py-6"
    >
      <div>
        <h1 className="text-lg font-semibold text-ink">{title}</h1>
        {description && <p className="mt-1 text-sm text-subtle">{description}</p>}
      </div>
      {action}
    </motion.div>
  );
}
