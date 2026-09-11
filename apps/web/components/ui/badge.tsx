import { HTMLAttributes } from "react";
import clsx from "clsx";

type Tone = "neutral" | "accent" | "good" | "warn" | "bad";

const toneClasses: Record<Tone, string> = {
  neutral: "bg-ink/8 text-subtle",
  accent: "bg-accent-soft text-accent",
  good: "bg-good-soft text-good",
  warn: "bg-warn-soft text-warn",
  bad: "bg-bad-soft text-bad",
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
