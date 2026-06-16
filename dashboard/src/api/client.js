// API layer for the DocPilot dashboard.
// Talks to the FastAPI bridge; falls back to representative sample data when the
// backend is unreachable so the UI is always demonstrable.

const BASE = "";

async function req(path, options) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export const api = {
  health: () => req("/api/health"),
  overview: () => req("/api/overview"),
  staleness: () => req("/api/staleness"),
  prs: () => req("/api/prs"),
  mapping: () => req("/api/mapping"),
  getConfig: () => req("/api/config"),
  updateConfig: (body) => req("/api/config", { method: "PUT", body: JSON.stringify(body) }),
  demos: () => req("/api/demos"),
  runDemo: (name) => req(`/api/demos/${name}`, { method: "POST" }),
  checkPaste: (body) => req("/api/check/paste", { method: "POST", body: JSON.stringify(body) }),
  checkGithub: (body) => req("/api/check/github", { method: "POST", body: JSON.stringify(body) }),
};

// ---- offline fallback samples ------------------------------------------------

export const SAMPLE = {
  overview: {
    stats: { docs_monitored: 47, stale_detected: 4, auto_fixes: 3, prs_generated: 4 },
    health: "amber",
    activity: [
      { id: 1, type: "auto_fixed", title: "verify_token parameter renamed", detail: "Docs referenced parameter 'user_id' that was renamed to 'account_id'.", timestamp: new Date(Date.now() - 3.6e6).toISOString() },
      { id: 2, type: "auto_fixed", title: "REQUEST_TIMEOUT default changed", detail: "Docs stated old default 30; code now uses 60.", timestamp: new Date(Date.now() - 7.2e6).toISOString() },
      { id: 3, type: "auto_fixed", title: "/legacy/stats endpoint removed", detail: "Docs still describe the removed endpoint /legacy/stats.", timestamp: new Date(Date.now() - 1.08e7).toISOString() },
      { id: 4, type: "drafted", title: "REDIS_URL added without docs", detail: "New configuration variable REDIS_URL is not documented.", timestamp: new Date(Date.now() - 1.44e7).toISOString() },
    ],
  },
  staleness: {
    findings: [
      { id: 1, title: "verify_token parameter renamed", file: "src/auth.py", heading: "Authentication > Token Verification", change_type: "api_signature", is_stale: true, confidence: "high", diagnosis: "Documentation references parameter(s) ['user_id'] that were renamed or removed (new params: ['account_id']).", action: "auto_fix", validation_passed: true, status: "auto_fixed", original: "Call `verify_token(token, user_id)` to validate a JWT. The `user_id` argument must match the subject encoded in the token.", corrected: "Call `verify_token(token, account_id)` to validate a JWT. The `account_id` argument must match the subject encoded in the token.", timestamp: new Date(Date.now() - 3.6e6).toISOString() },
      { id: 2, title: "REQUEST_TIMEOUT default changed", file: "src/config.py", heading: "Configuration > Timeouts", change_type: "config_change", is_stale: true, confidence: "high", diagnosis: "Documentation states old default value(s) ['30']; the code now uses ['60'].", action: "auto_fix", validation_passed: true, status: "auto_fixed", original: "The `REQUEST_TIMEOUT` setting defaults to 30 seconds.", corrected: "The `REQUEST_TIMEOUT` setting defaults to 60 seconds.", timestamp: new Date(Date.now() - 7.2e6).toISOString() },
      { id: 3, title: "/legacy/stats endpoint removed", file: "src/api.py", heading: "API > Legacy Stats", change_type: "feature_removed", is_stale: true, confidence: "high", diagnosis: "Documentation still describes the endpoint `/legacy/stats`, which was removed.", action: "auto_fix", validation_passed: true, status: "auto_fixed", original: "Send a `GET /legacy/stats` request to retrieve legacy statistics.", corrected: "<!-- DOCPILOT: REVIEW NEEDED -->\n> Note: `legacy_stats` was removed. This documentation is now obsolete.\n\nSend a `GET /legacy/stats` request to retrieve legacy statistics.", timestamp: new Date(Date.now() - 1.08e7).toISOString() },
      { id: 4, title: "REDIS_URL added without docs", file: "src/config.py", heading: "Configuration > Environment Variables", change_type: "feature_added", is_stale: true, confidence: "medium", diagnosis: "New configuration variable `REDIS_URL` is not documented in this section.", action: "draft_fix", validation_passed: true, status: "drafted", original: "Set `DATABASE_URL` to point DocPilot at your Postgres instance.", corrected: "<!-- DOCPILOT: REVIEW NEEDED -->\nSet `DATABASE_URL` to point DocPilot at your Postgres instance.\n\n- `REDIS_URL` — _(newly added; document its purpose and default here)._", timestamp: new Date(Date.now() - 1.44e7).toISOString() },
    ],
  },
  prs: {
    prs: [
      { id: 1, number: 101, title: "docs: fix 'Authentication > Token Verification'", sections: ["Authentication > Token Verification"], confidence: "high", action: "auto_fix", merge_status: "merged", url: "#", timestamp: new Date(Date.now() - 3.6e6).toISOString() },
      { id: 2, number: 102, title: "docs: fix 'Configuration > Timeouts'", sections: ["Configuration > Timeouts"], confidence: "high", action: "auto_fix", merge_status: "merged", url: "#", timestamp: new Date(Date.now() - 7.2e6).toISOString() },
      { id: 3, number: 103, title: "docs: fix 'API > Legacy Stats'", sections: ["API > Legacy Stats"], confidence: "high", action: "auto_fix", merge_status: "open", url: "#", timestamp: new Date(Date.now() - 1.08e7).toISOString() },
      { id: 4, number: 104, title: "docs: fix 'Configuration > Environment Variables'", sections: ["Configuration > Environment Variables"], confidence: "medium", action: "draft_fix", merge_status: "open", url: "#", timestamp: new Date(Date.now() - 1.44e7).toISOString() },
    ],
  },
  config: {
    confidence_threshold: 0.75, similarity_threshold: 0.78, auto_merge: false,
    llm_provider: "openai", embedding_model: "text-embedding-3-small",
    doc_paths: ["docs", "README.md"], code_paths: ["src", "lib"],
  },
};

// Wrap a call so it falls back to a sample on failure.
export async function withFallback(fn, sample) {
  try {
    return await fn();
  } catch (e) {
    console.warn("API unreachable, using sample data:", e.message);
    return sample;
  }
}
