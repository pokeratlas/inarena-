import { expect, test } from "@playwright/test";
import { expectUsableControls } from "./guardian-checks";

const API = "http://127.0.0.1:8000";
const BOOTSTRAP_KEY = "fullstack-operator";

test("hand history opens as a usable mobile drawer @guardian-table-utilities", async ({ page, request }) => {
  const suffix = `${test.info().project.name}-${test.info().retry}-${Date.now()}`;
  const name = `Utilities ${suffix}`;

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
  for (const seat of [1, 2]) {
    const user = `utilities-${suffix}-${seat}`;
    expect((await request.post(`${API}/api/v1/operator/balance`, {
      headers: operator,
      data: { user_id: user, delta: 20_000 },
    })).ok()).toBeTruthy();

    const sessionResponse = await request.post(`${API}/api/v1/sessions`, {
      data: {
        user_id: user,
        provider: "test",
        data: { telegram_user: { first_name: `Player ${seat}` } },
      },
    });
    expect(sessionResponse.ok()).toBeTruthy();
    const session = await sessionResponse.json();

    expect((await request.post(`${API}/api/v1/tables/${table.id}/join-auth`, {
      headers: {
        "X-Session-ID": session.session_id,
        "Idempotency-Key": `utilities-join-${suffix}-${seat}`,
      },
      data: { seat_no: seat, stack: 10_000 },
    })).ok()).toBeTruthy();

    players.push({ user, sessionId: session.session_id, seat });
  }

  await expect.poll(async () => {
    const state = await (await request.get(`${API}/api/v1/tables/${table.id}`)).json();
    return state.active_hand ?? null;
  }, { timeout: 10_000 }).not.toBeNull();

  const live = await (await request.get(`${API}/api/v1/tables/${table.id}`)).json();
  const actor = players.find((player) => player.seat === live.active_hand.action_seat)!;
  const fold = await request.post(`${API}/api/v1/tables/${table.id}/action-auth`, {
    headers: {
      "X-Session-ID": actor.sessionId,
      "Idempotency-Key": `utilities-fold-${suffix}`,
    },
    data: {
      action: "fold",
      expected_action_no: Number(live.active_hand.state.action_no ?? 0),
    },
  });
  expect(fold.ok()).toBeTruthy();

  await expect.poll(async () => {
    const rows = await (await request.get(`${API}/api/v1/tables/${table.id}/hands?limit=5`)).json();
    return rows.length;
  }, { timeout: 10_000 }).toBeGreaterThan(0);

  await page.addInitScript((sessionId) => {
    localStorage.setItem("inarena_session_id", sessionId);
  }, players[0].sessionId);
  await page.goto("/");
  await page.getByRole("button", { name: "ONLINE" }).click();

  const mine = page.getByRole("region", { name: "Ваши столы" });
  await expect(mine.getByText(name, { exact: true })).toBeVisible();
  await mine.getByRole("button", { name: "Вернуться в игру", exact: true }).click();

  const historyButton = page.getByRole("button", { name: "История рук" });
  await expectUsableControls(page, [historyButton]);
  await historyButton.click();

  const drawer = page.getByRole("dialog", { name: "История рук" });
  await expect(drawer).toBeVisible();
  await expect(drawer.getByText("История рук", { exact: true })).toBeVisible();
  await expect(drawer.getByLabel("Последняя раздача")).toContainText("BB");
  await expect(drawer.getByLabel("Действия раздачи")).toContainText("fold");

  const geometry = await drawer.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return {
      left: rect.left,
      right: rect.right,
      viewport: document.documentElement.clientWidth,
      scroll: document.documentElement.scrollWidth,
    };
  });
  expect(geometry.left).toBeGreaterThanOrEqual(0);
  expect(geometry.right).toBeLessThanOrEqual(geometry.viewport + 1);
  expect(geometry.scroll).toBeLessThanOrEqual(geometry.viewport);

  const close = drawer.getByRole("button", { name: "Закрыть историю" });
  await expectUsableControls(page, [close]);
  await close.click();
  await expect(drawer).toHaveCount(0);
});
