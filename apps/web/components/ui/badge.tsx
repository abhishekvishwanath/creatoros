import { HTMLAttributes } from "react";
import clsx from "clsx";

type Tone = "neutral" | "accent" | "good" | "warn" | "bad";

const toneClasses: Record<Tone, string> = {
  neutral: "bg-zinc-100 text-zinc-600",
  accent: "bg-accent-soft text-accent",
  good: "bg-green-50 text-good",
  warn: "bg-amber-50 text-warn",
  bad: "bg-red-50 text-bad",
};

export function Badge({
  tone = "neutral",
  className,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        toneClasses[tone],
        className
      )}
      {...props}
    />
  );
}
