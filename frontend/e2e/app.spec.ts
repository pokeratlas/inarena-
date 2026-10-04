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

  await expect(page.getByText("INARENA OWNER")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Table Manager" })).toBeVisible();
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


test("Telegram shell calls ready before slow session refresh and uses one restore request", async ({ page }) => {
  let currentSessionRequests = 0;
  let refreshSeen = false;
  let releaseRefresh!: () => void;
  const refreshGate = new Promise<void>((resolve) => {
    releaseRefresh = resolve;
  });

  await page.route("**/api/v1/auth/session", async (route) => {
    currentSessionRequests += 1;
    await route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ detail: "unexpected current-session request" }),
    });
  });

  await page.route("**/api/v1/auth/refresh", async (route) => {
    refreshSeen = true;
    await refreshGate;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        session_id: "session-fast-bootstrap",
        user_id: "telegram-user-1",
        provider: "telegram",
        data: { telegram_user: { first_name: "Fast" } },
        expires_at: null,
        updated_at: "2026-10-05T00:00:00Z",
      }),
    });
  });

  await page.route("**/telegram-web-app.js?63", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/javascript",
      body: `
        window.__telegramReadyCalls = 0;
        window.__telegramExpandCalls = 0;
        window.Telegram = {
          WebApp: {
            initData: "telegram-init-data",
            ready: () => { window.__telegramReadyCalls += 1; },
            expand: () => { window.__telegramExpandCalls += 1; }
          }
        };
      `,
    });
  });

  await page.addInitScript(() => {
    localStorage.setItem("inarena_session_id", "session-fast-bootstrap");
  });

  await page.goto("/");

  await expect.poll(() =>
    page.evaluate(() => (window as any).__telegramReadyCalls),
  ).toBeGreaterThan(0);
  await expect.poll(() => refreshSeen).toBe(true);
  expect(currentSessionRequests).toBe(0);

  // The native Telegram placeholder can already be dismissed while the
  // backend session refresh is still intentionally blocked.
  await expect(page.getByText("INARENA", { exact: true })).toBeVisible();

  releaseRefresh();
  await page.getByRole("button", { name: "ONLINE" }).click();
  await expect(page.getByText("Подключаем Telegram…")).toHaveCount(0);
});
