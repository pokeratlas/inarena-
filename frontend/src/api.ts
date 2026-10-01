import type { PlayerTableView, TableEvent, TableState } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export async function listTables(): Promise<TableState[]> {
  const response = await fetch(`${API_BASE}/api/v1/tables`);
  if (!response.ok) throw new Error("Unable to load tables");
  return response.json();
}

export async function getTable(tableId: string): Promise<TableState> {
  const response = await fetch(`${API_BASE}/api/v1/tables/${tableId}`);
  if (!response.ok) throw new Error("Unable to load table");
  return response.json();
}

export async function getEventsAfter(
  tableId: string,
  afterSeq: number,
): Promise<TableEvent[]> {
  const url = new URL(
    `${API_BASE}/api/v1/tables/${tableId}/events`,
    window.location.origin,
  );
  url.searchParams.set("after_seq", String(afterSeq));
  const response = await fetch(url);
  if (!response.ok) throw new Error("Unable to load table events");
  return response.json();
}

export function tableWebSocketUrl(tableId: string): string {
  const base = API_BASE || window.location.origin;
  const url = new URL(base);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = `/ws/tables/${tableId}`;
  url.search = "";
  return url.toString();
}


export interface AuthSession {
  session_id: string;
  user_id: string;
  provider: string;
  data: Record<string, unknown>;
  expires_at: string | null;
  updated_at: string;
}

export async function authenticateTelegram(
  initData: string,
): Promise<AuthSession> {
  const response = await fetch(`${API_BASE}/api/v1/auth/telegram`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ init_data: initData }),
  });
  if (!response.ok) throw new Error("Telegram authentication failed");
  return response.json();
}


export async function getPlayerTableView(
  tableId: string,
  sessionId: string,
): Promise<PlayerTableView> {
  const response = await fetch(`${API_BASE}/api/v1/tables/${tableId}/view`, {
    headers: { "X-Session-ID": sessionId },
  });
  if (!response.ok) throw new Error("Unable to load private table view");
  return response.json();
}

export async function joinAuthenticatedTable(
  tableId: string,
  sessionId: string,
  seatNo: number,
  stack: number,
): Promise<TableState> {
  const response = await fetch(
    `${API_BASE}/api/v1/tables/${tableId}/join-auth`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionId,
      },
      body: JSON.stringify({ seat_no: seatNo, stack }),
    },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "Unable to join table");
  }
  return response.json();
}

export async function submitPlayerAction(
  tableId: string,
  sessionId: string,
  payload: {
    action: "fold" | "check" | "call" | "bet" | "raise";
    expected_action_no: number;
    amount?: number;
  },
): Promise<TableState> {
  const response = await fetch(
    `${API_BASE}/api/v1/tables/${tableId}/action-auth`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionId,
      },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "Player action rejected");
  }
  return response.json();
}
