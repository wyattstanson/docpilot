import React, { useEffect, useState } from "react";
import { Save, RotateCcw, Settings } from "lucide-react";
import { api, SAMPLE, withFallback } from "../api/client.js";
import { SectionHeader, Skeleton } from "../components/ui.jsx";
import { useToast } from "../hooks/useToast.jsx";

export default function Configuration() {
  const toast = useToast();
  const [cfg, setCfg] = useState(null);
  const [initial, setInitial] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    withFallback(api.getConfig, SAMPLE.config).then((c) => {
      setCfg(c);
      setInitial(c);
    });
  }, []);

  if (!cfg) {
    return (
      <div className="animate-fade-in">
        <SectionHeader title="Configuration" subtitle="Tune DocPilot's behavior." />
        <Skeleton className="h-80 w-full max-w-2xl" />
      </div>
    );
  }

  const set = (k, v) => setCfg({ ...cfg, [k]: v });

  async function save() {
    setSaving(true);
    try {
      const updated = await api.updateConfig({
        confidence_threshold: Number(cfg.confidence_threshold),
        similarity_threshold: Number(cfg.similarity_threshold),
        auto_merge: cfg.auto_merge,
        llm_provider: cfg.llm_provider,
      });
      setCfg((c) => ({ ...c, ...updated }));
      setInitial((c) => ({ ...c, ...updated }));
      toast("Configuration saved", "success");
    } catch (e) {
      toast("Saved locally (backend unreachable)", "info");
      setInitial(cfg);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="animate-fade-in">
      <SectionHeader title="Configuration" subtitle="Tune DocPilot's confidence routing, linking, and providers." />

      <div className="glass max-w-2xl p-6">
        <div className="space-y-7">
          <Slider
            label="Confidence threshold"
            hint="Minimum confidence required to act on a finding."
            value={cfg.confidence_threshold}
            onChange={(v) => set("confidence_threshold", v)}
          />
          <Slider
            label="Similarity threshold"
            hint="Cosine similarity cutoff for embedding-based links."
            value={cfg.similarity_threshold}
            onChange={(v) => set("similarity_threshold", v)}
          />

          <Toggle
            label="Auto-merge high-confidence fixes"
            hint="Merge fix PRs automatically when confidence is high."
            value={!!cfg.auto_merge}
            onChange={(v) => set("auto_merge", v)}
          />

          <div>
            <label className="mb-2 block text-sm font-medium text-paper-200">LLM Provider</label>
            <div className="flex gap-2">
              {["openai", "anthropic", "mock"].map((p) => (
                <button
                  key={p}
                  onClick={() => set("llm_provider", p)}
                  className={`flex-1 rounded-xl border px-4 py-2.5 text-sm font-medium capitalize transition ${
                    cfg.llm_provider === p
                      ? "border-violet-glow/40 bg-violet-glow/15 text-paper-50 shadow-glow"
                      : "border-paper-50/10 bg-paper-50/[0.02] text-paper-400 hover:text-paper-50"
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          <ReadOnly label="Watched code paths" value={(cfg.code_paths || []).join(", ")} />
          <ReadOnly label="Watched doc paths" value={(cfg.doc_paths || []).join(", ")} />

          <div className="flex gap-3 border-t border-paper-50/5 pt-5">
            <button className="btn-primary" onClick={save} disabled={saving}>
              <Save size={16} /> {saving ? "Saving…" : "Save changes"}
            </button>
            <button className="btn-ghost" onClick={() => setCfg(initial)}>
              <RotateCcw size={16} /> Reset
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Slider({ label, hint, value, onChange }) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <div>
          <label className="text-sm font-medium text-paper-200">{label}</label>
          <p className="text-xs text-paper-400">{hint}</p>
        </div>
        <span className="stat-num rounded-lg bg-violet-glow/15 px-2.5 py-1 text-sm text-violet-soft">
          {Number(value).toFixed(2)}
        </span>
      </div>
      <input
        type="range"
        min="0"
        max="1"
        step="0.01"
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full accent-violet-glow"
      />
    </div>
  );
}

function Toggle({ label, hint, value, onChange }) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <label className="text-sm font-medium text-paper-200">{label}</label>
        <p className="text-xs text-paper-400">{hint}</p>
      </div>
      <button
        onClick={() => onChange(!value)}
        className={`relative h-6 w-11 rounded-full transition ${value ? "bg-violet-glow shadow-glow" : "bg-paper-50/10"}`}
      >
        <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-paper-50 transition-all duration-200 ease-guide ${value ? "left-[22px]" : "left-0.5"}`} />
      </button>
    </div>
  );
}

function ReadOnly({ label, value }) {
  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-paper-200">{label}</label>
      <div className="rounded-xl border border-paper-50/5 bg-paper-50/[0.02] px-3.5 py-2.5 font-mono text-xs text-paper-400">
        {value || "—"}
      </div>
    </div>
  );
}
