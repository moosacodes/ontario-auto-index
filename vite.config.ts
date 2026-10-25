import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Relative asset URLs work at / locally and under /<repository>/ on GitHub Pages.
  base: "./",
  build: { outDir: "dist" },
});
