/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Warm near-black "ledger" surfaces (no blue-black neon).
        ink: {
          900: "#100f0d",
          850: "#15130f",
          800: "#1a1713",
          700: "#221d17",
          600: "#2b2419",
          500: "#3a3124",
        },
        // Warm paper text tones.
        paper: {
          50: "#f4eee0",
          100: "#ede6d5",
          200: "#d8cfba",
          400: "#9a9080",
          600: "#6e6657",
        },
        // Primary accent: clay / vermillion. Secondary: sand / gold.
        clay: { DEFAULT: "#d9542f", soft: "#e2683f", deep: "#b23f20" },
        sand: { DEFAULT: "#d8b26a", soft: "#e2c282" },
        sage: { DEFAULT: "#8a9a5b", soft: "#a3b274" },
        // Aliases so legacy utility classes keep resolving to the new palette.
        violet: { glow: "#d9542f", soft: "#e2683f" },
        cyan: { glow: "#d8b26a" },
      },
      fontFamily: {
        // Editorial masthead serif, grotesque UI, monospace metrics.
        serif: ['"Fraunces"', "Georgia", "serif"],
        sans: ['"Archivo"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      letterSpacing: {
        label: "0.14em",
      },
      boxShadow: {
        // Flat, printed-card shadows. No glow.
        glow: "0 1px 0 rgba(0,0,0,0.5), 0 14px 34px -22px rgba(0,0,0,0.9)",
        "glow-cyan": "0 1px 0 rgba(0,0,0,0.5), 0 14px 34px -22px rgba(0,0,0,0.9)",
        card: "0 1px 0 rgba(0,0,0,0.45), 0 18px 40px -28px rgba(0,0,0,0.85)",
        stamp: "inset 0 0 0 1px rgba(244,238,224,0.10)",
      },
      transitionTimingFunction: {
        // Guiding easings used across page + element transitions.
        guide: "cubic-bezier(0.22, 1, 0.36, 1)",
        smooth: "cubic-bezier(0.65, 0, 0.35, 1)",
        entrance: "cubic-bezier(0.16, 1, 0.3, 1)",
      },
      keyframes: {
        breathe: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.55" },
        },
        "page-in": {
          "0%": { opacity: "0", transform: "translateY(14px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "slide-in": {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "rule-draw": {
          "0%": { transform: "scaleX(0)" },
          "100%": { transform: "scaleX(1)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-468px 0" },
          "100%": { backgroundPosition: "468px 0" },
        },
      },
      animation: {
        breathe: "breathe 3.2s ease-in-out infinite",
        "page-in": "page-in 0.5s cubic-bezier(0.16, 1, 0.3, 1) both",
        "slide-in": "slide-in 0.45s cubic-bezier(0.22, 1, 0.36, 1) both",
        "fade-in": "fade-in 0.5s ease-out both",
        "rule-draw": "rule-draw 0.6s cubic-bezier(0.22, 1, 0.36, 1) both",
        shimmer: "shimmer 1.5s linear infinite",
      },
    },
  },
  plugins: [],
};
