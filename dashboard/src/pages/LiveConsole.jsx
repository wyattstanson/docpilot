import React, { useEffect, useState } from "react";
import { Play, Loader2, Sparkles, Github, ClipboardPaste, Wand2, FileSearch, Upload, CheckCircle2 } from "lucide-react";
import { api } from "../api/client.js";
import { SectionHeader, ConfidenceBadge, StatusBadge } from "../components/ui.jsx";
import DiffViewer from "../components/DiffViewer.jsx";
import { useToast } from "../hooks/useToast.jsx";
import { CHANGE_TYPE } from "../lib/format.js";

const MODES = [
  { id: "demo", label: "Demo", icon: Sparkles },
  { id: "audit", label: "Audit", icon: FileSearch },
  { id: "paste", label: "Paste", icon: ClipboardPaste },
  { id: "github", label: "GitHub", icon: Github },
];

const DEFAULT_PASTE = {
  file_path: "src/auth.py",
  old_code: "def verify_token(token, user_id):\n    return _decode(token, user_id)\n",
  new_code: "def verify_token(token, account_id):\n    return _decode(token, account_id)\n",
  doc_heading: "Authentication > Token Verification",
  doc_content: "Call `verify_token(token, user_id)` to validate a JWT. The `user_id` argument must match the subject in the token.",
};

export default function LiveConsole() {
  const toast = useToast();
  const [mode, setMode] = useState("demo");
  const [running, setRunning] = useState(false);
  const [stage, setStage] = useState("");
  const [result, setResult] = useState(null);
  const [demos, setDemos] = useState([]);
  const [paste, setPaste] = useState(DEFAULT_PASTE);
  const [gh, setGh] = useState({ repo_url: "", pr_number: "" });
  const [audit, setAudit] = useState({ code: null, docs: null });

  useEffect(() => {
    api.demos().then((d) => setDemos(d.demos)).catch(() => setDemos([]));
  }, []);

  async function pipelineStages(fn) {
    setRunning(true);
    setResult(null);
    const stages = ["Parsing the diff…", "Querying the link graph…", "Checking with the LLM…", "Generating the correction…"];
    for (const s of stages) {
      setStage(s);
      await new Promise((r) => setTimeout(r, 280));
    }
    try {
      const res = await fn();
      setResult(res);
      const f = res.finding;
      if (f?.is_stale) toast(`Stale doc detected · ${f.confidence} confidence`, "warning");
      else toast("Documentation is accurate", "success");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setRunning(false);
      setStage("");
    }
  }

  const runDemo = (name) => pipelineStages(() => api.runDemo(name));
  const runPaste = () => pipelineStages(() => api.checkPaste(paste));
  const runGithub = () =>
    pipelineStages(() => api.checkGithub({ repo_url: gh.repo_url, pr_number: Number(gh.pr_number) }));

  async function runAudit() {
    setRunning(true);
    setResult(null);
    const stages = ["Reading the files…", "Parsing code + docs…", "Building the link graph…", "Auditing each section…"];
    for (const s of stages) {
      setStage(s);
      await new Promise((r) => setTimeout(r, 260));
    }
    try {
      const fd = new FormData();
      fd.append("code", audit.code);
      fd.append("docs", audit.docs);
      const res = await api.audit(fd);
      res._audit = true;
      setResult(res);
      if (res.auditable_sections === 0) toast("No overlap — these docs don't reference this code", "info");
      else if (res.inconsistent > 0) toast(`${res.inconsistent} inconsistent doc section(s)`, "warning");
      else toast("Docs match the code", "success");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setRunning(false);
      setStage("");
    }
  }

  return (
    <div className="animate-fade-in">
      <SectionHeader title="Live Testing Console" subtitle="Run the real DocPilot pipeline on a diff and a doc section — watch it think.">
        <div className="glass flex gap-1 p-1">
          {MODES.map((m) => {
            const Icon = m.icon;
            return (
              <button
                key={m.id}
                onClick={() => { setMode(m.id); setResult(null); }}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                  mode === m.id ? "bg-violet-glow text-paper-50 shadow-glow" : "text-paper-400 hover:text-paper-50"
                }`}
              >
                <Icon size={14} /> {m.label}
              </button>
            );
          })}
        </div>
      </SectionHeader>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* input */}
        <div className="glass p-5">
          {mode === "demo" && (
            <div className="flex flex-col gap-3">
              <p className="text-sm text-paper-400">Pre-loaded staleness patterns. Each runs the actual engine.</p>
              {demos.map((d) => (
                <button
                  key={d.name}
                  disabled={running}
                  onClick={() => runDemo(d.name)}
                  className="group flex items-center justify-between gap-3 rounded-xl border border-paper-50/5 bg-paper-50/[0.02] p-4 text-left transition hover:border-violet-glow/30 hover:bg-violet-glow/[0.06] disabled:opacity-50"
                >
                  <div>
                    <p className="font-mono text-sm font-medium text-paper-50">{d.name}</p>
                    <p className="mt-0.5 text-xs text-paper-400">{d.description}</p>
                  </div>
                  <Play size={16} className="shrink-0 text-violet-soft opacity-0 transition group-hover:opacity-100" />
                </button>
              ))}
            </div>
          )}

          {mode === "audit" && (
            <div className="flex flex-col gap-3">
              <p className="text-sm text-paper-400">
                Upload a code file and your docs (Markdown, text, or PDF). DocPilot audits
                whether the docs still match the code — no diff needed.
              </p>
              <FilePicker
                label="Code file"
                accept=".py,.js,.jsx,.ts,.tsx,.mjs,.cjs"
                file={audit.code}
                onPick={(f) => setAudit({ ...audit, code: f })}
              />
              <FilePicker
                label="Docs file (.md / .txt / .pdf)"
                accept=".md,.markdown,.txt,.pdf"
                file={audit.docs}
                onPick={(f) => setAudit({ ...audit, docs: f })}
              />
              <button className="btn-primary" disabled={running || !audit.code || !audit.docs} onClick={runAudit}>
                {running ? <Loader2 size={16} className="animate-spin" /> : <FileSearch size={16} />} Run audit
              </button>
            </div>
          )}

          {mode === "paste" && (
            <div className="flex flex-col gap-3">
              <Field label="File path">
                <input className="inp" value={paste.file_path} onChange={(e) => setPaste({ ...paste, file_path: e.target.value })} />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Old code">
                  <textarea className="inp font-mono h-28" value={paste.old_code} onChange={(e) => setPaste({ ...paste, old_code: e.target.value })} />
                </Field>
                <Field label="New code">
                  <textarea className="inp font-mono h-28" value={paste.new_code} onChange={(e) => setPaste({ ...paste, new_code: e.target.value })} />
                </Field>
              </div>
              <Field label="Doc heading">
                <input className="inp" value={paste.doc_heading} onChange={(e) => setPaste({ ...paste, doc_heading: e.target.value })} />
              </Field>
              <Field label="Doc section content">
                <textarea className="inp h-24" value={paste.doc_content} onChange={(e) => setPaste({ ...paste, doc_content: e.target.value })} />
              </Field>
              <button className="btn-primary" disabled={running} onClick={runPaste}>
                {running ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />} Run check
              </button>
            </div>
          )}

          {mode === "github" && (
            <div className="flex flex-col gap-3">
              <p className="text-sm text-paper-400">Fetch a real PR diff and run the pipeline. Requires a backend with network access.</p>
              <Field label="Repository URL">
                <input className="inp" placeholder="https://github.com/owner/repo" value={gh.repo_url} onChange={(e) => setGh({ ...gh, repo_url: e.target.value })} />
              </Field>
              <Field label="PR number">
                <input className="inp" placeholder="42" value={gh.pr_number} onChange={(e) => setGh({ ...gh, pr_number: e.target.value })} />
              </Field>
              <button className="btn-primary" disabled={running || !gh.repo_url} onClick={runGithub}>
                {running ? <Loader2 size={16} className="animate-spin" /> : <Github size={16} />} Analyze PR
              </button>
            </div>
          )}
        </div>

        {/* output */}
        <div className="glass min-h-[20rem] p-5">
          {running ? (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
              <Loader2 size={28} className="animate-spin text-violet-soft" />
              <p className="font-mono text-sm text-paper-200">{stage}</p>
            </div>
          ) : !result ? (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-center text-paper-400">
              <Wand2 size={28} />
              <p className="text-sm">Run a check to see the diagnosis and proposed fix.</p>
            </div>
          ) : result._audit ? (
            <AuditResult result={result} />
          ) : (
            <Result result={result} />
          )}
        </div>
      </div>

      <style>{`.inp{width:100%;border-radius:0.5rem;border:1px solid rgba(244,238,224,0.10);background:rgba(244,238,224,0.02);padding:0.6rem 0.8rem;font-size:0.8rem;color:#ede6d5;outline:none;resize:vertical;transition:border-color .2s cubic-bezier(.22,1,.36,1)}.inp:focus{border-color:rgba(217,84,47,0.6)}`}</style>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium text-paper-400">{label}</span>
      {children}
    </label>
  );
}

function FilePicker({ label, accept, file, onPick }) {
  return (
    <label className="block cursor-pointer">
      <span className="mb-1.5 block text-xs font-medium text-paper-400">{label}</span>
      <div
        className={`flex items-center gap-3 rounded-md border border-dashed px-4 py-3 transition ${
          file ? "border-sage/40 bg-sage/[0.05]" : "border-paper-50/15 bg-paper-50/[0.02] hover:border-clay/40"
        }`}
      >
        <Upload size={16} className={file ? "text-sage-soft" : "text-paper-400"} />
        <span className="truncate text-sm text-paper-200">
          {file ? file.name : "Choose a file…"}
        </span>
      </div>
      <input
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => onPick(e.target.files?.[0] || null)}
      />
    </label>
  );
}

function AuditResult({ result }) {
  const findings = result.findings || [];
  const noOverlap = (result.auditable_sections ?? 0) === 0;
  const clean = !noOverlap && result.inconsistent === 0;
  return (
    <div className="animate-fade-in flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`chip ${
            noOverlap
              ? "bg-sand/15 text-sand-soft border border-sand/40"
              : clean
                ? "bg-sage/15 text-sage-soft border border-sage/40"
                : "bg-clay/15 text-clay-soft border border-clay/40"
          }`}
        >
          {noOverlap ? "No overlap" : clean ? "Consistent" : `${result.inconsistent} inconsistent`}
        </span>
        <span className="chip bg-paper-50/5 text-paper-400 border border-paper-50/15">
          {result.auditable_sections ?? 0}/{result.sections_checked} auditable · {result.code_chunks} symbols · {result.links} links
        </span>
      </div>

      {noOverlap ? (
        <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
          <FileSearch size={28} className="text-sand-soft" />
          <p className="text-sm text-paper-200">
            These docs don't reference anything in this code, so there was nothing to audit.
          </p>
          <p className="max-w-xs text-xs text-paper-400">
            Upload a docs file that actually describes the uploaded code (mentions its functions,
            classes, config keys, or routes).
          </p>
        </div>
      ) : clean ? (
        <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
          <CheckCircle2 size={28} className="text-sage-soft" />
          <p className="text-sm text-paper-200">The documentation matches the current code.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {findings.map((f, i) => (
            <div key={i} className="rounded-md border border-paper-50/10 bg-paper-50/[0.02] p-4">
              <div className="mb-1.5 flex items-center gap-2">
                <span className="font-serif text-sm text-paper-50">{f.heading}</span>
                <ConfidenceBadge value={f.confidence} />
                <span className="chip bg-paper-50/5 text-paper-400 border border-paper-50/15">
                  {f.kind === "missing_symbol" ? "missing symbol" : "mismatch"}
                </span>
              </div>
              <p className="text-sm text-paper-200">{f.diagnosis}</p>
              {f.suggested_fix && (
                <pre className="mt-2 overflow-auto rounded-md border border-sage/25 bg-sage/[0.05] p-3 font-mono text-[12.5px] leading-relaxed text-sage-soft whitespace-pre-wrap">
                  {f.suggested_fix.trim()}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Result({ result }) {
  const f = result.finding;
  const c = result.correction;
  const changes = result.changes || [];

  if (!f) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
        <StatusBadge value="verified" />
        <p className="text-sm text-paper-200">{result.message || "No meaningful change detected."}</p>
        {changes.length > 0 && (
          <p className="font-mono text-xs text-paper-400">{changes.length} change(s) parsed</p>
        )}
      </div>
    );
  }

  return (
    <div className="animate-fade-in flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`chip ${f.is_stale ? "bg-clay/15 text-clay-soft border border-clay/40" : "bg-sage/15 text-sage-soft border border-sage/40"}`}>
          {f.is_stale ? "Stale" : "Accurate"}
        </span>
        <ConfidenceBadge value={f.confidence} />
        {c && <StatusBadge value={c.action === "auto_fix" ? "auto_fixed" : c.action === "draft_fix" ? "drafted" : "flagged"} />}
        {changes[0] && <span className="chip bg-paper-50/5 text-paper-400 border border-paper-50/15">{CHANGE_TYPE[changes[0].change_type] || changes[0].change_type}</span>}
      </div>

      <div className="rounded-md border border-sand/25 bg-sand/[0.05] px-4 py-3">
        <p className="text-[10px] font-semibold uppercase tracking-label text-sand-soft">Diagnosis</p>
        <p className="mt-1 text-sm text-paper-200">{f.diagnosis}</p>
      </div>

      {c && c.corrected_content && (
        <>
          <DiffViewer original={c.original_content} corrected={c.corrected_content} />
          {c.validation_passed != null && (
            <p className="text-xs text-paper-400">
              Validation gate:{" "}
              <span className={c.validation_passed ? "text-sage-soft" : "text-clay-soft"}>
                {c.validation_passed ? "Passed" : "Failed"}
              </span>{" "}
              — {c.validation_notes}
            </p>
          )}
        </>
      )}
    </div>
  );
}
