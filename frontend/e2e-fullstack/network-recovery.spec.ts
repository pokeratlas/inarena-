import { expect, test } from "@playwright/test";
import { measureJourney } from "./guardian-checks";

const API = "http://127.0.0.1:8000";

test("active cash hand recovers after an offline gap without duplicate action @guardian-network-recovery", async ({ browser, request }) => {
  test.setTimeout(60_000);

  const suffix = `${test.info().project.name}-${test.info().retry}-${Date.now()}`;
  const name = `Network recovery ${suffix}`;
  const auth = await request.post(`${API}/api/v1/operator/auth`, {
    headers: { "X-Operator-Key": "fullstack-operator" },
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
    const user = `network-${suffix}-${seat}`;
    expect((await request.post(`${API}/api/v1/operator/balance`, {
      headers: operator,
      data: { user_id: user, delta: 20_000 },
    })).ok()).toBeTruthy();

    const sessionResponse = await request.post(`${API}/api/v1/sessions`, {
      data: {
        user_id: user,
        provider: "test",
        data: { telegram_user: { first_name: `Network ${seat}` } },
      },
    });
    expect(sessionResponse.ok()).toBeTruthy();
    const session = await sessionResponse.json();

    expect((await request.post(`${API}/api/v1/tables/${table.id}/join-auth`, {
      headers: {
        "X-Session-ID": session.session_id,
        "Idempotency-Key": `network-join-${suffix}-${seat}`,
      },
      data: { seat_no: seat, stack: 10_000 },
    })).ok()).toBeTruthy();

    players.push({ user, sessionId: session.session_id, seat });
  }

  await expect.poll(async () => {
    const state = await (await request.get(`${API}/api/v1/tables/${table.id}`)).json();
    return state.active_hand?.hand_id ?? null;
  }, { timeout: 10_000 }).not.toBeNull();

  const beforeOpen = await (await request.get(`${API}/api/v1/tables/${table.id}`)).json();
  const firstHandId = beforeOpen.active_hand.hand_id;
  const actor = players.find((player) => player.seat === beforeOpen.active_hand.action_seat);
  expect(actor).toBeTruthy();

  const context = await browser.newContext();
  await context.addInitScript((sessionId) => {
    localStorage.setItem("inarena_session_id", sessionId);
  }, actor!.sessionId);
  const page = await context.newPage();
  await page.goto("/");
  await page.getByRole("button", { name: "ONLINE" }).click();

  const mine = page.getByRole("region", { name: "Ваши столы" });
  await expect(mine.getByText(name, { exact: true })).toBeVisible();
  await mine.getByRole("button", { name: "Вернуться в игру", exact: true }).click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  await expect(page.getByLabel("Соединение активно", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Действия игрока")).toBeVisible();

  const current = await (await request.get(`${API}/api/v1/tables/${table.id}`)).json();
  expect(current.active_hand?.hand_id).toBe(firstHandId);
  expect(current.active_hand?.action_seat).toBe(actor!.seat);

  await context.setOffline(true);
  await expect(page.getByLabel("Переподключение", { exact: true })).toBeVisible();
  await expect(page.getByText(
    "Восстанавливаем связь со столом. Дождитесь обновления перед действием.",
    { exact: true },
  )).toBeVisible();
  await expect(page.getByRole("button", { name: "Fold", exact: true })).toBeDisabled();

  const traceId = `guardian-network-${suffix}`;
  const serverFold = await request.post(`${API}/api/v1/tables/${table.id}/action-auth`, {
    headers: {
      "X-Session-ID": actor!.sessionId,
      "Idempotency-Key": `network-fold-${suffix}`,
      "X-Request-ID": traceId,
    },
    data: {
      action: "fold",
      expected_action_no: Number(current.active_hand.state.action_no ?? 0),
    },
  });
  expect(serverFold.ok()).toBeTruthy();
  expect(serverFold.headers()["x-request-id"]).toBe(traceId);

  await expect.poll(async () => {
    const state = await (await request.get(`${API}/api/v1/tables/${table.id}`)).json();
    const handId = state.active_hand?.hand_id ?? null;
    return handId !== null && handId !== firstHandId;
  }, { timeout: 10_000 }).toBe(true);

  await measureJourney("network-recovery", "active-hand-reconnect", async () => {
    await context.setOffline(false);
    await expect(page.getByLabel("Соединение активно", { exact: true })).toBeVisible();
    await expect(page.locator(".pot-display strong")).toHaveText("1.5 BB");
    await expect(page.locator(".pot-display-v2")).toContainText("150 chips");
    await expect(page.locator(".street-label")).toHaveText("PREFLOP");
  });

  const history = await (await request.get(
    `${API}/api/v1/tables/${table.id}/hands?limit=10`,
  )).json();
  expect(history.filter((hand: any) => hand.hand_id === firstHandId)).toHaveLength(1);

  const actions = await (await request.get(
    `${API}/api/v1/tables/${table.id}/hands/${firstHandId}/actions`,
  )).json();
  expect(actions.filter((action: any) =>
    action.player_id === actor!.user && action.action === "fold",
  )).toHaveLength(1);

  await context.close();
});
