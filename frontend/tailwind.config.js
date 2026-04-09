/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Fraunces"', "serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
        sans: ['"Inter"', "system-ui", "sans-serif"],
      },
      colors: {
        // Ink scale: inverted for light mode.
        // 950 = darkest text ink, 100 = near-cream surface.
        // Names unchanged so existing components keep working.
        ink: {
          950: "#1a1a1a",   // primary text
          900: "#2d2d2d",   // strong text
          800: "#4a4a4a",   // secondary text
          700: "#6b6b6b",   // tertiary / labels
          600: "#8a8a8a",   // muted
          500: "#a8a8a8",   // placeholder
          400: "#c4c4c4",   // hairline / subtle border
          300: "#d9d3c5",   // warm border
          200: "#ebe4d2",   // card surface
          100: "#f4ede0",   // soft surface
        },
        // Cream base — the app background. One extra step lighter for max warmth.
        cream: {
          50:  "#FDFBF6",   // lightest
          100: "#FAF6EF",   // primary background
          200: "#F4EEDF",   // elevated surface
          300: "#EBE2CC",   // raised
        },
        // Amber was the old accent; now it's CORAL. Kept the name so components
        // using `bg-amber-400` / `text-amber-500` automatically get coral.
        amber: {
          400: "#FF7A5E",   // hover/lighter coral
          500: "#FF5A3C",   // primary coral — the HERO color
          600: "#E63E20",   // pressed/darker coral
        },
        // True coral name, for places I want to be explicit.
        coral: {
          300: "#FFB5A3",
          400: "#FF7A5E",
          500: "#FF5A3C",
          600: "#E63E20",
          700: "#B82E17",
        },
        // Sage stays green (the "calm/good" state) but shifted for cream contrast.
        sage: {
          400: "#4FA77C",
          500: "#2F8559",
          600: "#1F6842",
        },
        // Rose stays red (the "alert/bad" state) but deeper for cream contrast.
        rose: {
          400: "#E84B5B",
          500: "#C92E3E",
          600: "#A31F2D",
        },
        // Accent color for the "unknown/neutral" state in the graph.
        honey: {
          400: "#F5B947",
          500: "#E89C20",
        },
      },
      boxShadow: {
        // Custom chunky shadows with coral tint — the Gen Z "pop"
        pop: "4px 4px 0 0 #1a1a1a",
        "pop-sm": "2px 2px 0 0 #1a1a1a",
        "pop-coral": "4px 4px 0 0 #FF5A3C",
        soft: "0 2px 8px rgba(26, 26, 26, 0.06)",
        raised: "0 4px 16px rgba(26, 26, 26, 0.08)",
      },
      keyframes: {
        pulseRing: {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(255, 90, 60, 0.5)" },
          "50%": { boxShadow: "0 0 0 10px rgba(255, 90, 60, 0)" },
        },
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        wiggle: {
          "0%, 100%": { transform: "rotate(-1deg)" },
          "50%": { transform: "rotate(1deg)" },
        },
      },
      animation: {
        pulseRing: "pulseRing 2s ease-in-out infinite",
        fadeUp: "fadeUp 0.3s ease-out",
        wiggle: "wiggle 0.5s ease-in-out",
      },
    },
  },
  plugins: [],
};
