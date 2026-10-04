import { expect, test } from "@playwright/test";
import { expectUsableControls } from "./guardian-checks";

const API = "http://127.0.0.1:8000";
const BOOTSTRAP_KEY = "fullstack-operator";

test("Table V2 keeps hero, opponents and board readable on mobile and desktop @guardian-table-v2", async ({ page, request }) => {
  const suffix = `${test.info().project.name}-${test.info().retry}-${Date.now()}`;
  const name = `Table V2 ${suffix}`;

  const auth = await request.post(`${API}/api/v1/operator/auth`, {
    headers: { "X-Operator-Key": BOOTSTRAP_KEY },
    data: { scopes: [] },
  });
  expect(auth.ok()).toBeTruthy();
  const operator = { "X-Operator-Key": (await auth.json()).token };

  const created = await request.post(`${API}/api/v1/operator/tables`, {
    headers: operator,
    data: { name },
  });
  expect(created.ok()).toBeTruthy();
  const table = await created.json();

  const players: Array<{ user: string; sessionId: string; seat: number }> = [];
  for (const seat of [1, 2, 3, 4, 5, 6, 7]) {
    const user = `table-v2-${suffix}-${seat}`;
    expect((await request.post(`${API}/api/v1/operator/balance`, {
      headers: operator,
      data: { user_id: user, delta: 20_000 },
    })).ok()).toBeTruthy();

    const sessionResponse = await request.post(`${API}/api/v1/sessions`, {
      data: {
        user_id: user,
        provider: "test",
        data: { telegram_user: { first_name: seat === 1 ? "Hero" : `Opponent ${seat}` } },
      },
    });
    expect(sessionResponse.ok()).toBeTruthy();
    const session = await sessionResponse.json();

    expect((await request.post(`${API}/api/v1/tables/${table.id}/join-auth`, {
      headers: {
        "X-Session-ID": session.session_id,
        "Idempotency-Key": `table-v2-join-${suffix}-${seat}`,
      },
      data: { seat_no: seat, stack: 10_000 },
    })).ok()).toBeTruthy();

    players.push({ user, sessionId: session.session_id, seat });
  }

  await expect.poll(async () => {
    const state = await (await request.get(`${API}/api/v1/tables/${table.id}`)).json();
    return state.active_hand?.street ?? null;
  }, { timeout: 10_000 }).toBe("preflop");

  await page.addInitScript((sessionId) => {
    localStorage.setItem("inarena_session_id", sessionId);
  }, players[0].sessionId);
  await page.goto("/");
  await page.getByRole("button", { name: "ONLINE" }).click();

  const mine = page.getByRole("region", { name: "Ваши столы" });
  await expect(mine.getByText(name, { exact: true })).toBeVisible();
  await mine.getByRole("button", { name: "Вернуться в игру", exact: true }).click();

  const stage = page.getByLabel("Стол INARENA", { exact: true });
  const hero = page.getByLabel("Ваше место", { exact: true });
  const opponents = page.locator(".opponent-seat");
  await expect(stage).toBeVisible();
  await expect(hero).toBeVisible();
  await expect(opponents).toHaveCount(6);
  await expect(page.getByLabel("Ваши карты")).toBeVisible();
  await expect(page.getByLabel("Общие карты")).toBeVisible();
  await expect(page.locator(".pot-display-v2")).toContainText("BB");

  const geometry = await page.evaluate(() => {
    const stage = document.querySelector('[aria-label="Стол INARENA"]')!.getBoundingClientRect();
    const hero = document.querySelector('[aria-label="Ваше место"]')!.getBoundingClientRect();
    const opponents = Array.from(document.querySelectorAll(".opponent-seat"))
      .map((element) => element.getBoundingClientRect());
    return {
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      stageLeft: stage.left,
      stageRight: stage.right,
      stageTop: stage.top,
      stageBottom: stage.bottom,
      heroCenter: hero.top + hero.height / 2,
      stageCenter: stage.top + stage.height / 2,
      maxOpponentCenter: Math.max(...opponents.map((rect) => rect.top + rect.height / 2)),
      opponentsInside: opponents.every((rect) =>
        rect.left >= stage.left - 2 &&
        rect.right <= stage.right + 2 &&
        rect.top >= stage.top - 2 &&
        rect.bottom <= stage.bottom + 2
      ),
    };
  });
  expect(geometry.scrollWidth).toBeLessThanOrEqual(geometry.clientWidth);
  expect(geometry.stageLeft).toBeGreaterThanOrEqual(-1);
  expect(geometry.stageRight).toBeLessThanOrEqual(geometry.clientWidth + 1);
  expect(geometry.heroCenter).toBeGreaterThan(geometry.stageCenter);
  expect(geometry.maxOpponentCenter).toBeLessThan(geometry.heroCenter);
  expect(geometry.opponentsInside).toBe(true);

  const info = page.getByRole("button", { name: "Информация о столе" });
  await expectUsableControls(page, [info]);
  await info.click();
  await expect(page.getByLabel("Информация о столе")).toContainText("7-MAX");
});
