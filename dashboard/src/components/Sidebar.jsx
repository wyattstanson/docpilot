import React from "react";
import {
  LayoutDashboard,
  Network,
  FileWarning,
  GitPullRequest,
  Settings,
  TerminalSquare,
} from "lucide-react";
import Logo from "./Logo.jsx";

export const NAV = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "map", label: "Repository Map", icon: Network },
  { id: "staleness", label: "Staleness Report", icon: FileWarning },
  { id: "prs", label: "PR Activity", icon: GitPullRequest },
  { id: "console", label: "Live Console", icon: TerminalSquare },
  { id: "config", label: "Configuration", icon: Settings },
];

export default function Sidebar({ active, onChange, health }) {
  const dot =
    health === "red" ? "bg-clay" : health === "amber" ? "bg-sand" : "bg-sage";
  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-paper-50/[0.07] bg-ink-850/70 px-4 py-6">
      <div className="mb-9 flex items-center gap-3 px-1">
        <Logo size={42} />
        <div>
          <p className="font-serif text-xl font-semibold leading-none tracking-tight text-paper-50">
            DocPilot
          </p>
          <p className="mt-1.5 text-[10px] font-semibold uppercase tracking-label text-paper-400">
            self-healing docs
          </p>
        </div>
      </div>

      <div className="rule mb-5 animate-rule-draw" />

      <nav className="flex flex-1 flex-col gap-1" role="navigation">
        {NAV.map((item) => {
          const Icon = item.icon;
          const isActive = active === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onChange(item.id)}
              aria-current={isActive ? "page" : undefined}
              className={`nav-item ${isActive ? "nav-item-active" : ""}`}
            >
              <Icon size={16} strokeWidth={2} />
              {item.label}
            </button>
          );
        })}
      </nav>

      <div className="rule my-5" />

      <div className="flex items-center gap-2.5 px-1.5">
        <span className={`h-1.5 w-1.5 rounded-full ${dot} animate-breathe`} />
        <span className="text-[10px] font-semibold uppercase tracking-label text-paper-400">
          Engine connected
        </span>
      </div>
    </aside>
  );
}
