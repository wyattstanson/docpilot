import React, { useEffect, useMemo, useState } from "react";
import { Network, Code2, FileText } from "lucide-react";
import { api } from "../api/client.js";
import { SectionHeader, Skeleton, EmptyState } from "../components/ui.jsx";

const KIND_COLOR = {
  function: "#d9542f",
  method: "#e2683f",
  class: "#b23f20",
  api_route: "#d8b26a",
  config: "#8a9a5b",
  cli_command: "#a3b274",
};

export default function RepositoryMap() {
  const [graph, setGraph] = useState(null);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    api
      .mapping()
      .then(setGraph)
      .catch(() => setGraph({ code_chunks: [], doc_sections: [], links: [] }));
  }, []);

  const linkedSections = useMemo(() => {
    if (!graph || !selected) return new Set();
    return new Set(
      graph.links.filter((l) => l.code_chunk_id === selected).map((l) => l.doc_section_id)
    );
  }, [graph, selected]);

  const linkedChunks = useMemo(() => {
    if (!graph || !selected) return new Set();
    return new Set(
      graph.links.filter((l) => l.doc_section_id === selected).map((l) => l.code_chunk_id)
    );
  }, [graph, selected]);

  if (!graph) {
    return (
      <div className="animate-fade-in">
        <SectionHeader title="Repository Map" subtitle="Code-to-docs link graph." />
        <div className="grid grid-cols-2 gap-6">
          <Skeleton className="h-96" />
          <Skeleton className="h-96" />
        </div>
      </div>
    );
  }

  const chunks = graph.code_chunks.slice(0, 40);
  const sections = graph.doc_sections.slice(0, 40);

  const isHi = (id) => selected === id || linkedSections.has(id) || linkedChunks.has(id);
  const dim = (id) => selected && !isHi(id);

  return (
    <div className="animate-fade-in">
      <SectionHeader
        title="Repository Map"
        subtitle="Click a code chunk or doc section to trace its links. Color-coded by kind."
      >
        <div className="glass flex items-center gap-2 px-3.5 py-2 text-xs text-paper-400">
          <Network size={14} className="text-violet-soft" />
          {graph.code_chunks.length} chunks · {graph.doc_sections.length} sections · {graph.links.length} links
        </div>
      </SectionHeader>

      {chunks.length === 0 ? (
        <EmptyState icon={Network} title="No mapping yet" hint="Run `docpilot build` to generate the link graph." />
      ) : (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <Column
            title="Code"
            icon={Code2}
            items={chunks.map((c) => ({
              id: c.chunk_id,
              label: c.symbol,
              sub: c.file_path,
              color: KIND_COLOR[c.kind] || "#8b5cf6",
              kind: c.kind,
            }))}
            selected={selected}
            isHi={isHi}
            dim={dim}
            onSelect={setSelected}
          />
          <Column
            title="Documentation"
            icon={FileText}
            items={sections.map((s) => ({
              id: s.section_id,
              label: s.heading_path,
              sub: s.file_path,
              color: "#d8b26a",
            }))}
            selected={selected}
            isHi={isHi}
            dim={dim}
            onSelect={setSelected}
          />
        </div>
      )}
    </div>
  );
}

function Column({ title, icon: Icon, items, isHi, dim, onSelect }) {
  return (
    <div className="glass p-4">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-paper-200">
        <Icon size={16} className="text-violet-soft" /> {title}
        <span className="ml-auto font-mono text-xs text-paper-400">{items.length}</span>
      </div>
      <div className="flex max-h-[70vh] flex-col gap-1.5 overflow-auto pr-1">
        {items.map((it) => (
          <button
            key={it.id}
            onClick={() => onSelect(it.id)}
            className={`group flex items-center gap-3 rounded-lg border px-3 py-2 text-left transition-all duration-200 ${
              isHi(it.id)
                ? "border-violet-glow/40 bg-violet-glow/10"
                : "border-paper-50/5 bg-paper-50/[0.02] hover:border-paper-50/10 hover:bg-paper-50/[0.04]"
            } ${dim(it.id) ? "opacity-30" : "opacity-100"}`}
          >
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: it.color }} />
            <span className="min-w-0">
              <span className="block truncate font-mono text-[13px] text-paper-100">{it.label}</span>
              <span className="block truncate text-[11px] text-paper-400">{it.sub}</span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
