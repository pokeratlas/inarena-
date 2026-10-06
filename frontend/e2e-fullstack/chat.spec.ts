import { expect, test, type Page } from "@playwright/test";
import { expectUsableControls, measureJourney } from "./guardian-checks";

const API = "http://127.0.0.1:8000";

test("seated players exchange private chat, unread and reconnect history @guardian-table-chat", async ({ page, browser, request }) => {
  const suffix = `${test.info().project.name}-${test.info().retry}`;
  const name = `Chat ${suffix}`;
  const auth = await request.post(`${API}/api/v1/operator/auth`, { headers: { "X-Operator-Key": "fullstack-operator" }, data: { scopes: [] } });
  expect(auth.ok()).toBeTruthy();
  const headers = { "X-Operator-Key": (await auth.json()).token };
  const created = await request.post(`${API}/api/v1/operator/tables`, { headers, data: { name } });
  expect(created.ok()).toBeTruthy();
  const table = await created.json();
  const sessions: string[] = [];
  for (let seat = 1; seat <= 2; seat++) {
    const user = `chat-${suffix}-${seat}`;
    expect((await request.post(`${API}/api/v1/operator/balance`, { headers, data: { user_id: user, delta: 20000 } })).ok()).toBeTruthy();
    const sessionResponse = await request.post(`${API}/api/v1/sessions`, { data: { user_id: user, provider: "test", data: {} } });
    expect(sessionResponse.ok()).toBeTruthy();
    const session = (await sessionResponse.json()).session_id;
    sessions.push(session);
    expect((await request.post(`${API}/api/v1/tables/${table.id}/join-auth`, { headers: { "X-Session-ID": session }, data: { seat_no: seat, stack: 5000 } })).ok()).toBeTruthy();
  }
  async function enter(target: Page, session: string) {
    await target.addInitScript((id) => localStorage.setItem("inarena_session_id", id), session);
    await target.goto("/");
    await target.getByRole("button", { name: "ONLINE" }).click();
    await target.locator(".lobby-card").filter({ hasText: name }).getByRole("button", { name: "Открыть" }).click();
    await target.getByRole("button", { name: "Чат", exact: true }).click();
    await expect(target.getByText("Чат подключён", { exact: true })).toBeVisible();
  }
  const other = await browser.newContext();
  const second = await other.newPage();
  try {
    await enter(page, sessions[0]);
    await enter(second, sessions[1]);
    await page.getByLabel("Сообщение", { exact: true }).fill("Привет со стола <b>текст</b>");
    await expectUsableControls(page, [page.getByRole("button", { name: "Отправить", exact: true })]);
    await measureJourney("table-chat", "chat-message-delivered", async () => {
      await page.getByRole("button", { name: "Отправить", exact: true }).click();
      await expect(second.getByRole("log").getByText("Привет со стола <b>текст</b>", { exact: true })).toBeVisible();
    });
    await expect(page.getByLabel("Сообщение", { exact: true })).toHaveValue("");
    await expect(second.getByRole("log").locator("b")).toHaveCount(0);
    await page.getByRole("button", { name: "Чат", exact: true }).click();
    await second.getByLabel("Сообщение", { exact: true }).fill("Ответ игрока");
    await second.getByRole("button", { name: "Отправить", exact: true }).click();
    await expect(page.getByRole("button", { name: "Чат · 1 новых", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Чат · 1 новых", exact: true }).click();
    await expect(page.getByRole("log").getByText("Ответ игрока", { exact: true })).toBeVisible();
    await page.context().setOffline(true);
    await expect(page.getByText("Восстанавливаем связь с чатом…")).toBeVisible();
    await page.context().setOffline(false);
    await expect(page.getByText("Чат подключён", { exact: true })).toBeVisible();
    await page.reload();
    await page.getByRole("button", { name: "ONLINE" }).click();
    await page.locator(".lobby-card").filter({ hasText: name }).getByRole("button", { name: "Открыть" }).click();
    await page.getByRole("button", { name: "Чат", exact: true }).click();
    await expect(page.getByRole("log").getByText("Ответ игрока", { exact: true })).toBeVisible();
    await expect(page.getByRole("log").getByText("Привет со стола <b>текст</b>", { exact: true })).toHaveCount(1);
  } finally { await page.context().setOffline(false); await other.close(); }
});
