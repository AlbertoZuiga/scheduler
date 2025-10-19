/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: [
    "./app/templates/**/*.html",
    "./app/static/js/**/*.js",
    "./app/static/**/*.css",
    "./app/components/**/*.html",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#6366f1",
          light: "#818cf8",
          dark: "#4f46e5",
        },
        accent: {
          DEFAULT: "#a78bfa",
          light: "#c4b5fd",
          dark: "#7c3aed",
        },

        "light-background": "#ffffff",
        "light-surface": "#f9fafb",
        "light-card": "#f3f4f6",
        "light-border": "#d1d5db",
        "light-muted": "#e5e7eb",
        "light-text-primary": "#111827",
        "light-text-secondary": "#374151",
        "light-text-muted": "#6b7280",

        "dark-background": "#0f0f0f",
        "dark-surface": "#18181b",
        "dark-card": "#1f1f23",
        "dark-border": "#27272a",
        "dark-muted": "#3f3f46",
        "dark-text-primary": "#f5f5f5",
        "dark-text-secondary": "#a1a1aa",
        "dark-text-muted": "#71717a",

        success: {
          DEFAULT: "#22c55e",
          light: "#4ade80",
          dark: "#16a34a",
        },
        warning: {
          DEFAULT: "#facc15",
          light: "#fde047",
          dark: "#ca8a04",
        },
        error: {
          DEFAULT: "#ef4444",
          light: "#f87171",
          dark: "#dc2626",
        },
        info: {
          DEFAULT: "#0ea5e9",
          light: "#38bdf8",
          dark: "#0284c7",
        },
      },

      fontFamily: {
        sans: [
          "Inter",
          "system-ui",
          "Avenir",
          "Helvetica",
          "Arial",
          "sans-serif",
        ],
        mono: ["Fira Code", "monospace"],
      },

      spacing: {
        128: "32rem",
        144: "36rem",
      },


      boxShadow: {
        card: "0 2px 6px rgba(0,0,0,0.1)",
        "card-dark": "0 2px 6px rgba(255,255,255,0.05)",
      },


      transitionProperty: {
        theme: "background-color, border-color, color, fill, stroke",
      },
    },
  },
  plugins: [
    require("@tailwindcss/forms"),
    require("@tailwindcss/typography"),
  ],
};
