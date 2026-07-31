import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: "#1a3c6e",
        accent: "#0d8a5e",
        danger: "#c0392b",
      },
    },
  },
  plugins: [],
};

export default config;
