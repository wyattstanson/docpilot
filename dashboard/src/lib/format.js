export function timeAgo(iso) {
  const then = new Date(iso).getTime();
  const secs = Math.max(1, Math.floor((Date.now() - then) / 1000));
  const units = [
    ["d", 86400],
    ["h", 3600],
    ["m", 60],
    ["s", 1],
  ];
  for (const [label, size] of units) {
    if (secs >= size) return `${Math.floor(secs / size)}${label} ago`;
  }
  return "just now";
}

// Editorial badge palette — clay / sand / sage / ink with hairline borders.
export const CONFIDENCE = {
  high: { label: "High", cls: "bg-sage/15 text-sage-soft border border-sage/40" },
  medium: { label: "Medium", cls: "bg-sand/15 text-sand-soft border border-sand/40" },
  low: { label: "Low", cls: "bg-paper-50/10 text-paper-400 border border-paper-50/20" },
};

export const STATUS = {
  auto_fixed: { label: "Auto-fixed", cls: "bg-clay/15 text-clay-soft border border-clay/40" },
  drafted: { label: "Drafted", cls: "bg-sand/15 text-sand-soft border border-sand/40" },
  flagged: { label: "Flagged", cls: "bg-sand/15 text-sand-soft border border-sand/40" },
  verified: { label: "Verified", cls: "bg-sage/15 text-sage-soft border border-sage/40" },
  pending: { label: "Pending", cls: "bg-paper-50/10 text-paper-400 border border-paper-50/20" },
  live: { label: "Live", cls: "bg-clay/15 text-clay-soft border border-clay/40" },
};

export const CHANGE_TYPE = {
  api_signature: "Signature change",
  config_change: "Config change",
  feature_added: "Feature added",
  feature_removed: "Feature removed",
  behavior_change: "Behavior change",
  none: "—",
};
