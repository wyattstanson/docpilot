import React from "react";

// Lightweight side-by-side diff: line-level set comparison, good enough to
// highlight what changed between the original and corrected doc sections.
function classify(lines, other) {
  const set = new Set(other.map((l) => l.trim()));
  return lines.map((l) => ({ text: l, changed: l.trim() !== "" && !set.has(l.trim()) }));
}

function Pane({ title, lines, tone }) {
  const accent =
    tone === "old"
      ? "border-clay/20 bg-clay/[0.04]"
      : "border-sage/25 bg-sage/[0.05]";
  const lineMark =
    tone === "old"
      ? "bg-clay/10 text-clay-soft border-l-2 border-clay/60"
      : "bg-sage/10 text-sage-soft border-l-2 border-sage/60";
  return (
    <div className={`flex-1 overflow-hidden rounded-md border ${accent}`}>
      <div className="border-b border-paper-50/10 px-4 py-2 text-[10px] font-semibold uppercase tracking-label text-paper-400">
        {title}
      </div>
      <pre className="max-h-72 overflow-auto p-3 font-mono text-[12.5px] leading-relaxed text-paper-200">
        {lines.map((l, i) => (
          <div
            key={i}
            className={`whitespace-pre-wrap px-2 py-0.5 transition-colors duration-200 ${l.changed ? lineMark : ""}`}
          >
            {l.text || " "}
          </div>
        ))}
      </pre>
    </div>
  );
}

export default function DiffViewer({ original = "", corrected = "" }) {
  const o = (original || "").split("\n");
  const c = (corrected || "").split("\n");
  return (
    <div className="flex flex-col gap-3 md:flex-row">
      <Pane title="Current docs" tone="old" lines={classify(o, c)} />
      <Pane title="DocPilot correction" tone="new" lines={classify(c, o)} />
    </div>
  );
}
