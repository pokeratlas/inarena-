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
