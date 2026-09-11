"use client";

import { useMemo, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Line, Sparkles, Html, Float } from "@react-three/drei";
import * as THREE from "three";

// The real loop this product runs (CLAUDE.md §63/§65) — not a decorative
// shape. Each node lights up in the pipeline-progress view as its real
// backend stage completes (see PipelineNode below).
const STAGES = ["Research", "Strategy", "Content", "Performance", "Learning"] as const;
export type StageStatus = "pending" | "active" | "done";

const ACCENT = "#6366f1";
const NODE_IDLE = "#a5b4fc";
const NODE_DONE = "#34d399";

function CreatorCore() {
  const ref = useRef<THREE.Mesh>(null);
  useFrame((_, delta) => {
    if (ref.current) ref.current.rotation.y += delta * 0.25;
  });
  return (
    <Float speed={1.2} rotationIntensity={0.3} floatIntensity={0.6}>
      <mesh ref={ref}>
        <icosahedronGeometry args={[0.85, 1]} />
        <meshStandardMaterial color={ACCENT} emissive={ACCENT} emissiveIntensity={0.55} roughness={0.25} metalness={0.2} />
      </mesh>
    </Float>
  );
}

function OrbitNode({
  angle,
  radius,
  yOffset,
  label,
  status,
}: {
  angle: number;
  radius: number;
  yOffset: number;
  label: string;
  status: StageStatus;
}) {
  // Y comes from a fixed per-node offset (yOffset), not a function of the
  // rotating angle — that guarantees every node sits at a distinct height
  // no matter how the scene has rotated, so labels never stack on top of
  // each other. An angle-derived Y (tried first) put two nodes at
  // near-identical screen positions at certain rotations, including the
  // very first frame a visitor sees.
  const position: [number, number, number] = useMemo(
    () => [Math.cos(angle) * radius, yOffset, Math.sin(angle) * radius],
    [angle, radius, yOffset]
  );
  const color = status === "pending" ? NODE_IDLE : status === "active" ? ACCENT : NODE_DONE;
  const scale = status === "active" ? 1.25 : 1;

  return (
    <group>
      <Line points={[[0, 0, 0], position]} color={color} transparent opacity={status === "pending" ? 0.15 : 0.5} lineWidth={1} />
      <mesh position={position} scale={scale}>
        <sphereGeometry args={[0.24, 16, 16]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={status === "pending" ? 0.15 : 0.6} />
      </mesh>
      {/* Real DOM text via drei's Html (tracks the 3D position) rather than
          WebGL-rendered text (drei's Text/troika) — avoids font-shaping in
          the GL context entirely, which is both lighter and sidesteps a
          real failure mode observed under software-rendered WebGL (a lost
          context with no visible fallback). A small opaque chip (not just
          colored text) keeps it legible regardless of what's behind the
          canvas at this spot — text tokens make it theme-aware. */}
      <Html position={position} center style={{ pointerEvents: "none" }} zIndexRange={[0, 0]}>
        <span
          className={
            "whitespace-nowrap rounded-full border border-border bg-canvas-raised px-1.5 py-0.5 text-[9px] font-medium shadow-sm " +
            (status === "pending" ? "text-subtle" : "text-ink")
          }
          style={{ transform: "translateY(20px)" }}
        >
          {label}
        </span>
      </Html>
    </group>
  );
}

function Scene({ statuses }: { statuses?: Partial<Record<(typeof STAGES)[number], StageStatus>> }) {
  const groupRef = useRef<THREE.Group>(null);
  useFrame((_, delta) => {
    if (groupRef.current) groupRef.current.rotation.y += delta * 0.12;
  });

  return (
    <>
      <ambientLight intensity={0.5} />
      <pointLight position={[4, 4, 4]} intensity={40} color="#818cf8" />
      <pointLight position={[-4, -2, -4]} intensity={20} color="#22d3ee" />
      <Sparkles count={35} scale={7} size={2} speed={0.2} color="#a5b4fc" opacity={0.35} />
      <group ref={groupRef}>
        <CreatorCore />
        {STAGES.map((label, i) => (
          <OrbitNode
            key={label}
            angle={(i / STAGES.length) * Math.PI * 2}
            radius={3.0}
            yOffset={(i - (STAGES.length - 1) / 2) * 0.55}
            label={label}
            status={statuses?.[label] ?? "pending"}
          />
        ))}
      </group>
    </>
  );
}

export function CreatorBrainScene({
  className,
  statuses,
}: {
  className?: string;
  statuses?: Partial<Record<(typeof STAGES)[number], StageStatus>>;
}) {
  // Skip WebGL entirely if it's unavailable (old browsers, some headless/
  // locked-down environments) rather than crash the page it's embedded in.
  const [supported] = useState(() => {
    if (typeof window === "undefined") return true;
    try {
      const canvas = document.createElement("canvas");
      return !!(canvas.getContext("webgl") || canvas.getContext("experimental-webgl"));
    } catch {
      return false;
    }
  });
  // A driver can still lose the context after creation (low-end/virtual
  // GPUs, some sandboxed environments — observed directly under headless
  // software rendering). Rendering nothing at that point is better than a
  // dead canvas sitting where content was expected.
  const [lost, setLost] = useState(false);

  if (!supported || lost) return null;

  return (
    <div className={className}>
      <Canvas
        dpr={[1, 1.75]}
        camera={{ position: [0, 0.6, 8.5], fov: 50 }}
        gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
        onCreated={({ gl }) => {
          gl.domElement.addEventListener("webglcontextlost", (e) => {
            e.preventDefault();
            setLost(true);
          });
        }}
      >
        <Scene statuses={statuses} />
      </Canvas>
    </div>
  );
}
