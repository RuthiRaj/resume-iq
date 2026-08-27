import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        page: "#F6F7F9",
        surface: "#FFFFFF",
        border: "#E4E7EC",
        primary: {
          DEFAULT: "#101828",
          foreground: "#FFFFFF",
        },
        secondary: {
          DEFAULT: "#667085",
          foreground: "#101828",
        },
        muted: {
          DEFAULT: "#98A2B3",
          foreground: "#667085",
        },
        accent: {
          DEFAULT: "#3652D9",
          foreground: "#FFFFFF",
          soft: "#EEF1FD",
        },
        status: {
          success: "#12805C",
          "success-soft": "#E7F5EF",
          warning: "#B54708",
          "warning-soft": "#FFF6ED",
          error: "#B42318",
          "error-soft": "#FEF3F2",
        },
      },
      fontSize: {
        display: ["32px", { lineHeight: "40px", fontWeight: "600" }],
        h1: ["23px", { lineHeight: "32px", fontWeight: "600" }],
        h2: ["15px", { lineHeight: "22px", fontWeight: "600" }],
        body: ["13.5px", { lineHeight: "20px", fontWeight: "400" }],
        small: ["12.5px", { lineHeight: "18px", fontWeight: "400" }],
        caption: [
          "11.5px",
          {
            lineHeight: "16px",
            fontWeight: "600",
            letterSpacing: "0.4px",
          },
        ],
      },
      borderRadius: {
        card: "10px",
        btn: "6px",
        input: "6px",
        modal: "10px",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "-apple-system", "sans-serif"],
      },
      boxShadow: {
        subtle: "0 1px 2px 0 rgba(16, 24, 40, 0.05)",
        card: "none",
        dropdown: "0 4px 12px rgba(16, 24, 40, 0.08)",
      },
    },
  },
  plugins: [],
};

export default config;
