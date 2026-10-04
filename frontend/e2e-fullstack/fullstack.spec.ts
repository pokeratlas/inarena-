import { expect, test } from "@playwright/test";
import { expectUsableControls, measureJourney } from "./guardian-checks";

const API = "http://127.0.0.1:8000";
const BOOTSTRAP_KEY = "fullstack-operator";

function fixtureName(name: string): string {
  return `${name} ${test.info().project.name}-${test.info().retry}`;
}

async function createOperatorToken(request: any): Promise<string> {
  const response = await request.post(`${API}/api/v1/operator/auth`, {
    headers: { "X-Operator-Key": BOOTSTRAP_KEY },
    data: { scopes: [] },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()).token;
}

test("operator bootstrap exchanges for scoped session and dashboard loads @guardian-owner-session", async ({
  page,
}) => {
  await page.goto("/?operator=1");

  await page
    .getByPlaceholder("Bootstrap operator key")
    .fill(BOOTSTRAP_KEY);
  await page.getByRole("button", { name: "Получить сессию" }).click();

  await expect(page.getByRole("heading", { name: "Table Manager" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Выйти" })).toBeVisible();
  const token = await page.evaluate(() =>
    localStorage.getItem("inarena_operator_token"),
  );
  expect(token).toMatch(/^ops_/);

  await expect(page.getByPlaceholder("Bootstrap operator key")).toHaveCount(0);
  const reopened = await page.context().newPage();
  await reopened.goto("/?operator=1");
  await expect(reopened.getByRole("heading", { name: "Table Manager" })).toBeVisible();
  await expect(reopened.getByRole("button", { name: "Выйти" })).toBeVisible();
  await reopened.close();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Table Manager" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Выйти" })).toBeVisible();

  await page.getByRole("button", { name: "Выйти" }).click();
  await expect(page.getByPlaceholder("Bootstrap operator key")).toBeVisible();
  expect(
    await page.evaluate(() =>
      localStorage.getItem("inarena_operator_token"),
    ),
  ).toBeNull();
});

test("authenticated player restores session and joins a real cash table @guardian-join", async ({
  page,
  request,
}) => {
  const operatorToken = await createOperatorToken(request);

  const tableResponse = await request.post(
    `${API}/api/v1/operator/tables`,
    {
      headers: { "X-Operator-Key": operatorToken },
      data: { name: fixtureName("E2E Cash Table") },
    },
  );
  expect(tableResponse.ok()).toBeTruthy();
  const table = await tableResponse.json();

  const balanceResponse = await request.post(
    `${API}/api/v1/operator/balance`,
    {
      headers: { "X-Operator-Key": operatorToken },
      data: { user_id: fixtureName("e2e-player"), delta: 20_000 },
    },
  );
  expect(balanceResponse.ok()).toBeTruthy();

  const sessionResponse = await request.post(`${API}/api/v1/sessions`, {
    data: {
      user_id: fixtureName("e2e-player"),
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

  await measureJourney("join", "lobby-ready", async () => {
  await page.getByRole("button", { name: "ONLINE" }).click();
  await expect(page.getByText(fixtureName("E2E Cash Table"))).toBeVisible();
  await expect(page.getByText(/Баланс 20000 chips/)).toBeVisible();
  });

  await page.locator(".lobby-card").filter({ hasText: fixtureName("E2E Cash Table") })
    .getByRole("button", { name: /Сесть · Seat 1/ }).click();
  await expect(page.getByLabel("Выбор buy-in")).toBeVisible();
  await expect(
    page.getByLabel("Выбор buy-in").getByText(/Баланс 20,?000/),
  ).toBeVisible();
  await expectUsableControls(page, [
    page.getByRole("button", { name: "50 BB" }),
    page.getByRole("button", { name: /Сесть за стол/ }),
  ]);
  await measureJourney("join", "buy-in-seated", async () => {
  await page.getByRole("button", { name: "50 BB" }).click();
  await page.getByRole("button", { name: /Сесть за стол/ }).click();

  await expect(page.getByText(fixtureName("E2E Cash Table"))).toBeVisible();
  await expect(page.getByText("ВЫ", { exact: true })).toBeVisible();
  });

  const stateResponse = await request.get(
    `${API}/api/v1/tables/${table.id}`,
  );
  expect(stateResponse.ok()).toBeTruthy();
  const state = await stateResponse.json();
  expect(state.seats).toHaveLength(1);
  expect(state.seats[0].player_id).toBe(fixtureName("e2e-player"));
  expect(state.seats[0].stack).toBe(5_000);
});


test("invalid persisted operator token is cleared and recovery is explicit @guardian-owner-recovery", async ({
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


test("only an authenticated operator can create a table from Dashboard @guardian-owner-create", async ({ page, request }) => {
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
  await page.getByRole("textbox", { name: "Название стола" }).fill(fixtureName("Owner-created beta table"));
  await page.getByRole("spinbutton", { name: "Small blind" }).fill("25");
  await page.getByRole("spinbutton", { name: "Big blind" }).fill("50");
  await page.getByRole("spinbutton", { name: "Min buy-in" }).fill("1000");
  await page.getByRole("spinbutton", { name: "Max buy-in" }).fill("5000");
  await expectUsableControls(page, [createButton]);
  await measureJourney("owner-create", "owner-table-created", async () => {
  await createButton.click();
  await expect(page.locator(".operator-table-card").filter({ hasText: fixtureName("Owner-created beta table") })).toHaveCount(1);
  });
  const tables = await request.get(`${API}/api/v1/tables`);
  const createdTables = (await tables.json()).filter(
    (table: any) => table.name === fixtureName("Owner-created beta table"),
  );
  expect(createdTables).toHaveLength(1);
  expect(createdTables[0].max_seats).toBe(7);
  expect(createdTables[0].small_blind).toBe(25);
  expect(createdTables[0].big_blind).toBe(50);
  expect(createdTables[0].cash_buyin_min).toBe(1000);
  expect(createdTables[0].cash_buyin_max).toBe(5000);
  await page.getByRole("button", { name: "Выйти" }).click();
  await expect(createButton).toHaveCount(0);
});


test("player profile shows only identity and refreshed balance @guardian-profile", async ({ page, request }) => {
  const token = await createOperatorToken(request);
  const userId = fixtureName("profile-player");
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
  await expect(page.getByLabel("Карточка игрока")).toBeVisible();
  await expect(page.getByLabel("Баланс игрока")).toBeVisible();
  await expect(page.getByLabel("Статистика игрока")).toBeVisible();
  await expect(page.getByLabel("Последняя активность")).toBeVisible();
  const profileGeometry = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(profileGeometry.scrollWidth).toBeLessThanOrEqual(profileGeometry.clientWidth);
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  await expectUsableControls(page, [page.getByRole("button", { name: "Скопировать ID" })]);
  await page.getByRole("button", { name: "Скопировать ID" }).click();
  await expect(page.getByRole("status")).toHaveText("ID скопирован");
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(userId);
  await page.evaluate(() => {
    Object.defineProperty(navigator.clipboard, "writeText", {
      value: async () => { throw new Error("Clipboard denied"); },
    });
  });
  await page.getByRole("button", { name: "Скопировать ID" }).click();
  await expect(page.getByRole("status")).toContainText("скопируйте вручную");
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


test("owner table manager reflects a two-player live hand @guardian-owner-live", async ({ page, request }) => {
  const token = await createOperatorToken(request);
  const headers = { "X-Operator-Key": token };
  const created = await request.post(`${API}/api/v1/operator/tables`, {
    headers,
    data: { name: fixtureName("Start hand test") },
  });
  expect(created.ok()).toBeTruthy();
  const table = await created.json();

  await page.goto("/?operator=1");
  await page.getByPlaceholder("Bootstrap operator key").fill(BOOTSTRAP_KEY);
  await page.getByRole("button", { name: "Получить сессию" }).click();

  const card = page.locator(".operator-table-card").filter({
    hasText: fixtureName("Start hand test"),
  });
  await expect(card).toBeVisible();

  for (const seat of [1, 2]) {
    const user = `${fixtureName("start-player")}-${seat}`;
    expect((await request.post(`${API}/api/v1/operator/balance`, {
      headers,
      data: { user_id: user, delta: 20000 },
    })).ok()).toBeTruthy();
    const session = await (await request.post(`${API}/api/v1/sessions`, {
      data: { user_id: user, provider: "test", data: {} },
    })).json();
    expect((await request.post(`${API}/api/v1/tables/${table.id}/join-auth`, {
      headers: {
        "X-Session-ID": session.session_id,
        "Idempotency-Key": `start-join-${seat}`,
      },
      data: { seat_no: seat, stack: 10000 },
    })).ok()).toBeTruthy();
  }

  await expect.poll(async () => {
    const state = await (
      await request.get(`${API}/api/v1/tables/${table.id}`)
    ).json();
    return state.active_hand?.street ?? null;
  }, { timeout: 10_000 }).toBe("preflop");

  await expect(
    card.getByText("Идёт раздача", { exact: true }),
  ).toBeVisible({ timeout: 10_000 });
  await expect(card.getByText("2/7", { exact: true })).toBeVisible();
  await expect(card.getByRole("button", { name: "Начать раздачу" })).toHaveCount(0);
  await card.getByRole("button", { name: "Управление" }).click();
  await expect(card.getByText(/PREFLOP · Pot 150/)).toBeVisible();

  const state = await (
    await request.get(`${API}/api/v1/tables/${table.id}`)
  ).json();
  expect(state.active_hand.street).toBe("preflop");
  expect(state.active_hand.pot).toBe(150);
  expect(state.seats).toHaveLength(2);
});

test("cash table auto-starts for two players and continues to next hand @guardian-cash-loop", async ({ browser, request }) => {
  const token = await createOperatorToken(request);
  const headers = { "X-Operator-Key": token };
  const created = await request.post(`${API}/api/v1/operator/tables`, {
    headers,
    data: { name: fixtureName("Functional cash loop") },
  });
  expect(created.ok()).toBeTruthy();
  const table = await created.json();

  const players: Array<{ user: string; sessionId: string; seat: number }> = [];
  for (const seat of [1, 2]) {
    const user = `${fixtureName("functional-player")}-${seat}`;
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
    const card = playerPage.locator(".lobby-card").filter({ hasText: fixtureName("Functional cash loop") });
    await card.getByRole("button", { name: "Открыть" }).click();
    await expect(playerPage.getByRole("heading", { name: fixtureName("Functional cash loop") })).toBeVisible();
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

  let nextActor: (typeof clients)[number] | undefined;
  await measureJourney("cash-loop", "next-hand-ready", async () => {
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

  nextActor = clients.find((client) => client.seat === nextState.active_hand.action_seat);
  await expect(nextActor!.page.getByLabel("Действия игрока")).toBeVisible();
  });

  // Real UI Call -> Raise -> Call, then verify the authoritative flop/pot.
  await nextActor!.page.getByRole("button", { name: "Call 50", exact: true }).click();
  const raiser = clients.find((client) => client.seat !== nextActor!.seat)!;
  await expect(raiser.page.getByRole("button", { name: "Raise to 200", exact: true })).toBeEnabled();
  await raiser.page.getByRole("button", { name: "Raise to 200", exact: true }).click();
  await expect(nextActor!.page.getByRole("button", { name: "Call 100", exact: true })).toBeEnabled();
  await nextActor!.page.getByRole("button", { name: "Call 100", exact: true }).click();
  await expect.poll(async () => {
    const state = await (await request.get(`${API}/api/v1/tables/${table.id}`)).json();
    return { street: state.active_hand?.street, pot: state.active_hand?.pot };
  }).toEqual({ street: "flop", pot: 400 });

  for (const client of clients) {
    await client.context.close();
  }
});


test("cash watchdog starts a ready open table even when no join trigger fires @guardian-watchdog", async ({ request }) => {
  const token = await createOperatorToken(request);
  const headers = { "X-Operator-Key": token };
  const created = await request.post(`${API}/api/v1/operator/tables`, {
    headers,
    data: { name: fixtureName("Watchdog cash table") },
  });
  expect(created.ok()).toBeTruthy();
  const table = await created.json();

  for (const seat of [1, 2]) {
    const user = `${fixtureName("watchdog-player")}-${seat}`;
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


test("player can request leave during a hand and is removed before next cash hand @guardian-leave", async ({ browser, request }) => {
  const token = await createOperatorToken(request);
  const headers = { "X-Operator-Key": token };
  const created = await request.post(`${API}/api/v1/operator/tables`, {
    headers,
    data: { name: fixtureName("Leave after hand cash") },
  });
  expect(created.ok()).toBeTruthy();
  const table = await created.json();

  const players: Array<{ user: string; sessionId: string; seat: number }> = [];
  for (const seat of [1, 2]) {
    const user = `${fixtureName("leave-player")}-${seat}`;
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
  await actorPage.locator(".lobby-card").filter({ hasText: fixtureName("Leave after hand cash") }).getByRole("button", { name: "Открыть" }).click();

  const leaveContext = await browser.newContext();
  await leaveContext.addInitScript((id) => localStorage.setItem("inarena_session_id", id), leavingPlayer.sessionId);
  const leavePage = await leaveContext.newPage();
  await leavePage.goto("/");
  await leavePage.getByRole("button", { name: "ONLINE", exact: false }).click();
  await leavePage.locator(".lobby-card").filter({ hasText: fixtureName("Leave after hand cash") }).getByRole("button", { name: "Открыть" }).click();

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


test("table state exposes only public player identity fields @guardian-identity", async ({ request }) => {
  const token = await createOperatorToken(request);
  const headers = { "X-Operator-Key": token };
  const created = await request.post(`${API}/api/v1/operator/tables`, {
    headers,
    data: { name: fixtureName("Identity table") },
  });
  const table = await created.json();

  expect((await request.post(`${API}/api/v1/operator/balance`, {
    headers,
    data: { user_id: fixtureName("tg:identity-player"), delta: 20_000 },
  })).ok()).toBeTruthy();

  const session = await (await request.post(`${API}/api/v1/sessions`, {
    data: {
      user_id: fixtureName("tg:identity-player"),
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


test("cash player can sit out during a hand and return for the next one @guardian-sit-out", async ({ browser, request }) => {
  const token = await createOperatorToken(request);
  const headers = { "X-Operator-Key": token };
  const created = await request.post(`${API}/api/v1/operator/tables`, {
    headers,
    data: { name: fixtureName("Sit out cash") },
  });
  expect(created.ok()).toBeTruthy();
  const table = await created.json();

  const players: Array<{ user: string; sessionId: string; seat: number }> = [];
  for (const seat of [1, 2]) {
    const user = `${fixtureName("sitout-player")}-${seat}`;
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
        "Idempotency-Key": `sitout-join-${seat}`,
      },
      data: { seat_no: seat, stack: 10_000 },
    })).ok()).toBeTruthy();
    players.push({ user, sessionId: session.session_id, seat });
  }

  await expect.poll(async () => {
    const state = await (await request.get(`${API}/api/v1/tables/${table.id}`)).json();
    return state.active_hand?.action_seat ?? null;
  }, { timeout: 10_000 }).not.toBeNull();

  const playing = await (await request.get(`${API}/api/v1/tables/${table.id}`)).json();
  const actor = players.find((player) => player.seat === playing.active_hand.action_seat)!;

  const context = await browser.newContext();
  await context.addInitScript((id) => {
    localStorage.setItem("inarena_session_id", id);
  }, actor.sessionId);
  const page = await context.newPage();
  await page.goto("/");
  await page.getByRole("button", { name: "ONLINE", exact: false }).click();
  await page
    .locator(".lobby-card")
    .filter({ hasText: fixtureName("Sit out cash") })
    .getByRole("button", { name: "Открыть" })
    .click();

  await expect(page.getByRole("button", { name: "Sit out", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Sit out", exact: true }).click();
  await expect(page.getByRole("button", { name: "Sit out после раздачи" })).toBeVisible();

  const afterRequest = await (await request.get(`${API}/api/v1/tables/${table.id}`)).json();
  expect(
    afterRequest.seats.find((seat: any) => seat.player_id === actor.user)?.status,
  ).toBe("sitting_out_next");

  await expect(page.getByRole("button", { name: "Fold" })).toBeVisible();
  await page.getByRole("button", { name: "Fold" }).click();

  await expect.poll(async () => {
    const state = await (await request.get(`${API}/api/v1/tables/${table.id}`)).json();
    const actorSeat = state.seats.find((seat: any) => seat.player_id === actor.user);
    return {
      activeHand: state.active_hand,
      actorStatus: actorSeat?.status ?? null,
      status: state.status,
    };
  }, { timeout: 10_000 }).toEqual({
    activeHand: null,
    actorStatus: "sitting_out",
    status: "open",
  });

  await expect(page.getByRole("button", { name: "Вернуться в игру" })).toBeVisible();
  await page.getByRole("button", { name: "Вернуться в игру" }).click();

  await expect.poll(async () => {
    const state = await (await request.get(`${API}/api/v1/tables/${table.id}`)).json();
    return {
      hand: state.active_hand?.hand_id ?? null,
      actorStatus:
        state.seats.find((seat: any) => seat.player_id === actor.user)?.status ?? null,
    };
  }, { timeout: 10_000 }).toEqual({
    hand: expect.any(String),
    actorStatus: "seated",
  });

  await context.close();
});


test("cash player can top up immediately between hands @guardian-top-up", async ({ page, request }) => {
  const token = await createOperatorToken(request);
  const headers = { "X-Operator-Key": token };
  const created = await request.post(`${API}/api/v1/operator/tables`, {
    headers,
    data: { name: fixtureName("Immediate top-up cash") },
  });
  expect(created.ok()).toBeTruthy();
  const table = await created.json();

  const user = fixtureName("topup-immediate-player");
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
      "Idempotency-Key": "topup-immediate-join",
    },
    data: { seat_no: 1, stack: 5_000 },
  })).ok()).toBeTruthy();

  await page.addInitScript((id) => {
    localStorage.setItem("inarena_session_id", id);
  }, session.session_id);
  await page.goto("/");
  await page.getByRole("button", { name: "ONLINE", exact: false }).click();
  await page
    .locator(".lobby-card")
    .filter({ hasText: fixtureName("Immediate top-up cash") })
    .getByRole("button", { name: "Открыть" })
    .click();

  await page.getByRole("button", { name: "Пополнить стек" }).click();
  await expect(page.getByLabel("Пополнение стека")).toBeVisible();
  await page.getByRole("button", { name: "+25 BB" }).click();
  await page.getByRole("button", { name: /Добавить ·/ }).click();

  await expect.poll(async () => {
    const state = await (await request.get(
      `${API}/api/v1/tables/${table.id}`,
    )).json();
    const seat = state.seats.find((item: any) => item.player_id === user);
    return {
      stack: seat?.stack ?? null,
      pending: seat?.pending_top_up ?? null,
    };
  }).toEqual({ stack: 7_500, pending: 0 });

  const balance = await (await request.get(`${API}/api/v1/me/balance`, {
    headers: { "X-Session-ID": session.session_id },
  })).json();
  expect(balance.balance).toBe(17_500);
});


test("cash top-up requested during a hand applies only after settlement @guardian-queued-top-up", async ({ browser, request }) => {
  const token = await createOperatorToken(request);
  const headers = { "X-Operator-Key": token };
  const created = await request.post(`${API}/api/v1/operator/tables`, {
    headers,
    data: { name: fixtureName("Queued top-up cash") },
  });
  expect(created.ok()).toBeTruthy();
  const table = await created.json();

  const players: Array<{ user: string; sessionId: string; seat: number }> = [];
  for (const seat of [1, 2]) {
    const user = `${fixtureName("topup-queued-player")}-${seat}`;
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
        "Idempotency-Key": `topup-queued-join-${seat}`,
      },
      data: { seat_no: seat, stack: 10_000 },
    })).ok()).toBeTruthy();
    players.push({ user, sessionId: session.session_id, seat });
  }

  await expect.poll(async () => {
    const state = await (await request.get(
      `${API}/api/v1/tables/${table.id}`,
    )).json();
    return state.active_hand?.action_seat ?? null;
  }, { timeout: 10_000 }).not.toBeNull();

  const active = await (await request.get(
    `${API}/api/v1/tables/${table.id}`,
  )).json();
  const actor = players.find(
    (player) => player.seat === active.active_hand.action_seat,
  )!;
  const beforeStack = active.seats.find(
    (seat: any) => seat.player_id === actor.user,
  ).stack;

  const context = await browser.newContext();
  await context.addInitScript((id) => {
    localStorage.setItem("inarena_session_id", id);
  }, actor.sessionId);
  const actorPage = await context.newPage();
  await actorPage.goto("/");
  await actorPage.getByRole("button", { name: "ONLINE", exact: false }).click();
  await actorPage
    .locator(".lobby-card")
    .filter({ hasText: fixtureName("Queued top-up cash") })
    .getByRole("button", { name: "Открыть" })
    .click();

  await actorPage.getByRole("button", { name: "Пополнить стек" }).click();
  await actorPage.getByRole("button", { name: "+25 BB" }).click();
  await actorPage
    .getByRole("button", { name: /Добавить со следующей/ })
    .click();

  await expect.poll(async () => {
    const state = await (await request.get(
      `${API}/api/v1/tables/${table.id}`,
    )).json();
    const seat = state.seats.find((item: any) => item.player_id === actor.user);
    return {
      stack: seat?.stack ?? null,
      pending: seat?.pending_top_up ?? null,
    };
  }).toEqual({ stack: beforeStack, pending: 2_500 });

  await expect(
    actorPage.getByText(/Top-up \+2,?500 применится после раздачи/),
  ).toBeVisible();

  await actorPage.getByRole("button", { name: "Sit out", exact: true }).click();
  await expect(
    actorPage.getByRole("button", { name: "Sit out после раздачи" }),
  ).toBeVisible();
  await actorPage.getByRole("button", { name: "Fold" }).click();

  await expect.poll(async () => {
    const state = await (await request.get(
      `${API}/api/v1/tables/${table.id}`,
    )).json();
    const seat = state.seats.find((item: any) => item.player_id === actor.user);
    return {
      active: state.active_hand,
      status: seat?.status ?? null,
      stack: seat?.stack ?? null,
      pending: seat?.pending_top_up ?? null,
    };
  }, { timeout: 10_000 }).toEqual({
    active: null,
    status: "sitting_out",
    stack: beforeStack + 2_500,
    pending: 0,
  });

  const balance = await (await request.get(`${API}/api/v1/me/balance`, {
    headers: { "X-Session-ID": actor.sessionId },
  })).json();
  expect(balance.balance).toBe(17_500);

  await context.close();
});


test("cash MVP acceptance: showdown, reconnect, top-up, sit-out, return and exit @guardian-cash-acceptance", async ({ browser, request }) => {
  test.setTimeout(90_000);

  const token = await createOperatorToken(request);
  const headers = { "X-Operator-Key": token };
  const created = await request.post(`${API}/api/v1/operator/tables`, {
    headers,
    data: { name: fixtureName("Cash MVP acceptance") },
  });
  expect(created.ok()).toBeTruthy();
  const table = await created.json();

  const players: Array<{
    user: string;
    sessionId: string;
    seat: number;
  }> = [];

  for (const seat of [1, 2]) {
    const user = `${fixtureName("acceptance-player")}-${seat}`;
    expect((await request.post(`${API}/api/v1/operator/balance`, {
      headers,
      data: { user_id: user, delta: 30_000 },
    })).ok()).toBeTruthy();

    const session = await (await request.post(`${API}/api/v1/sessions`, {
      data: {
        user_id: user,
        provider: "test",
        data: { telegram_user: { first_name: `Player ${seat}` } },
      },
    })).json();

    expect((await request.post(`${API}/api/v1/tables/${table.id}/join-auth`, {
      headers: {
        "X-Session-ID": session.session_id,
        "Idempotency-Key": `acceptance-join-${seat}`,
      },
      data: { seat_no: seat, stack: 10_000 },
    })).ok()).toBeTruthy();

    players.push({
      user,
      sessionId: session.session_id,
      seat,
    });
  }

  const readState = async () =>
    (await (await request.get(`${API}/api/v1/tables/${table.id}`)).json());

  const playerForSeat = (seatNo: number) => {
    const player = players.find((item) => item.seat === seatNo);
    if (!player) throw new Error(`No session for seat ${seatNo}`);
    return player;
  };

  let actionCounter = 0;
  const actCurrent = async (
    action: "fold" | "check" | "call" | "bet" | "raise",
    amount?: number,
  ) => {
    const state = await readState();
    expect(state.active_hand).not.toBeNull();
    const actor = playerForSeat(state.active_hand.action_seat);
    const response = await request.post(
      `${API}/api/v1/tables/${table.id}/action-auth`,
      {
        headers: {
          "X-Session-ID": actor.sessionId,
          "Idempotency-Key": `acceptance-action-${++actionCounter}`,
        },
        data: {
          action,
          expected_action_no: Number(
            state.active_hand.state.action_no ?? 0,
          ),
          ...(amount === undefined ? {} : { amount }),
        },
      },
    );
    expect(response.ok()).toBeTruthy();
    return response.json();
  };

  await expect.poll(async () => {
    const state = await readState();
    return state.active_hand?.street ?? null;
  }, { timeout: 10_000 }).toBe("preflop");

  const firstHand = await readState();
  const firstHandId = firstHand.active_hand.hand_id;
  expect(firstHand.active_hand.pot).toBe(150);

  // Preflop: SB/button raises to 300, BB calls.
  await actCurrent("raise", 300);
  let state = await actCurrent("call");
  expect(state.active_hand.street).toBe("flop");
  expect(state.active_hand.pot).toBe(600);
  expect(state.active_hand.state.board).toHaveLength(3);

  // Flop: check, bet 200, call.
  await actCurrent("check");
  await actCurrent("bet", 200);
  state = await actCurrent("call");
  expect(state.active_hand.street).toBe("turn");
  expect(state.active_hand.pot).toBe(1_000);
  expect(state.active_hand.state.board).toHaveLength(4);

  // Turn: check/check.
  await actCurrent("check");
  state = await actCurrent("check");
  expect(state.active_hand.street).toBe("river");
  expect(state.active_hand.pot).toBe(1_000);
  expect(state.active_hand.state.board).toHaveLength(5);

  // River: bet 300/call -> automatic showdown settlement.
  await actCurrent("bet", 300);
  state = await actCurrent("call");
  expect(state.active_hand).toBeNull();

  const history = await (await request.get(
    `${API}/api/v1/tables/${table.id}/hands?limit=5`,
  )).json();
  expect(history[0].hand_id).toBe(firstHandId);
  expect(history[0].pot).toBe(1_600);
  expect(
    Object.values(history[0].final_stacks as Record<string, number>)
      .reduce((sum, value) => sum + Number(value), 0),
  ).toBe(20_000);

  // Automatic next hand.
  await expect.poll(async () => {
    const next = await readState();
    return next.active_hand?.hand_id ?? null;
  }, { timeout: 10_000 }).not.toBeNull();

  const secondHand = await readState();
  expect(secondHand.active_hand.hand_id).not.toBe(firstHandId);
  expect(secondHand.status).toBe("playing");
  expect(secondHand.active_hand.pot).toBe(150);

  // Private cards survive a real client reconnect.
  const reconnectPlayer = players[0];
  const openPlayerTable = async () => {
    const context = await browser.newContext();
    await context.addInitScript((sessionId) => {
      localStorage.setItem("inarena_session_id", sessionId);
    }, reconnectPlayer.sessionId);
    const page = await context.newPage();
    await page.goto("/");
    await page.getByRole("button", { name: "ONLINE", exact: false }).click();
    await page
      .locator(".lobby-card")
      .filter({ hasText: fixtureName("Cash MVP acceptance") })
      .getByRole("button", { name: "Открыть" })
      .click();
    await expect(
      page.getByRole("heading", { name: fixtureName("Cash MVP acceptance") }),
    ).toBeVisible();
    await expect(page.getByLabel("Ваши карты")).toBeVisible();
    return context;
  };

  const firstContext = await openPlayerTable();
  await firstContext.close();
  const secondContext = await openPlayerTable();
  await secondContext.close();

  const privateView = await (await request.get(
    `${API}/api/v1/tables/${table.id}/view`,
    { headers: { "X-Session-ID": reconnectPlayer.sessionId } },
  )).json();
  expect(privateView.hole_cards).toHaveLength(2);

  // Queue a top-up for the current actor, sit out after this hand, then fold.
  const current = await readState();
  const topUpActor = playerForSeat(current.active_hand.action_seat);
  const stackBeforeTopUp = current.seats.find(
    (seat: any) => seat.player_id === topUpActor.user,
  ).stack;

  const topUp = await request.post(
    `${API}/api/v1/tables/${table.id}/top-up-auth`,
    {
      headers: {
        "X-Session-ID": topUpActor.sessionId,
        "Idempotency-Key": "acceptance-topup",
      },
      data: { amount: 1_000 },
    },
  );
  expect(topUp.ok()).toBeTruthy();
  const queued = await topUp.json();
  const queuedSeat = queued.seats.find(
    (seat: any) => seat.player_id === topUpActor.user,
  );
  expect(queuedSeat.stack).toBe(stackBeforeTopUp);
  expect(queuedSeat.pending_top_up).toBe(1_000);

  const sitOut = await request.post(
    `${API}/api/v1/tables/${table.id}/sit-out-auth`,
    {
      headers: {
        "X-Session-ID": topUpActor.sessionId,
        "Idempotency-Key": "acceptance-sitout",
      },
    },
  );
  expect(sitOut.ok()).toBeTruthy();

  state = await actCurrent("fold");
  const afterFoldSeat = state.seats.find(
    (seat: any) => seat.player_id === topUpActor.user,
  );
  expect(state.active_hand).toBeNull();
  expect(afterFoldSeat.status).toBe("sitting_out");
  expect(afterFoldSeat.pending_top_up).toBe(0);
  expect(afterFoldSeat.stack).toBe(stackBeforeTopUp + 1_000);

  // Return to the game and verify the next hand starts again.
  const sitIn = await request.post(
    `${API}/api/v1/tables/${table.id}/sit-in-auth`,
    {
      headers: {
        "X-Session-ID": topUpActor.sessionId,
        "Idempotency-Key": "acceptance-sitin",
      },
    },
  );
  expect(sitIn.ok()).toBeTruthy();

  await expect.poll(async () => {
    const next = await readState();
    return next.active_hand?.hand_id ?? null;
  }, { timeout: 10_000 }).not.toBeNull();

  const thirdHand = await readState();
  expect(thirdHand.status).toBe("playing");

  // Current actor sits out, folds, then leaves the cash table cleanly.
  const exitPlayer = playerForSeat(thirdHand.active_hand.action_seat);
  expect((await request.post(
    `${API}/api/v1/tables/${table.id}/sit-out-auth`,
    {
      headers: {
        "X-Session-ID": exitPlayer.sessionId,
        "Idempotency-Key": "acceptance-exit-sitout",
      },
    },
  )).ok()).toBeTruthy();

  state = await actCurrent("fold");
  expect(state.active_hand).toBeNull();
  expect(
    state.seats.find((seat: any) => seat.player_id === exitPlayer.user)?.status,
  ).toBe("sitting_out");

  const stand = await request.post(
    `${API}/api/v1/tables/${table.id}/stand-auth`,
    {
      headers: {
        "X-Session-ID": exitPlayer.sessionId,
        "Idempotency-Key": "acceptance-stand",
      },
    },
  );
  expect(stand.ok()).toBeTruthy();
  const finalState = await stand.json();
  expect(
    finalState.seats.some(
      (seat: any) => seat.player_id === exitPlayer.user,
    ),
  ).toBe(false);
  expect(finalState.seats).toHaveLength(1);
  expect(finalState.active_hand).toBeNull();
  expect(finalState.status).toBe("open");
});


test("tables enforce fixed seven-max capacity @guardian-seven-max", async ({ request }) => {
  const token = await createOperatorToken(request);
  const headers = { "X-Operator-Key": token };
  const created = await request.post(`${API}/api/v1/operator/tables`, {
    headers,
    data: { name: fixtureName("Seven max contract") },
  });
  expect(created.ok()).toBeTruthy();
  const table = await created.json();

  const seatSeven = await request.post(
    `${API}/api/v1/tables/${table.id}/join`,
    {
      data: {
        player_id: fixtureName("seven-max-seat-7"),
        seat_no: 7,
        stack: 10_000,
      },
    },
  );
  expect(seatSeven.ok()).toBeTruthy();

  const seatEight = await request.post(
    `${API}/api/v1/tables/${table.id}/join`,
    {
      data: {
        player_id: fixtureName("seven-max-seat-8"),
        seat_no: 8,
        stack: 10_000,
      },
    },
  );
  expect(seatEight.status()).toBe(422);

  const state = await (
    await request.get(`${API}/api/v1/tables/${table.id}`)
  ).json();
  expect(state.max_seats).toBe(7);
  expect(state.seats).toHaveLength(1);
  expect(state.seats[0].seat_no).toBe(7);
  expect(state.seats.some((seat: any) => seat.seat_no > 7)).toBe(false);
});


test("table manager pauses and reopens a cash table @guardian-owner-lifecycle", async ({ page, request }) => {
  const token = await createOperatorToken(request);
  const headers = { "X-Operator-Key": token };
  const created = await request.post(`${API}/api/v1/operator/tables`, {
    headers,
    data: { name: fixtureName("Manager status cash") },
  });
  expect(created.ok()).toBeTruthy();

  await page.goto("/?operator=1");
  await page.getByPlaceholder("Bootstrap operator key").fill(BOOTSTRAP_KEY);
  await page.getByRole("button", { name: "Получить сессию" }).click();

  const card = page.locator(".operator-table-card").filter({
    hasText: fixtureName("Manager status cash"),
  });
  await expect(card).toBeVisible();

  await card.getByRole("button", { name: "Пауза" }).click();
  await expect(card.getByText("Пауза", { exact: true })).toBeVisible();

  await card.getByRole("button", { name: "Открыть стол" }).click();
  await expect(card.getByText("Открыт", { exact: true })).toBeVisible();

  const state = await (
    await request.get(`${API}/api/v1/tables/${(await created.json()).id}`)
  ).json();
  expect(state.status).toBe("open");
  expect(state.max_seats).toBe(7);
  await card.getByRole("button", { name: "Управление" }).click();
  await expect(card.getByLabel("Места за столом").locator(".manager-seat-dot")).toHaveCount(7);
  await card.getByRole("button", { name: "Закрыть стол" }).click();
  await expect(card.getByText("Закрыт", { exact: true })).toBeVisible();
  await expect(card.getByRole("button", { name: "Закрыть стол" })).toBeDisabled();
  const closed = await request.get(`${API}/api/v1/tables/${(await created.json()).id}`);
  expect((await closed.json()).status).toBe("closed");
  const dimensions = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.client);
});
