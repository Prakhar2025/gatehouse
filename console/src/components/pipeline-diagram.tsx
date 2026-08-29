"use client";

import { motion } from "framer-motion";

/**
 * The gate, drawn. Animated SVG pipeline shared by the landing and
 * how-it-works pages: one untrusted signal becomes three possible endings,
 * and the graduated silence law decides which.
 */
const STAGES = [
  { id: "signal", label: "Signal", sub: "forwarded, fenced" },
  { id: "triage", label: "Triage", sub: "Bedrock Nova" },
  { id: "verify", label: "Verify", sub: "registries" },
  { id: "graph", label: "Graph", sub: "HMAC hashes" },
  { id: "guardian", label: "Guardian", sub: "code decides" },
];

const ENDINGS = [
  { label: "SAFE", sub: "handled silently", cls: "text-[#3ddc84] border-[#14532d] bg-[#0c2318]" },
  { label: "SUSPICIOUS", sub: "review with evidence", cls: "text-[#f5b83d] border-[#6b4a0d] bg-[#2a1e06]" },
  { label: "SCAM", sub: "warn, guard, record", cls: "text-[#ff6b6b] border-[#6e1c1c] bg-[#2b0d0d]" },
];

export function PipelineDiagram() {
  return (
    <div className="w-full overflow-x-auto">
      <svg viewBox="0 0 920 150" className="min-w-[720px] w-full" role="img" aria-label="Gatehouse investigation pipeline">
        <defs>
          <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill="#5b5b66" />
          </marker>
        </defs>
        {STAGES.map((s, i) => {
          const x = 20 + i * 180;
          return (
            <g key={s.id}>
              <motion.rect
                x={x}
                y={45}
                width={140}
                height={58}
                rx={8}
                fill="#131316"
                stroke="#34343c"
                initial={{ opacity: 0, y: 8 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.12, duration: 0.4 }}
              />
              <text x={x + 70} y={70} textAnchor="middle" className="fill-white" fontSize="14" fontWeight="600">
                {s.label}
              </text>
              <text x={x + 70} y={88} textAnchor="middle" fill="#8f8f9b" fontSize="10.5">
                {s.sub}
              </text>
              {i < STAGES.length - 1 ? (
                <motion.line
                  x1={x + 142}
                  y1={74}
                  x2={x + 178}
                  y2={74}
                  stroke="#5b5b66"
                  strokeWidth={1.5}
                  markerEnd="url(#arr)"
                  initial={{ pathLength: 0 }}
                  whileInView={{ pathLength: 1 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.12 * i + 0.3, duration: 0.35 }}
                />
              ) : null}
            </g>
          );
        })}
        {ENDINGS.map((e, i) => {
          const x = 380 + i * 180;
          return (
            <g key={e.label}>
              <motion.line
                x1={740}
                y1={103}
                x2={x + 70}
                y2={128}
                stroke="#3a3a42"
                strokeWidth={1}
                strokeDasharray="3 3"
                initial={{ opacity: 0 }}
                whileInView={{ opacity: 1 }}
                viewport={{ once: true }}
                transition={{ delay: 0.9 + i * 0.15 }}
              />
              <motion.rect
                x={x}
                y={130}
                width={140}
                height={1}
                fill="transparent"
                initial={{ opacity: 0 }}
                whileInView={{ opacity: 1 }}
                viewport={{ once: true }}
                transition={{ delay: 0.9 + i * 0.15 }}
              />
              <motion.text
                x={x + 70}
                y={148}
                textAnchor="middle"
                fontSize="11.5"
                fontWeight="600"
                className={e.cls.split(" ")[0]}
                initial={{ opacity: 0 }}
                whileInView={{ opacity: 1 }}
                viewport={{ once: true }}
                transition={{ delay: 1 + i * 0.15 }}
              >
                {e.label}
              </motion.text>
              <motion.text
                x={x + 70}
                y={162}
                textAnchor="middle"
                fontSize="9.5"
                fill="#8f8f9b"
                initial={{ opacity: 0 }}
                whileInView={{ opacity: 1 }}
                viewport={{ once: true }}
                transition={{ delay: 1.05 + i * 0.15 }}
              >
                {e.sub}
              </motion.text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
