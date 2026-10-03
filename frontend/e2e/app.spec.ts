import { expect, test } from "@playwright/test";

test("player shell switches offline and online modes", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByText("INARENA", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Главная" })).toBeVisible();

  await page.getByRole("button", { name: "ONLINE" }).click();
  await expect(page.getByRole("heading", { name: "Лобби" })).toBeVisible();
  await expect(page.getByText("Откройте приложение внутри Telegram")).toBeVisible();
});

test("operator route renders protected dashboard login", async ({ page }) => {
  await page.goto("/?operator=1");

  await expect(page.getByText("INARENA OPERATOR")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await expect(page.getByPlaceholder("Bootstrap operator key")).toBeVisible();
  await expect(page.getByRole("button", { name: "Получить сессию" })).toBeVisible();
});


for (const width of [360, 390, 430]) {
  test(`mobile shell has no horizontal overflow at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/");

    const dimensions = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }));

    expect(dimensions.scrollWidth).toBeLessThanOrEqual(
      dimensions.clientWidth,
    );
    await expect(
      page.getByRole("button", { name: "ONLINE" }),
    ).toBeVisible();
    await expect(
      page.getByRole("navigation", { name: "Основная навигация" }),
    ).toBeVisible();
  });
}

test("operator dashboard uses desktop width without overflow", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/?operator=1");

  const geometry = await page.locator(".operator-shell").evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return {
      width: rect.width,
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    };
  });

  expect(geometry.width).toBeGreaterThan(430);
  expect(geometry.width).toBeLessThanOrEqual(1100);
  expect(geometry.scrollWidth).toBeLessThanOrEqual(geometry.clientWidth);
});


test("beta diagnostics renders without sensitive credentials", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?diagnostics=1");

  await expect(
    page.getByRole("heading", { name: "Device diagnostics" }),
  ).toBeVisible();
  await expect(page.getByText("Telegram", { exact: true })).toBeVisible();
  await expect(page.getByText("Viewport", { exact: true })).toBeVisible();
  await expect(page.getByText("Session", { exact: true })).toBeVisible();

  const content = await page.locator("body").innerText();
  expect(content).not.toContain("initData=");
  expect(content).not.toContain("inarena_session_id");
  expect(content).not.toContain("ops_");

  const width = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(width).toBeLessThanOrEqual(390);
});


test("profile outside Telegram explains sign-in without exposing credentials", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Профиль", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Профиль", exact: true })).toBeVisible();
  await expect(page.getByText(/Откройте приложение внутри Telegram и дождитесь входа/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Создать стол" })).toHaveCount(0);
  await page.getByRole("button", { name: "Главная", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Главная", exact: true })).toBeVisible();
});
