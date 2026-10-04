import { expect, test } from "@playwright/test";
import { expectUsableControls, measureJourney } from "./guardian-checks";

const API = "http://127.0.0.1:8000";
const BOOTSTRAP_KEY = "fullstack-operator";

test("owner credits test chips and filters tables safely @guardian-owner-credit", async ({ page, request }) => {
  const suffix = `${test.info().project.name}-${test.info().retry}-${Date.now()}`;
  const userId = `owner-credit-${suffix}`;
  const openName = `Credit open ${suffix}`;
  const pausedName = `Credit paused ${suffix}`;

  const auth = await request.post(`${API}/api/v1/operator/auth`, {
    headers: { "X-Operator-Key": BOOTSTRAP_KEY },
    data: { scopes: [] },
  });
  expect(auth.ok()).toBeTruthy();
  const operator = { "X-Operator-Key": (await auth.json()).token };

  const sessionResponse = await request.post(`${API}/api/v1/sessions`, {
    data: { user_id: userId, provider: "test", data: {} },
  });
  expect(sessionResponse.ok()).toBeTruthy();
  const sessionId = (await sessionResponse.json()).session_id;

  for (const name of [openName, pausedName]) {
    const created = await request.post(`${API}/api/v1/operator/tables`, {
      headers: operator,
      data: { name },
    });
    expect(created.ok()).toBeTruthy();
  }

  await page.goto("/?operator=1");
  await page.getByPlaceholder("Bootstrap operator key").fill(BOOTSTRAP_KEY);
  await page.getByRole("button", { name: "Получить сессию" }).click();

  const credit = page.getByRole("region", {
    name: "Быстрое начисление тестовых chips",
  });
  const playerId = credit.getByLabel("Player ID для начисления");
  const addFive = credit.getByRole("button", {
    name: "Начислить 5000 test chips",
  });
  await playerId.fill(userId);
  await expectUsableControls(page, [addFive]);

  await measureJourney("owner-credit", "quick-credit", async () => {
    await addFive.click();
    await expect(credit.getByRole("status")).toContainText(/5[,\\s]?000/);
  });

  const balance = await request.get(`${API}/api/v1/me/balance`, {
    headers: { "X-Session-ID": sessionId },
  });
  expect(balance.ok()).toBeTruthy();
  expect((await balance.json()).balance).toBe(5_000);

  const pausedCard = page.locator(".operator-table-card").filter({ hasText: pausedName });
  const openCard = page.locator(".operator-table-card").filter({ hasText: openName });
  await expect(pausedCard).toBeVisible();
  await expect(openCard).toBeVisible();
  await pausedCard.getByRole("button", { name: "Пауза" }).click();
  await expect(pausedCard.getByText("Пауза", { exact: true })).toBeVisible();

  const pausedFilter = page.getByRole("button", {
    name: "Показать столы: пауза",
  });
  const openFilter = page.getByRole("button", {
    name: "Показать столы: открыты",
  });
  await expectUsableControls(page, [pausedFilter, openFilter]);

  await pausedFilter.click();
  await expect(pausedCard).toBeVisible();
  await expect(openCard).toHaveCount(0);

  await openFilter.click();
  await expect(openCard).toBeVisible();
  await expect(pausedCard).toHaveCount(0);
});
