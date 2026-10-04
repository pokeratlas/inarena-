import { defineConfig, devices } from "@playwright/test";
import fullstack from "./playwright.fullstack.config";

export default defineConfig({
  ...fullstack,
  // Shared local backend: predictable order and no concurrent cash fixtures.
  workers: 1,
  forbidOnly: true,
  retries: 1,
  outputDir: "guardian-results/artifacts",
  reporter: [
    ["list"],
    ["json", { outputFile: "guardian-results/playwright.json" }],
    ["html", { outputFolder: "guardian-report", open: "never" }],
  ],
  use: {
    ...fullstack.use,
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    { name: "guardian-desktop", use: { ...devices["Desktop Chrome"] } },
    {
      name: "guardian-mobile",
      use: { ...devices["iPhone 13"], defaultBrowserType: "chromium" },
      grep: /@guardian-(join|owner-create|owner-live|owner-lifecycle|table-chat|return|owner-credit|network-recovery|table-v2|table-utilities)/,
    },
  ],
});
