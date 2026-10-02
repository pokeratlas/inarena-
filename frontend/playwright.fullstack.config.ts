import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e-fullstack",
  timeout: 45_000,
  use: {
    baseURL: "http://127.0.0.1:4174",
    trace: "retain-on-failure",
  },
  webServer: {
    command:
      "VITE_API_BASE=http://127.0.0.1:8000 npm run dev -- --host 127.0.0.1 --port 4174",
    url: "http://127.0.0.1:4174",
    reuseExistingServer: !process.env.CI,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
