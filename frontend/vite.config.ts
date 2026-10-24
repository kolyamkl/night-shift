import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// VEIL_API points /api somewhere else, for example the mock stream (npm run dev:mock).
export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: { "/api": loadEnv(mode, ".", "VEIL_").VEIL_API || "http://127.0.0.1:8000" },
  },
}));
