import React from "react";

// A drawn compass-rose mark — nods to "pilot / guiding", no emoji, no icon font.
// The needle's north half is clay, south half is paper; a hairline seal frames it.
export default function Logo({ size = 40 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="DocPilot"
    >
      <rect x="1.25" y="1.25" width="37.5" height="37.5" rx="9" fill="#15130f" />
      <rect
        x="1.25"
        y="1.25"
        width="37.5"
        height="37.5"
        rx="9"
        stroke="#d9542f"
        strokeOpacity="0.55"
        strokeWidth="1.5"
      />
      {/* compass needle */}
      <path d="M20 7 L24 20 L20 20 Z" fill="#e2683f" />
      <path d="M20 7 L16 20 L20 20 Z" fill="#b23f20" />
      <path d="M20 33 L16 20 L20 20 Z" fill="#ede6d5" />
      <path d="M20 33 L24 20 L20 20 Z" fill="#9a9080" />
      {/* hub */}
      <circle cx="20" cy="20" r="2.4" fill="#15130f" stroke="#ede6d5" strokeWidth="1.1" />
      {/* cardinal ticks */}
      <circle cx="20" cy="5.5" r="0.9" fill="#d8b26a" />
    </svg>
  );
}
