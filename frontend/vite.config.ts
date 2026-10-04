import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // Playwright writes HTML trace resources; these are not application edits.
    watch: { ignored: ["**/guardian-results/**", "**/guardian-report/**", "**/test-results/**", "**/playwright-report/**"] },
  },
});
