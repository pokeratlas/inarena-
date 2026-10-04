import { expect, test, type WebSocketRoute } from "@playwright/test";
import { expectUsableControls, measureJourney } from "./guardian-checks";

const API = "http://127.0.0.1:8000";

test("return restores a seat safely, waits for sync and preserves sit-out @guardian-return", async ({ page, request }) => {
  const suffix = `${test.info().project.name}-${test.info().retry}-${Date.now()}`;
  const name = `Return ${suffix}`;
  const user = `return-${suffix}`;
  const auth = await request.post(`${API}/api/v1/operator/auth`, { headers: { "X-Operator-Key": "fullstack-operator" }, data: { scopes: [] } });
  expect(auth.ok()).toBeTruthy();
  const operator = { "X-Operator-Key": (await auth.json()).token };
  const created = await request.post(`${API}/api/v1/operator/tables`, { headers: operator, data: { name } });
  expect(created.ok()).toBeTruthy();
  const table = await created.json();
  expect((await request.post(`${API}/api/v1/operator/balance`, { headers: operator, data: { user_id: user, delta: 20000 } })).ok()).toBeTruthy();
  const sessionResponse = await request.post(`${API}/api/v1/sessions`, { data: { user_id: user, provider: "test", data: {} } });
  expect(sessionResponse.ok()).toBeTruthy();
  const session = (await sessionResponse.json()).session_id;
  const headers = { "X-Session-ID": session };
  const joined = await request.post(`${API}/api/v1/tables/${table.id}/join-auth`, { headers, data: { seat_no: 1, stack: 5000 } });
  expect(joined.ok()).toBeTruthy();
  const balanceBeforeReturn = (await (await request.get(`${API}/api/v1/me/balance`, { headers })).json()).balance;

  let holdSync = true;
  const held: { socket: WebSocketRoute; message: string | Buffer }[] = [];
  await page.routeWebSocket(`**/ws/tables/${table.id}`, (socket) => {
    const server = socket.connectToServer();
    server.onMessage((message) => {
      if (holdSync) held.push({ socket, message });
      else socket.send(message);
    });
  });
  await page.addInitScript((id) => localStorage.setItem("inarena_session_id", id), session);
  await page.goto("/");
  await page.getByRole("button", { name: "ONLINE" }).click();
  const mine = page.getByRole("region", { name: "Ваши столы" });
  await expect(mine.getByText(name, { exact: true })).toBeVisible();
  const returnButton = mine.getByRole("button", { name: "Вернуться в игру", exact: true });
  await expectUsableControls(page, [returnButton]);
  await measureJourney("return", "return-to-table", async () => {
    await returnButton.click();
    await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
    await expect(page.getByText("Восстанавливаем связь со столом. Дождитесь обновления перед действием.", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Соединение активно", { exact: true })).toHaveCount(0);
    await expect.poll(() => held.length).toBeGreaterThan(0);
    holdSync = false;
    for (const item of held) item.socket.send(item.message);
    held.length = 0;
    await expect(page.getByLabel("Соединение активно", { exact: true })).toBeVisible();
  });
  await expect(page.getByText("ВЫ", { exact: true })).toBeVisible();
  const state = await (await request.get(`${API}/api/v1/tables/${table.id}`)).json();
  expect(state.seats).toEqual((await joined.json()).seats);
  expect((await (await request.get(`${API}/api/v1/me/balance`, { headers })).json()).balance).toBe(balanceBeforeReturn);

  // No active hand: reconnect feedback must still be visible without action buttons.
  await page.context().setOffline(true);
  await expect(page.getByText("Восстанавливаем связь со столом. Дождитесь обновления перед действием.", { exact: true })).toBeVisible();
  await page.context().setOffline(false);
  await expect(page.getByLabel("Соединение активно", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Sit out", exact: true }).click();
  await expect(page.getByRole("button", { name: "Вернуться в игру", exact: true })).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "ONLINE" }).click();
  await expect(mine.getByText("Вы в sit-out. Возвращение откроет стол; участие включается отдельно.", { exact: true })).toBeVisible();
  await returnButton.click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Вернуться в игру", exact: true })).toBeVisible();
  expect((await (await request.get(`${API}/api/v1/tables/${table.id}`)).json()).seats[0].status).toBe("sitting_out");
  const back = page.getByRole("button", { name: "← Лобби", exact: true });
  await expectUsableControls(page, [back]);
  await back.click();
  await expect(returnButton).toBeVisible();
  // Another device leaves after the lobby loaded. The shortcut must revalidate.
  expect((await request.post(`${API}/api/v1/tables/${table.id}/stand-auth`, { headers })).ok()).toBeTruthy();
  await returnButton.click();
  await expect(page.getByRole("alert").getByText("Место за этим столом больше недоступно. Выберите стол в лобби.", { exact: true })).toBeVisible();
  await expect(mine).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Игровой стол" })).toHaveCount(0);
});
