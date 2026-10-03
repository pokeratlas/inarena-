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
  await expect(page.getByText("ВЫ", { exact: true })).toBeVisible();

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


test("cash table auto-starts for two players and continues to next hand", async ({ browser, request }) => {
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

  await expect.poll(async () => {
    const state = await (await request.get(`${API}/api/v1/tables/${table.id}`)).json();
    return state.active_hand?.hand_id ?? null;
  }, { timeout: 10_000 }).not.toBeNull();

  const firstHand = await (await request.get(
    `${API}/api/v1/tables/${table.id}`,
  )).json();
  expect(firstHand.status).toBe("playing");
  expect(firstHand.active_hand.pot).toBe(150);
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
  await expect(observer!.page.getByText(`Ход игрока ${actionSeat}`)).toBeVisible();

  await actor!.page.getByRole("button", { name: "Fold" }).click();

  await expect.poll(async () => {
    const state = await (await request.get(`${API}/api/v1/tables/${table.id}`)).json();
    const handId = state.active_hand?.hand_id ?? null;
    return handId !== null && handId !== firstHandId;
  }, { timeout: 10_000 }).toBe(true);

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


test("cash watchdog starts a ready open table even when no join trigger fires", async ({ request }) => {
  const token = await createOperatorToken(request);
  const headers = { "X-Operator-Key": token };
  const created = await request.post(`${API}/api/v1/operator/tables`, {
    headers,
    data: { name: "Watchdog cash table" },
  });
  expect(created.ok()).toBeTruthy();
  const table = await created.json();

  for (const seat of [1, 2]) {
    const user = `watchdog-player-${seat}`;
    const joined = await request.post(`${API}/api/v1/tables/${table.id}/join`, {
      data: { player_id: user, seat_no: seat, stack: 10_000 },
    });
    expect(joined.ok()).toBeTruthy();
  }

  const immediatelyAfterJoin = await (
    await request.get(`${API}/api/v1/tables/${table.id}`)
  ).json();
  expect(immediatelyAfterJoin.status).toBe("open");
  expect(immediatelyAfterJoin.active_hand).toBeNull();

  await expect.poll(async () => {
    const state = await (
      await request.get(`${API}/api/v1/tables/${table.id}`)
    ).json();
    return {
      status: state.status,
      hand: state.active_hand?.hand_id ?? null,
      pot: state.active_hand?.pot ?? null,
    };
  }, { timeout: 10_000 }).toEqual({
    status: "playing",
    hand: expect.any(String),
    pot: 150,
  });
});


test("player can request leave during a hand and is removed before next cash hand", async ({ browser, request }) => {
  const token = await createOperatorToken(request);
  const headers = { "X-Operator-Key": token };
  const created = await request.post(`${API}/api/v1/operator/tables`, {
    headers,
    data: { name: "Leave after hand cash" },
  });
  expect(created.ok()).toBeTruthy();
  const table = await created.json();

  const players: Array<{ user: string; sessionId: string; seat: number }> = [];
  for (const seat of [1, 2]) {
    const user = `leave-player-${seat}`;
    expect((await request.post(`${API}/api/v1/operator/balance`, {
      headers,
      data: { user_id: user, delta: 20_000 },
    })).ok()).toBeTruthy();
    const session = await (await request.post(`${API}/api/v1/sessions`, {
      data: { user_id: user, provider: "test", data: {} },
    })).json();
    expect((await request.post(`${API}/api/v1/tables/${table.id}/join-auth`, {
      headers: {
        "X-Session-ID": session.session_id,
        "Idempotency-Key": `leave-join-${seat}`,
      },
      data: { seat_no: seat, stack: 10_000 },
    })).ok()).toBeTruthy();
    players.push({ user, sessionId: session.session_id, seat });
  }

  await expect.poll(async () => {
    const state = await (await request.get(`${API}/api/v1/tables/${table.id}`)).json();
    return state.active_hand?.hand_id ?? null;
  }, { timeout: 10_000 }).not.toBeNull();

  const state = await (await request.get(`${API}/api/v1/tables/${table.id}`)).json();
  const actionSeat = state.active_hand.action_seat;
  const actorPlayer = players.find((p) => p.seat === actionSeat)!;
  const leavingPlayer = players.find((p) => p.seat !== actionSeat)!;

  const actorContext = await browser.newContext();
  await actorContext.addInitScript((id) => localStorage.setItem("inarena_session_id", id), actorPlayer.sessionId);
  const actorPage = await actorContext.newPage();
  await actorPage.goto("/");
  await actorPage.getByRole("button", { name: "ONLINE", exact: false }).click();
  await actorPage.locator(".lobby-card").filter({ hasText: "Leave after hand cash" }).getByRole("button", { name: "Открыть" }).click();

  const leaveContext = await browser.newContext();
  await leaveContext.addInitScript((id) => localStorage.setItem("inarena_session_id", id), leavingPlayer.sessionId);
  const leavePage = await leaveContext.newPage();
  await leavePage.goto("/");
  await leavePage.getByRole("button", { name: "ONLINE", exact: false }).click();
  await leavePage.locator(".lobby-card").filter({ hasText: "Leave after hand cash" }).getByRole("button", { name: "Открыть" }).click();

  const leaveButton = leavePage.getByRole("button", { name: "Покинуть стол" });
  await expect(leaveButton).toBeVisible();
  await leaveButton.click();
  await expect(leavePage.getByRole("button", { name: "Выход после раздачи…" })).toBeVisible();

  await actorPage.getByRole("button", { name: "Fold" }).click();

  await expect.poll(async () => {
    const next = await (await request.get(`${API}/api/v1/tables/${table.id}`)).json();
    return next.seats.some((seat: any) => seat.player_id === leavingPlayer.user);
  }, { timeout: 10_000 }).toBe(false);

  const afterLeave = await (await request.get(`${API}/api/v1/tables/${table.id}`)).json();
  expect(afterLeave.seats).toHaveLength(1);
  expect(afterLeave.active_hand).toBeNull();
  expect(afterLeave.status).toBe("open");

  await actorContext.close();
  await leaveContext.close();
});


test("table state exposes only public player identity fields", async ({ request }) => {
  const token = await createOperatorToken(request);
  const headers = { "X-Operator-Key": token };
  const created = await request.post(`${API}/api/v1/operator/tables`, {
    headers,
    data: { name: "Identity table" },
  });
  const table = await created.json();

  expect((await request.post(`${API}/api/v1/operator/balance`, {
    headers,
    data: { user_id: "tg:identity-player", delta: 20_000 },
  })).ok()).toBeTruthy();

  const session = await (await request.post(`${API}/api/v1/sessions`, {
    data: {
      user_id: "tg:identity-player",
      provider: "telegram",
      data: {
        telegram_user: {
          first_name: "Ivan",
          last_name: "Petrov",
          username: "ivanp",
          photo_url: "https://example.com/avatar.jpg",
          language_code: "ru",
        },
        query_id: "private-query",
      },
    },
  })).json();

  expect((await request.post(`${API}/api/v1/tables/${table.id}/join-auth`, {
    headers: {
      "X-Session-ID": session.session_id,
      "Idempotency-Key": "identity-join",
    },
    data: { seat_no: 1, stack: 10_000 },
  })).ok()).toBeTruthy();

  const state = await (await request.get(`${API}/api/v1/tables/${table.id}`)).json();
  expect(state.seats[0].display_name).toBe("Ivan Petrov");
  expect(state.seats[0].photo_url).toBe("https://example.com/avatar.jpg");
  expect(JSON.stringify(state.seats[0])).not.toContain(session.session_id);
  expect(JSON.stringify(state.seats[0])).not.toContain("private-query");
  expect(JSON.stringify(state.seats[0])).not.toContain("language_code");
});
