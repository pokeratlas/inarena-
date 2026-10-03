import { expect, test } from "@playwright/test";

const API = "http://127.0.0.1:8000";
const BOOTSTRAP_KEY = "fullstack-operator";

async function createOperatorToken(request: any): Promise<string> {
  const response = await request.post(`${API}/api/v1/operator/auth`, {
    headers: { "X-Operator-Key": BOOTSTRAP_KEY },
    data: { scopes: [] },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()).token;
}

test("operator bootstrap exchanges for scoped session and dashboard loads", async ({
  page,
}) => {
  await page.goto("/?operator=1");

  await page
    .getByPlaceholder("Bootstrap operator key")
    .fill(BOOTSTRAP_KEY);
  await page.getByRole("button", { name: "Получить сессию" }).click();

  await expect(page.getByText("Tables", { exact: true })).toBeVisible();
  const token = await page.evaluate(() =>
    localStorage.getItem("inarena_operator_token"),
  );
  expect(token).toMatch(/^ops_/);

  await expect(page.getByPlaceholder("Bootstrap operator key")).toHaveCount(0);
  const reopened = await page.context().newPage();
  await reopened.goto("/?operator=1");
  await expect(reopened.getByText("Tables", { exact: true })).toBeVisible();
  await reopened.close();
  await page.reload();
  await expect(page.getByText("Tables", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Выйти" })).toBeVisible();

  await page.getByRole("button", { name: "Выйти" }).click();
  await expect(page.getByPlaceholder("Bootstrap operator key")).toBeVisible();
  expect(
    await page.evaluate(() =>
      localStorage.getItem("inarena_operator_token"),
    ),
  ).toBeNull();
});

test("authenticated player restores session and joins a real cash table", async ({
  page,
  request,
}) => {
  const operatorToken = await createOperatorToken(request);

  const tableResponse = await request.post(
    `${API}/api/v1/operator/tables`,
    {
      headers: { "X-Operator-Key": operatorToken },
      data: { name: "E2E Cash Table" },
    },
  );
  expect(tableResponse.ok()).toBeTruthy();
  const table = await tableResponse.json();

  const balanceResponse = await request.post(
    `${API}/api/v1/operator/balance`,
    {
      headers: { "X-Operator-Key": operatorToken },
      data: { user_id: "e2e-player", delta: 20_000 },
    },
  );
  expect(balanceResponse.ok()).toBeTruthy();

  const sessionResponse = await request.post(`${API}/api/v1/sessions`, {
    data: {
      user_id: "e2e-player",
      provider: "test",
      data: {},
    },
  });
  expect(sessionResponse.ok()).toBeTruthy();
  const session = await sessionResponse.json();

  await page.goto("/");
  await page.evaluate((sessionId) => {
    localStorage.setItem("inarena_session_id", sessionId);
  }, session.session_id);
  await page.reload();

  await page.getByRole("button", { name: "ONLINE" }).click();
  await expect(page.getByText("E2E Cash Table")).toBeVisible();
  await expect(page.getByText(/Баланс 20000 chips/)).toBeVisible();

  await page.getByRole("button", { name: /Сесть · Seat 1/ }).click();

  await expect(page.getByText("E2E Cash Table")).toBeVisible();
  await expect(page.getByText(/Seat 1 · Вы/)).toBeVisible();

  const stateResponse = await request.get(
    `${API}/api/v1/tables/${table.id}`,
  );
  expect(stateResponse.ok()).toBeTruthy();
  const state = await stateResponse.json();
  expect(state.seats).toHaveLength(1);
  expect(state.seats[0].player_id).toBe("e2e-player");
  expect(state.seats[0].stack).toBe(10_000);
});


test("invalid persisted operator token is cleared and recovery is explicit", async ({
  page,
}) => {
  await page.goto("/?operator=1");
  await page.evaluate(() => {
    localStorage.setItem("inarena_operator_token", "ops_invalid");
  });
  await page.reload();

  await expect(
    page.getByText("Сессия оператора истекла. Получите новую сессию."),
  ).toBeVisible();
  expect(
    await page.evaluate(() =>
      localStorage.getItem("inarena_operator_token"),
    ),
  ).toBeNull();
});


test("only an authenticated operator can create a table from Dashboard", async ({ page, request }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Создать стол" })).toHaveCount(0);
  await page.goto("/?operator=1");
  await expect(page.getByRole("button", { name: "Создать стол" })).toHaveCount(0);
  await page.getByPlaceholder("Bootstrap operator key").fill(BOOTSTRAP_KEY);
  await page.getByRole("button", { name: "Получить сессию" }).click();
  const createButton = page.getByRole("button", { name: "Создать стол", exact: true });
  await expect(createButton).toBeVisible();
  await expect(createButton).toBeDisabled();
  await page.getByRole("textbox", { name: "Название стола" }).fill("   ");
  await expect(createButton).toBeDisabled();
  await page.getByRole("textbox", { name: "Название стола" }).fill("Owner-created beta table");
  await createButton.click();
  await expect(page.locator(".operator-table-card").filter({ hasText: "Owner-created beta table" })).toHaveCount(1);
  const tables = await request.get(`${API}/api/v1/tables`);
  expect((await tables.json()).filter((table: any) => table.name === "Owner-created beta table")).toHaveLength(1);
  await page.getByRole("button", { name: "Выйти" }).click();
  await expect(createButton).toHaveCount(0);
});


test("player profile shows only identity and refreshed balance", async ({ page, request }) => {
  const token = await createOperatorToken(request);
  const userId = "profile-player";
  const sessionResponse = await request.post(`${API}/api/v1/sessions`, {
    data: { user_id: userId, provider: "test", data: { telegram_user: { first_name: "Beta", last_name: "Player" } } },
  });
  const session = await sessionResponse.json();
  await page.addInitScript((id) => localStorage.setItem("inarena_session_id", id), session.session_id);
  await page.goto("/");
  await page.getByRole("button", { name: "ONLINE", exact: false }).click();
  await page.getByRole("button", { name: "Профиль", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Профиль", exact: true })).toBeVisible();
  await expect(page.getByText("Beta Player", { exact: true })).toBeVisible();
  await expect(page.getByText(userId, { exact: true })).toBeVisible();
  await expect(page.getByText("0 chips", { exact: true })).toBeVisible();
  expect(await page.locator("body").innerText()).not.toContain(session.session_id);
  await expect(page.getByRole("button", { name: "Создать стол" })).toHaveCount(0);
  const credit = await request.post(`${API}/api/v1/operator/balance`, {
    headers: { "X-Operator-Key": token }, data: { user_id: userId, delta: 20000 },
  });
  expect(credit.ok()).toBeTruthy();
  await page.getByRole("button", { name: "Обновить баланс" }).click();
  await expect(page.getByText("20000 chips", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Лобби", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Лобби" })).toBeVisible();
  await expect(page.getByText(/Баланс 20000 chips/)).toBeVisible();
});


test("owner starts a two-player hand and duplicate start stays disabled", async ({ page, request }) => {
  const token = await createOperatorToken(request);
  const headers = { "X-Operator-Key": token };
  const created = await request.post(`${API}/api/v1/operator/tables`, { headers, data: { name: "Start hand test" } });
  expect(created.ok()).toBeTruthy();
  const table = await created.json();
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Начать раздачу" })).toHaveCount(0);
  await page.goto("/?operator=1");
  await page.getByPlaceholder("Bootstrap operator key").fill(BOOTSTRAP_KEY);
  await page.getByRole("button", { name: "Получить сессию" }).click();
  const card = page.locator(".operator-table-card").filter({ hasText: "Start hand test" });
  const start = card.getByRole("button", { name: "Начать раздачу" });
  await start.click();
  await expect(page.getByRole("alert")).toContainText("at least two funded players");
  for (const seat of [1, 2]) {
    const user = `start-player-${seat}`;
    expect((await request.post(`${API}/api/v1/operator/balance`, { headers, data: { user_id: user, delta: 20000 } })).ok()).toBeTruthy();
    const session = await (await request.post(`${API}/api/v1/sessions`, { data: { user_id: user, provider: "test", data: {} } })).json();
    expect((await request.post(`${API}/api/v1/tables/${table.id}/join-auth`, { headers: { "X-Session-ID": session.session_id, "Idempotency-Key": `start-join-${seat}` }, data: { seat_no: seat, stack: 10000 } })).ok()).toBeTruthy();
  }
  await start.click();
  await expect(start).toBeDisabled();
  const state = await (await request.get(`${API}/api/v1/tables/${table.id}`)).json();
  expect(state.active_hand.street).toBe("preflop");
  expect(state.active_hand.pot).toBe(150);
  expect(state.seats).toHaveLength(2);
});


test("two player clients receive actions and cash game continues to next hand", async ({ browser, request }) => {
  const token = await createOperatorToken(request);
  const headers = { "X-Operator-Key": token };
  const created = await request.post(`${API}/api/v1/operator/tables`, {
    headers,
    data: { name: "Functional cash loop" },
  });
  expect(created.ok()).toBeTruthy();
  const table = await created.json();

  const players: Array<{ user: string; sessionId: string; seat: number }> = [];
  for (const seat of [1, 2]) {
    const user = `functional-player-${seat}`;
    const credit = await request.post(`${API}/api/v1/operator/balance`, {
      headers,
      data: { user_id: user, delta: 20_000 },
    });
    expect(credit.ok()).toBeTruthy();
    const sessionResponse = await request.post(`${API}/api/v1/sessions`, {
      data: { user_id: user, provider: "test", data: {} },
    });
    expect(sessionResponse.ok()).toBeTruthy();
    const session = await sessionResponse.json();
    const joined = await request.post(`${API}/api/v1/tables/${table.id}/join-auth`, {
      headers: {
        "X-Session-ID": session.session_id,
        "Idempotency-Key": `functional-join-${seat}`,
      },
      data: { seat_no: seat, stack: 10_000 },
    });
    expect(joined.ok()).toBeTruthy();
    players.push({ user, sessionId: session.session_id, seat });
  }

  const clients = [];
  for (const player of players) {
    const context = await browser.newContext();
    await context.addInitScript((sessionId) => {
      localStorage.setItem("inarena_session_id", sessionId);
    }, player.sessionId);
    const playerPage = await context.newPage();
    await playerPage.goto("/");
    await playerPage.getByRole("button", { name: "ONLINE", exact: false }).click();
    const card = playerPage.locator(".lobby-card").filter({ hasText: "Functional cash loop" });
    await card.getByRole("button", { name: "Открыть" }).click();
    await expect(playerPage.getByRole("heading", { name: "Functional cash loop" })).toBeVisible();
    clients.push({ ...player, context, page: playerPage });
  }

  const started = await request.post(
    `${API}/api/v1/operator/tables/${table.id}/start-hand`,
    { headers, data: {} },
  );
  expect(started.ok()).toBeTruthy();
  const firstHand = await started.json();
  const firstHandId = firstHand.active_hand.hand_id;
  const actionSeat = firstHand.active_hand.action_seat;
  const actor = clients.find((client) => client.seat === actionSeat);
  const observer = clients.find((client) => client.seat !== actionSeat);
  expect(actor).toBeTruthy();
  expect(observer).toBeTruthy();

  await expect(actor!.page.getByLabel("Ваши карты")).toBeVisible();
  await expect(actor!.page.getByLabel("Действия игрока")).toBeVisible();
  await expect(actor!.page.getByRole("button", { name: "Fold" })).toBeVisible();
  await expect(actor!.page.getByRole("button", { name: /Call|Check/ })).toBeVisible();
  await expect(actor!.page.getByRole("button", { name: /Raise|Bet/ })).toBeVisible();
  await expect(observer!.page.getByText("Ожидание хода соперника…")).toBeVisible();

  await actor!.page.getByRole("button", { name: "Fold" }).click();

  await expect.poll(async () => {
    const state = await (await request.get(`${API}/api/v1/tables/${table.id}`)).json();
    return state.active_hand?.hand_id ?? null;
  }, { timeout: 10_000 }).not.toBe(firstHandId);

  const nextState = await (await request.get(`${API}/api/v1/tables/${table.id}`)).json();
  expect(nextState.status).toBe("playing");
  expect(nextState.active_hand).not.toBeNull();
  expect(nextState.active_hand.pot).toBe(150);

  const nextActor = clients.find((client) => client.seat === nextState.active_hand.action_seat);
  await expect(nextActor!.page.getByLabel("Действия игрока")).toBeVisible();

  for (const client of clients) {
    await client.context.close();
  }
});
