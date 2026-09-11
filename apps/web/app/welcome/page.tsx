"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, Sparkles, Target, TrendingUp, Brain } from "lucide-react";
import { Button } from "@/components/ui/button";

const CreatorBrainScene = dynamic(
  () => import("@/components/three/creator-brain-scene").then((m) => m.CreatorBrainScene),
  { ssr: false }
);

const PILLARS = [
  {
    icon: Brain,
    title: "Understands you",
    description: "Creator DNA built from your own content — positioning, voice, and pillars, not a generic template.",
  },
  {
    icon: Target,
    title: "Finds real opportunities",
    description: "Every recommendation is evidence-linked — real research signals, real scores, never an opaque number.",
  },
  {
    icon: TrendingUp,
    title: "Learns what works",
    description: "Performance feeds a learning engine that compounds — next week's strategy already knows what happened last week.",
  },
];

export default function WelcomePage() {
  return (
    <div className="min-h-screen bg-canvas">
      <header className="flex items-center justify-between px-6 py-5 sm:px-10">
        <span className="text-sm font-semibold tracking-tight text-ink">Creator Intelligence OS</span>
        <Link href="/login" className="text-sm font-medium text-subtle hover:text-ink">
          Sign in
        </Link>
      </header>

      <section className="mx-auto flex max-w-6xl flex-col items-center px-6 pb-8 pt-2 text-center">
        <div className="pointer-events-none h-[300px] w-full sm:h-[380px]">
          <CreatorBrainScene className="h-full w-full" />
        </div>
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="-mt-4"
        >
          <span className="inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-3 py-1 text-xs font-medium text-accent">
            <Sparkles className="h-3 w-3" /> Paste a link. Every engine starts.
          </span>
          <h1 className="mx-auto mt-5 max-w-2xl text-3xl font-semibold tracking-tight text-ink sm:text-5xl">
            The AI strategist that knows your creator business
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-sm text-subtle sm:text-base">
            Not a script generator. A Creator Intelligence OS that understands who you are, researches your
            market, scores real opportunities, and learns from what happens after you publish.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link href="/login">
              <Button className="px-6 py-3 text-base">
                Get started <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </div>
        </motion.div>
      </section>

      <section className="mx-auto max-w-5xl px-6 pb-24 pt-12 sm:pt-16">
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
          {PILLARS.map((p, i) => (
            <motion.div
              key={p.title}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.4, delay: i * 0.08 }}
              className="rounded-xl border border-border bg-canvas-raised p-6 shadow-card"
            >
              <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-full bg-accent-soft">
                <p.icon className="h-4 w-4 text-accent" strokeWidth={1.75} />
              </div>
              <h3 className="text-sm font-semibold text-ink">{p.title}</h3>
              <p className="mt-1.5 text-sm text-subtle">{p.description}</p>
            </motion.div>
          ))}
        </div>
      </section>
    </div>
  );
}
