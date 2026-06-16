import React, { useEffect, useMemo, useState } from "react";
import { ChevronDown, FileWarning } from "lucide-react";
import { api, SAMPLE, withFallback } from "../api/client.js";
import { SectionHeader, Skeleton, ConfidenceBadge, StatusBadge, EmptyState } from "../components/ui.jsx";
import DiffViewer from "../components/DiffViewer.jsx";
import { CHANGE_TYPE } from "../lib/format.js";

const FILTERS = ["all", "high", "medium", "low"];

export default function StalenessReport() {
  const [data, setData] = useState(null);
  const [filter, setFilter] = useState("all");
  const [open, setOpen] = useState(null);

  useEffect(() => {
    withFallback(api.staleness, SAMPLE.staleness).then((d) => setData(d.findings));
  }, []);

  const rows = useMemo(() => {
    if (!data) return [];
    return filter === "all" ? data : data.filter((f) => f.confidence === filter);
  }, [data, filter]);

  return (
    <div className="animate-fade-in">
      <SectionHeader title="Staleness Report" subtitle="Every detected stale section, with the proposed correction.">
        <div className="glass flex gap-1 p-1">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium capitalize transition ${
                filter === f ? "bg-violet-glow text-paper-50 shadow-glow" : "text-paper-400 hover:text-paper-50"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </SectionHeader>

      {!data ? (
        <div className="flex flex-col gap-3">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-16 w-full" />)}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState icon={FileWarning} title="No stale sections" hint="Documentation is up to date for this filter." />
      ) : (
        <div className="glass overflow-hidden">
          <div className="grid grid-cols-12 gap-3 border-b border-paper-50/5 px-5 py-3 text-[11px] font-semibold uppercase tracking-wider text-paper-400">
            <div className="col-span-4">Doc Section</div>
            <div className="col-span-3">Linked Code</div>
            <div className="col-span-2">Change</div>
            <div className="col-span-2">Confidence</div>
            <div className="col-span-1 text-right">Status</div>
          </div>
          {rows.map((f, i) => (
            <div key={f.id} className="border-b border-paper-50/5 last:border-0">
              <button
                onClick={() => setOpen(open === f.id ? null : f.id)}
                style={{ animationDelay: `${i * 40}ms` }}
                className="animate-slide-in grid w-full grid-cols-12 items-center gap-3 px-5 py-3.5 text-left transition hover:bg-paper-50/[0.03]"
              >
                <div className="col-span-4 flex items-center gap-2">
                  <ChevronDown
                    size={15}
                    className={`shrink-0 text-paper-400 transition-transform ${open === f.id ? "rotate-180" : ""}`}
                  />
                  <span className="truncate text-sm font-medium text-paper-50">{f.heading}</span>
                </div>
                <div className="col-span-3 truncate font-mono text-xs text-paper-400">{f.file}</div>
                <div className="col-span-2 text-xs text-paper-200">{CHANGE_TYPE[f.change_type] || f.change_type}</div>
                <div className="col-span-2"><ConfidenceBadge value={f.confidence} /></div>
                <div className="col-span-1 flex justify-end"><StatusBadge value={f.status} /></div>
              </button>
              {open === f.id && (
                <div className="animate-fade-in space-y-4 bg-black/20 px-5 py-5">
                  <div className="rounded-md border border-sand/25 bg-sand/[0.05] px-4 py-3">
                    <p className="text-[10px] font-semibold uppercase tracking-label text-sand-soft">Diagnosis</p>
                    <p className="mt-1 text-sm text-paper-200">{f.diagnosis}</p>
                  </div>
                  {f.corrected ? (
                    <DiffViewer original={f.original} corrected={f.corrected} />
                  ) : (
                    <p className="text-sm text-paper-400">Flagged for human review — no automatic fix generated.</p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
