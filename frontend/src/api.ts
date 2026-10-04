import type { CashWaitlistStatus, HandActionEntry, HandHistoryEntry, OperatorAuditEntry, OperatorDashboard, PlayerBalance, PlayerHandHistoryEntry, PlayerTableView, TableEvent, TableState, TournamentRegistration } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

function createIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function mutationHeaders(
  sessionId: string,
  idempotencyKey: string,
  json = false,
): Record<string, string> {
  return {
    ...(json ? { "Content-Type": "application/json" } : {}),
    "X-Session-ID": sessionId,
    "Idempotency-Key": idempotencyKey,
  };
}

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
  idempotencyKey = createIdempotencyKey(),
): Promise<TableState> {
  const response = await fetch(
    `${API_BASE}/api/v1/tables/${tableId}/join-auth`,
    {
      method: "POST",
      headers: mutationHeaders(sessionId, idempotencyKey, true),
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
  idempotencyKey = createIdempotencyKey(),
): Promise<TableState> {
  const response = await fetch(
    `${API_BASE}/api/v1/tables/${tableId}/action-auth`,
    {
      method: "POST",
      headers: mutationHeaders(sessionId, idempotencyKey, true),
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "Player action rejected");
  }
  return response.json();
}


export async function getHandHistory(
  tableId: string,
  limit = 10,
): Promise<HandHistoryEntry[]> {
  const url = new URL(
    `${API_BASE}/api/v1/tables/${tableId}/hands`,
    window.location.origin,
  );
  url.searchParams.set("limit", String(limit));
  const response = await fetch(url);
  if (!response.ok) throw new Error("Unable to load hand history");
  return response.json();
}

export async function getHandActions(
  tableId: string,
  handId: string,
): Promise<HandActionEntry[]> {
  const response = await fetch(
    `${API_BASE}/api/v1/tables/${tableId}/hands/${handId}/actions`,
  );
  if (!response.ok) throw new Error("Unable to load hand actions");
  return response.json();
}


export async function getMyHandHistory(
  sessionId: string,
  limit = 10,
): Promise<PlayerHandHistoryEntry[]> {
  const url = new URL(
    `${API_BASE}/api/v1/me/hands`,
    window.location.origin,
  );
  url.searchParams.set("limit", String(limit));
  const response = await fetch(url, {
    headers: { "X-Session-ID": sessionId },
  });
  if (!response.ok) throw new Error("Unable to load player hand history");
  return response.json();
}


export async function getCurrentSession(
  sessionId: string,
): Promise<AuthSession> {
  const response = await fetch(`${API_BASE}/api/v1/auth/session`, {
    headers: { "X-Session-ID": sessionId },
  });
  if (!response.ok) throw new Error("Session is invalid or expired");
  return response.json();
}

export async function refreshCurrentSession(
  sessionId: string,
): Promise<AuthSession> {
  const response = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { "X-Session-ID": sessionId },
  });
  if (!response.ok) throw new Error("Unable to refresh session");
  return response.json();
}


export async function topUpAuthenticated(
  tableId: string,
  sessionId: string,
  amount: number,
  idempotencyKey = createIdempotencyKey(),
): Promise<TableState> {
  const response = await fetch(
    `${API_BASE}/api/v1/tables/${tableId}/top-up-auth`,
    {
      method: "POST",
      headers: mutationHeaders(sessionId, idempotencyKey, true),
      body: JSON.stringify({ amount }),
    },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "Unable to top up stack");
  }
  return response.json();
}

export async function sitOutAuthenticated(
  tableId: string,
  sessionId: string,
  idempotencyKey = createIdempotencyKey(),
): Promise<TableState> {
  const response = await fetch(
    `${API_BASE}/api/v1/tables/${tableId}/sit-out-auth`,
    {
      method: "POST",
      headers: mutationHeaders(sessionId, idempotencyKey),
    },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "Unable to sit out");
  }
  return response.json();
}

export async function sitInAuthenticated(
  tableId: string,
  sessionId: string,
  idempotencyKey = createIdempotencyKey(),
): Promise<TableState> {
  const response = await fetch(
    `${API_BASE}/api/v1/tables/${tableId}/sit-in-auth`,
    {
      method: "POST",
      headers: mutationHeaders(sessionId, idempotencyKey),
    },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "Unable to sit in");
  }
  return response.json();
}

export async function standAuthenticated(
  tableId: string,
  sessionId: string,
  idempotencyKey = createIdempotencyKey(),
): Promise<TableState> {
  const response = await fetch(
    `${API_BASE}/api/v1/tables/${tableId}/stand-auth`,
    {
      method: "POST",
      headers: mutationHeaders(sessionId, idempotencyKey),
    },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "Unable to leave table");
  }
  return response.json();
}

export async function tournamentRebuy(
  tableId: string,
  sessionId: string,
  idempotencyKey = createIdempotencyKey(),
): Promise<TableState> {
  const response = await fetch(
    `${API_BASE}/api/v1/tables/${tableId}/rebuy`,
    {
      method: "POST",
      headers: mutationHeaders(sessionId, idempotencyKey),
    },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "Rebuy unavailable");
  }
  return response.json();
}

export async function tournamentAddon(
  tableId: string,
  sessionId: string,
  idempotencyKey = createIdempotencyKey(),
): Promise<TableState> {
  const response = await fetch(
    `${API_BASE}/api/v1/tables/${tableId}/addon`,
    {
      method: "POST",
      headers: mutationHeaders(sessionId, idempotencyKey),
    },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "Add-on unavailable");
  }
  return response.json();
}

export interface OperatorSession {
  token: string;
  scopes: string[];
  expires_at_epoch: number;
}

export async function authenticateOperator(
  bootstrapKey: string,
  scopes: string[] = [],
  rememberMe = false,
): Promise<OperatorSession> {
  const response = await fetch(`${API_BASE}/api/v1/operator/auth`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Operator-Key": bootstrapKey,
    },
    body: JSON.stringify({ scopes, remember_me: rememberMe }),
  });
  if (!response.ok) throw new Error("Operator authentication failed");
  return response.json();
}

export async function revokeOperatorSession(
  operatorToken: string,
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/v1/operator/auth/revoke`, {
    method: "POST",
    headers: { "X-Operator-Key": operatorToken },
  });
  if (!response.ok && response.status !== 204) {
    throw new Error("Unable to revoke operator session");
  }
}


export async function operatorCreateTable(name: string, operatorKey: string): Promise<TableState> {
  const response = await fetch(`${API_BASE}/api/v1/operator/tables`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Operator-Key": operatorKey },
    body: JSON.stringify({ name: name.trim() }),
  });
  if (response.status === 401) throw new Error("Operator session expired or unauthorized");
  if (!response.ok) throw new Error("Не удалось создать стол");
  return response.json();
}

export async function getOperatorDashboard(
  operatorKey: string,
): Promise<OperatorDashboard> {
  const response = await fetch(`${API_BASE}/api/v1/operator/dashboard`, {
    headers: { "X-Operator-Key": operatorKey },
  });
  if (response.status === 401) {
    throw new Error("Operator session expired or unauthorized");
  }
  if (!response.ok) throw new Error("Operator access denied");
  return response.json();
}

export async function operatorBlindScheduleCommand(
  tableId: string,
  command: "start" | "pause" | "reset",
  operatorKey: string,
): Promise<TableState> {
  const response = await fetch(
    `${API_BASE}/api/v1/operator/tables/${tableId}/blind-schedule/${command}`,
    {
      method: "POST",
      headers: { "X-Operator-Key": operatorKey },
    },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "Schedule command failed");
  }
  return response.json();
}


export async function getMyBalance(
  sessionId: string,
): Promise<PlayerBalance> {
  const response = await fetch(`${API_BASE}/api/v1/me/balance`, {
    headers: { "X-Session-ID": sessionId },
  });
  if (!response.ok) throw new Error("Unable to load chip balance");
  return response.json();
}

export async function operatorAdjustBalance(
  userId: string,
  delta: number,
  operatorKey: string,
): Promise<PlayerBalance> {
  const response = await fetch(`${API_BASE}/api/v1/operator/balance`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Operator-Key": operatorKey,
    },
    body: JSON.stringify({ user_id: userId, delta }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "Balance adjustment failed");
  }
  return response.json();
}

export async function operatorWindowControl(
  tableId: string,
  windowName: "rebuy" | "addon",
  open: boolean,
  operatorKey: string,
): Promise<TableState> {
  const response = await fetch(
    `${API_BASE}/api/v1/operator/tables/${tableId}/window/${windowName}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Operator-Key": operatorKey,
      },
      body: JSON.stringify({ open }),
    },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "Window control failed");
  }
  return response.json();
}

export async function operatorCloseTable(
  tableId: string,
  operatorKey: string,
): Promise<TableState> {
  const response = await fetch(
    `${API_BASE}/api/v1/operator/tables/${tableId}/close`,
    {
      method: "POST",
      headers: { "X-Operator-Key": operatorKey },
    },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "Unable to close table");
  }
  return response.json();
}

export async function getOperatorAudit(
  operatorKey: string,
  tableId?: string,
  limit = 30,
): Promise<OperatorAuditEntry[]> {
  const url = new URL(
    `${API_BASE}/api/v1/operator/audit`,
    window.location.origin,
  );
  url.searchParams.set("limit", String(limit));
  if (tableId) url.searchParams.set("table_id", tableId);
  const response = await fetch(url, {
    headers: { "X-Operator-Key": operatorKey },
  });
  if (response.status === 401) {
    throw new Error("Operator session expired or unauthorized");
  }
  if (!response.ok) throw new Error("Unable to load operator audit");
  return response.json();
}


export async function getTournamentRegistration(
  tableId: string,
  sessionId: string,
): Promise<TournamentRegistration> {
  const response = await fetch(
    `${API_BASE}/api/v1/tournaments/${tableId}/registration`,
    { headers: { "X-Session-ID": sessionId } },
  );
  if (!response.ok) throw new Error("Unable to load tournament registration");
  return response.json();
}

export async function registerTournament(
  tableId: string,
  sessionId: string,
  idempotencyKey = createIdempotencyKey(),
): Promise<TournamentRegistration> {
  const response = await fetch(
    `${API_BASE}/api/v1/tournaments/${tableId}/register`,
    {
      method: "POST",
      headers: mutationHeaders(sessionId, idempotencyKey),
    },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "Tournament registration failed");
  }
  return response.json();
}

export async function unregisterTournament(
  tableId: string,
  sessionId: string,
  idempotencyKey = createIdempotencyKey(),
): Promise<TournamentRegistration> {
  const response = await fetch(
    `${API_BASE}/api/v1/tournaments/${tableId}/register`,
    {
      method: "DELETE",
      headers: mutationHeaders(sessionId, idempotencyKey),
    },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "Unable to withdraw registration");
  }
  return response.json();
}

export async function operatorTournamentCommand(
  tableId: string,
  command: "open-registration" | "start" | "cancel",
  operatorKey: string,
): Promise<TableState> {
  const response = await fetch(
    `${API_BASE}/api/v1/operator/tables/${tableId}/tournament/${command}`,
    {
      method: "POST",
      headers: { "X-Operator-Key": operatorKey },
    },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "Tournament command failed");
  }
  return response.json();
}


export async function getCashWaitlistStatus(
  tableId: string,
  sessionId: string,
): Promise<CashWaitlistStatus> {
  const response = await fetch(
    `${API_BASE}/api/v1/tables/${tableId}/waitlist`,
    { headers: { "X-Session-ID": sessionId } },
  );
  if (!response.ok) throw new Error("Unable to load cash waitlist status");
  return response.json();
}

export async function joinCashWaitlist(
  tableId: string,
  sessionId: string,
  idempotencyKey = createIdempotencyKey(),
): Promise<CashWaitlistStatus> {
  const response = await fetch(
    `${API_BASE}/api/v1/tables/${tableId}/waitlist`,
    {
      method: "POST",
      headers: mutationHeaders(sessionId, idempotencyKey),
    },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "Unable to join waitlist");
  }
  return response.json();
}

export async function leaveCashWaitlist(
  tableId: string,
  sessionId: string,
  idempotencyKey = createIdempotencyKey(),
): Promise<CashWaitlistStatus> {
  const response = await fetch(
    `${API_BASE}/api/v1/tables/${tableId}/waitlist`,
    {
      method: "DELETE",
      headers: mutationHeaders(sessionId, idempotencyKey),
    },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "Unable to leave waitlist");
  }
  return response.json();
}

export async function claimSeatReservation(
  tableId: string,
  sessionId: string,
  reservationId: string,
  stack: number,
  idempotencyKey = createIdempotencyKey(),
): Promise<TableState> {
  const response = await fetch(
    `${API_BASE}/api/v1/tables/${tableId}/reservations/claim`,
    {
      method: "POST",
      headers: mutationHeaders(sessionId, idempotencyKey, true),
      body: JSON.stringify({
        reservation_id: reservationId,
        stack,
      }),
    },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "Unable to claim reserved seat");
  }
  return response.json();
}


export interface ReleaseMetadata {
  release: string;
  environment: string;
}

export async function getReleaseMetadata(): Promise<ReleaseMetadata> {
  const response = await fetch(`${API_BASE}/version`);
  if (!response.ok) throw new Error("Unable to load release metadata");
  return response.json();
}


export async function operatorStartHand(tableId: string, operatorKey: string): Promise<TableState> {
  const response = await fetch(`${API_BASE}/api/v1/operator/tables/${tableId}/start-hand`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Operator-Key": operatorKey },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "Не удалось начать раздачу");
  }
  return response.json();
}
