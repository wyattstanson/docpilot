import React from "react";

const MAP = {
  green: { ring: "#8a9a5b", label: "All docs current", tone: "sage" },
  amber: { ring: "#d8b26a", label: "Review needed", tone: "sand" },
  red: { ring: "#d9542f", label: "Critical staleness", tone: "clay" },
};

export default function HealthOrb({ status = "green" }) {
  const c = MAP[status] || MAP.green;
  return (
    <div className="glass flex items-center gap-5 p-5">
      <div className="relative grid h-14 w-14 place-items-center">
        {/* steady editorial seal — a ringed disc, no neon glow */}
        <span
          className="absolute inset-0 rounded-full border-2"
          style={{ borderColor: c.ring, opacity: 0.4 }}
        />
        <span
          className="h-7 w-7 rounded-full animate-breathe"
          style={{ background: c.ring }}
        />
      </div>
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-label text-paper-400">
          System Health
        </p>
        <p className="mt-1 font-serif text-lg font-semibold text-paper-50">{c.label}</p>
      </div>
    </div>
  );
}
