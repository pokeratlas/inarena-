import type { TableEvent, TableState } from "./types";

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
