import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

async function expectNoSeriousAccessibilityIssues(page: any) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();

  const blocking = results.violations.filter(
    (violation) =>
      violation.impact === "serious" || violation.impact === "critical",
  );

  expect(
    blocking,
    JSON.stringify(
      blocking.map((item) => ({
        id: item.id,
        impact: item.impact,
        help: item.help,
        nodes: item.nodes.map((node) => node.target),
      })),
      null,
      2,
    ),
  ).toEqual([]);
}

test("player shell has no serious accessibility violations", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("INARENA", { exact: true })).toBeVisible();

  await expectNoSeriousAccessibilityIssues(page);

  await page.keyboard.press("Tab");
  const focused = await page.evaluate(
    () => document.activeElement?.tagName.toLowerCase(),
  );
  expect(["button", "a", "input"]).toContain(focused);
});

test("online lobby shell remains keyboard accessible", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "ONLINE" }).click();

  await expect(page.getByRole("heading", { name: "Лобби" })).toBeVisible();
  await expectNoSeriousAccessibilityIssues(page);

  const buttons = page.getByRole("button");
  expect(await buttons.count()).toBeGreaterThan(0);
});

test("operator login has no serious accessibility violations", async ({
  page,
}) => {
  await page.goto("/?operator=1");

  const keyInput = page.getByPlaceholder("Bootstrap operator key");
  await expect(keyInput).toBeVisible();

  await expectNoSeriousAccessibilityIssues(page);

  await page.keyboard.press("Tab");
  await expect(keyInput).toBeFocused();

  await keyInput.fill("keyboard-test-key");
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("button", { name: "Получить сессию" }),
  ).toBeFocused();
});
