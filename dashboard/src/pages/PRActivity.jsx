import React, { useEffect, useState } from "react";
import { GitPullRequest, GitMerge, ExternalLink, CircleDot } from "lucide-react";
import { api, SAMPLE, withFallback } from "../api/client.js";
import { SectionHeader, Skeleton, ConfidenceBadge, EmptyState } from "../components/ui.jsx";
import { timeAgo } from "../lib/format.js";

export default function PRActivity() {
  const [prs, setPrs] = useState(null);

  useEffect(() => {
    withFallback(api.prs, SAMPLE.prs).then((d) => setPrs(d.prs));
  }, []);

  return (
    <div className="animate-fade-in">
      <SectionHeader title="PR Activity" subtitle="Pull requests DocPilot opened to heal stale documentation." />

      {!prs ? (
        <div className="flex flex-col gap-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-24 w-full" />)}</div>
      ) : prs.length === 0 ? (
        <EmptyState icon={GitPullRequest} title="No PRs yet" hint="DocPilot opens a PR when it auto-fixes a stale section." />
      ) : (
        <div className="relative ml-3 border-l border-paper-50/10 pl-8">
          {prs.map((pr, i) => {
            const merged = pr.merge_status === "merged";
            return (
              <div key={pr.id} style={{ animationDelay: `${i * 70}ms` }} className="animate-slide-in relative mb-5">
                <span
                  className={`absolute -left-[42px] grid h-7 w-7 place-items-center rounded-full border ${
                    merged ? "border-violet-glow/40 bg-violet-glow/15 text-violet-soft" : "border-cyan-glow/40 bg-cyan-glow/15 text-cyan-glow"
                  }`}
                >
                  {merged ? <GitMerge size={14} /> : <CircleDot size={14} />}
                </span>
                <a
                  href={pr.url}
                  target="_blank"
                  rel="noreferrer"
                  className="glass glass-hover block p-4"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-2.5">
                      <span className="font-mono text-xs text-paper-400">#{pr.number}</span>
                      <span className="font-medium text-paper-50">{pr.title}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <ConfidenceBadge value={pr.confidence} />
                      <span
                        className={`chip ${
                          merged ? "bg-violet-glow/15 text-violet-soft border border-violet-glow/30" : "bg-cyan-glow/15 text-cyan-glow border border-cyan-glow/30"
                        }`}
                      >
                        {merged ? "Merged" : "Open"}
                      </span>
                      <ExternalLink size={14} className="text-paper-400" />
                    </div>
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-paper-400">
                    <span>Sections fixed:</span>
                    {pr.sections.map((s) => (
                      <span key={s} className="rounded-md bg-paper-50/5 px-2 py-0.5 font-mono text-[11px] text-paper-200">{s}</span>
                    ))}
                    <span className="ml-auto font-mono text-paper-400">{timeAgo(pr.timestamp)}</span>
                  </div>
                </a>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
