import { expect, test, type Locator, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";

const budgets: Record<string, Record<string, number>> = JSON.parse(
  readFileSync(new URL("./guardian-budgets.json", import.meta.url), "utf8"),
);

export async function measureJourney(
  journey: keyof typeof budgets,
  metric: string,
  action: () => Promise<void>,
) {
  const budgetMs = (budgets[journey] as Record<string, number>)[metric];
  if (!budgetMs) throw new Error(`Unknown Guardian budget: ${journey}/${metric}`);
  const started = performance.now();
  await action();
  const durationMs = Math.round(performance.now() - started);
  await test.info().attach(`guardian-metric:${metric}`, {
    body: Buffer.from(JSON.stringify({ metric, durationMs })),
    contentType: "application/json",
  });
  expect(durationMs, `${metric} exceeded ${budgetMs}ms`).toBeLessThanOrEqual(budgetMs);
}

export async function expectUsableControls(page: Page, controls: Locator[]) {
  const dimensions = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  expect(dimensions.scroll, "Horizontal overflow").toBeLessThanOrEqual(dimensions.client);
  for (const control of controls) {
    await expect(control).toBeVisible();
    await expect(control).toBeEnabled();
    await control.evaluate((element) => element.scrollIntoView({ block: "center", behavior: "instant" }));
    await control.click({ trial: true });
    const usable = await control.evaluate((element) => {
      const box = element.getBoundingClientRect();
      const hit = document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2);
      return { width: box.width, height: box.height, unobstructed: hit !== null && element.contains(hit) };
    });
    // Initial RC budget; a stricter 44px design target can follow a UI review.
    expect(usable.width, "Control is too narrow").toBeGreaterThanOrEqual(36);
    expect(usable.height, "Control is too short").toBeGreaterThanOrEqual(36);
    expect(usable.unobstructed, "Control is covered by another element").toBe(true);
  }
}
