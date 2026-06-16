import React, { useEffect, useState } from "react";
import { FileText, AlertTriangle, Wand2, GitPullRequest, Activity } from "lucide-react";
import { api, SAMPLE, withFallback } from "../api/client.js";
import { StatCard, SectionHeader, Skeleton } from "../components/ui.jsx";
import { StatusBadge } from "../components/ui.jsx";
import HealthOrb from "../components/HealthOrb.jsx";
import { timeAgo } from "../lib/format.js";

export default function Overview() {
  const [data, setData] = useState(null);

  useEffect(() => {
    withFallback(api.overview, SAMPLE.overview).then(setData);
  }, []);

  const stats = data?.stats;
  const loading = !data;

  return (
    <div className="animate-fade-in">
      <SectionHeader
        title="Overview"
        subtitle="Live monitoring of documentation health across the repository."
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard icon={FileText} label="Docs Monitored" value={stats?.docs_monitored} loading={loading} />
        <StatCard icon={AlertTriangle} label="Stale Detected" value={stats?.stale_detected} accent="cyan" loading={loading} />
        <StatCard icon={Wand2} label="Auto-Fixes Applied" value={stats?.auto_fixes} loading={loading} />
        <StatCard icon={GitPullRequest} label="PRs Generated" value={stats?.prs_generated} accent="cyan" loading={loading} />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-paper-200">
            <Activity size={16} className="text-violet-soft" /> Recent Activity
          </div>
          <div className="flex flex-col gap-3">
            {loading
              ? [0, 1, 2].map((i) => <Skeleton key={i} className="h-20 w-full" />)
              : data.activity.map((e, i) => (
                  <div
                    key={e.id}
                    style={{ animationDelay: `${i * 60}ms` }}
                    className="glass glass-hover animate-slide-in flex items-start justify-between gap-4 p-4"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2.5">
                        <StatusBadge value={e.type} />
                        <p className="truncate font-medium text-paper-50">{e.title}</p>
                      </div>
                      <p className="mt-1.5 line-clamp-2 text-sm text-paper-400">{e.detail}</p>
                    </div>
                    <span className="shrink-0 font-mono text-xs text-paper-400">{timeAgo(e.timestamp)}</span>
                  </div>
                ))}
          </div>
        </div>

        <div className="flex flex-col gap-4">
          <HealthOrb status={data?.health || "green"} />
          <div className="glass p-5">
            <p className="text-xs uppercase tracking-wider text-paper-400">Pipeline</p>
            <ul className="mt-3 space-y-2.5 text-sm">
              {[
                ["Parse code + docs", "violet"],
                ["Embed + link graph", "cyan"],
                ["Diff + staleness check", "violet"],
                ["Repair + validate", "cyan"],
              ].map(([label, tone]) => (
                <li key={label} className="flex items-center gap-2.5 text-paper-200">
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${tone === "cyan" ? "bg-cyan-glow" : "bg-violet-soft"}`}
                  />
                  {label}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
