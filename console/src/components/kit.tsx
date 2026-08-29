"use client";

/**
 * The premium kit: the interactions that separate a designed page from a
 * styled one. Spotlight cards that follow the mouse, blueprint grid with
 * vignette, film grain, animated counters, beam dividers, scroll reveals,
 * and a marquee. Zero extra dependencies.
 */
import { motion, useInView, useMotionValue, useSpring, useTransform } from "framer-motion";
import { useEffect, useRef, useState } from "react";

/** Film grain so dark surfaces read as material, not flat color. */
export function Noise({ opacity = 0.04 }: { opacity?: number }) {
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 z-50"
      style={{
        opacity,
        backgroundImage:
          "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='160' height='160' filter='url(%23n)' opacity='0.6'/%3E%3C/svg%3E\")",
      }}
    />
  );
}

/** Vercel-style blueprint grid that fades toward the edges. */
export function GridBackground({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={`pointer-events-none absolute inset-0 ${className ?? ""}`}
      style={{
        backgroundImage:
          "linear-gradient(to right, rgba(236,233,228,0.05) 1px, transparent 1px), linear-gradient(to bottom, rgba(236,233,228,0.05) 1px, transparent 1px)",
        backgroundSize: "56px 56px",
        maskImage: "radial-gradient(ellipse 90% 70% at 50% 0%, black 35%, transparent 100%)",
        WebkitMaskImage: "radial-gradient(ellipse 90% 70% at 50% 0%, black 35%, transparent 100%)",
      }}
    />
  );
}

/** Card whose border and interior glow track the pointer. */
export function SpotlightCard({
  children,
  className,
  glow = "255,180,84",
}: {
  children: React.ReactNode;
  className?: string;
  glow?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mx = useMotionValue(-400);
  const my = useMotionValue(-400);
  const sx = useSpring(mx, { stiffness: 220, damping: 26 });
  const sy = useSpring(my, { stiffness: 220, damping: 26 });
  return (
    <div
      ref={ref}
      onMouseMove={(e) => {
        const r = ref.current?.getBoundingClientRect();
        if (!r) return;
        mx.set(e.clientX - r.left);
        my.set(e.clientY - r.top);
      }}
      onMouseLeave={() => {
        mx.set(-400);
        my.set(-400);
      }}
      className={`group relative overflow-hidden rounded-xl border border-line bg-card ${className ?? ""}`}
    >
      <motion.div
        aria-hidden
        className="pointer-events-none absolute -inset-px rounded-xl"
        style={{
          background: useTransform(
            [sx, sy],
            ([x, y]: number[]) =>
              `radial-gradient(340px circle at ${x}px ${y}px, rgba(${glow},0.12), transparent 65%)`,
          ),
        }}
      />
      <div className="relative">{children}</div>
    </div>
  );
}

/** Number that counts up when scrolled into view. */
export function Counter({
  to,
  prefix = "",
  suffix = "",
  decimals = 0,
}: {
  to: number;
  prefix?: string;
  suffix?: string;
  decimals?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const [val, setVal] = useState(0);
  useEffect(() => {
    if (!inView) return;
    const start = performance.now();
    const dur = 1400;
    let raf = 0;
    const step = (t: number) => {
      const p = Math.min(1, (t - start) / dur);
      setVal(to * (1 - Math.pow(1 - p, 3)));
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [inView, to]);
  return (
    <span ref={ref} className="tabular-nums">
      {prefix}
      {val.toFixed(decimals)}
      {suffix}
    </span>
  );
}

/** Horizontal light beam that sweeps across on reveal. */
export function Beam({ delay = 0 }: { delay?: number }) {
  return (
    <div className="relative mx-auto h-px w-full max-w-5xl overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-line-strong to-transparent" />
      <motion.div
        className="absolute inset-y-0 w-1/3 bg-gradient-to-r from-transparent via-accent to-transparent"
        initial={{ x: "-120%" }}
        whileInView={{ x: "380%" }}
        viewport={{ once: true }}
        transition={{ duration: 1.6, delay, ease: "easeInOut" }}
      />
    </div>
  );
}

/** Scroll reveal wrapper. */
export function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.65, delay, ease: [0.16, 1, 0.3, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/** Scam-class marquee: infinite horizontal ticker. */
export function Marquee({ items }: { items: string[] }) {
  const row = [...items, ...items];
  return (
    <div className="relative overflow-hidden py-3" aria-hidden>
      <div className="pointer-events-none absolute inset-y-0 left-0 z-10 w-24 bg-gradient-to-r from-bg to-transparent" />
      <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-24 bg-gradient-to-l from-bg to-transparent" />
      <motion.div
        className="flex w-max gap-10"
        animate={{ x: ["0%", "-50%"] }}
        transition={{ duration: 28, ease: "linear", repeat: Infinity }}
      >
        {row.map((t, i) => (
          <span key={i} className="flex items-center gap-10 font-mono text-xs uppercase tracking-[0.25em] text-fg-subtle">
            {t}
            <span className="text-accent">×</span>
          </span>
        ))}
      </motion.div>
    </div>
  );
}
