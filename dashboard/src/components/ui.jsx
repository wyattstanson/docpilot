import React from "react";
import { CONFIDENCE, STATUS } from "../lib/format.js";

export function Skeleton({ className = "" }) {
  return <div className={`skeleton animate-shimmer rounded-md ${className}`} />;
}

export function ConfidenceBadge({ value }) {
  const c = CONFIDENCE[value] || CONFIDENCE.low;
  return <span className={`chip ${c.cls}`}>{c.label}</span>;
}

export function StatusBadge({ value }) {
  const s = STATUS[value] || STATUS.pending;
  return <span className={`chip ${s.cls}`}>{s.label}</span>;
}

export function StatCard({ icon: Icon, label, value, accent = "clay", loading }) {
  const tone = accent === "cyan" ? "text-sand" : "text-clay";
  return (
    <div className="glass glass-hover animate-slide-in p-5">
      <div className="flex items-start justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-label text-paper-400">
          {label}
        </span>
        <span className={`border border-paper-50/10 rounded-md p-2 ${tone}`}>
          {Icon && <Icon size={16} strokeWidth={2} />}
        </span>
      </div>
      {loading ? (
        <Skeleton className="mt-4 h-10 w-20" />
      ) : (
        <div className="mt-3 font-serif text-5xl font-semibold tracking-tight text-paper-50">
          {value}
        </div>
      )}
    </div>
  );
}

export function SectionHeader({ title, subtitle, children }) {
  return (
    <div className="mb-7">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-serif text-3xl font-semibold tracking-tight text-paper-50">
            {title}
          </h1>
          {subtitle && <p className="mt-1.5 max-w-xl text-sm text-paper-400">{subtitle}</p>}
        </div>
        {children}
      </div>
      <div className="rule mt-5 animate-rule-draw" />
    </div>
  );
}

export function EmptyState({ icon: Icon, title, hint }) {
  return (
    <div className="glass flex flex-col items-center justify-center gap-3 px-6 py-16 text-center">
      {Icon && <Icon size={28} className="text-paper-400" strokeWidth={1.5} />}
      <p className="font-serif text-lg text-paper-100">{title}</p>
      {hint && <p className="max-w-sm text-xs text-paper-400">{hint}</p>}
    </div>
  );
}
