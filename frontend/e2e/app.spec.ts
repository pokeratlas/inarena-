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
