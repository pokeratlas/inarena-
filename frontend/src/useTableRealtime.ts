import { useEffect, useRef, useState } from "react";

import { getTable, tableWebSocketUrl } from "./api";
import type { TableEvent, TableState } from "./types";

interface TableSnapshotMessage {
  type: "table_snapshot";
  seq: number;
  data: TableState;
}

interface TableEventMessage {
  type: "table_event";
  seq: number;
  event_type: string;
  data: TableState;
}

interface TableReplayMessage {
  type: "table_replay";
  events: TableEvent[];
}

type SocketMessage =
  | TableSnapshotMessage
  | TableEventMessage
  | TableReplayMessage;

function mergePublicSeatIdentity(
  previous: TableState | null,
  next: TableState,
): TableState {
  if (!previous) return next;
  const previousByPlayer = new Map(
    previous.seats.map((seat) => [seat.player_id, seat] as const),
  );
  return {
    ...next,
    seats: next.seats.map((seat) => {
      const previousSeat = previousByPlayer.get(seat.player_id);
      return {
        ...seat,
        display_name:
          seat.display_name ?? previousSeat?.display_name ?? null,
        photo_url:
          seat.photo_url ?? previousSeat?.photo_url ?? null,
        pending_top_up:
          seat.pending_top_up ?? previousSeat?.pending_top_up ?? 0,
      };
    }),
  };
}

export function useTableRealtime(tableId: string | null) {
  const [state, setState] = useState<TableState | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastSeq = useRef(0);

  useEffect(() => {
    setState(null);
    setConnected(false);
    setError(null);
    if (!tableId) {
      return;
    }

    let disposed = false;
    let retryTimer: number | null = null;
    let pollTimer: number | null = null;
    let syncTimer: number | null = null;
    let socket: WebSocket | null = null;
    let connecting = false;
    let revision = 0;
    const controller = new AbortController();
    lastSeq.current = 0;

    const applyMessage = (message: SocketMessage) => {
      revision += 1;
      if (message.type === "table_snapshot") {
        lastSeq.current = Math.max(lastSeq.current, message.seq);
        setState((current) =>
          mergePublicSeatIdentity(current, message.data),
        );
        return;
      }

      if (message.type === "table_event") {
        if (message.seq <= lastSeq.current) return;
        lastSeq.current = message.seq;
        setState((current) =>
          mergePublicSeatIdentity(current, message.data),
        );
        return;
      }

      for (const event of message.events) {
        if (event.seq <= lastSeq.current) continue;
        lastSeq.current = event.seq;
        setState((current) =>
          mergePublicSeatIdentity(current, event.payload),
        );
      }
    };

    const refreshSnapshot = async () => {
      const before = revision;
      const nextState = await getTable(tableId, AbortSignal.any([controller.signal, AbortSignal.timeout(5000)]));
      if (!disposed && revision === before) {
        setState((current) =>
          mergePublicSeatIdentity(current, nextState),
        );
      }
    };

    const connect = async () => {
      if (disposed || connecting || socket?.readyState === WebSocket.OPEN || socket?.readyState === WebSocket.CONNECTING) return;
      connecting = true;
      try {
        await refreshSnapshot();
        if (disposed) return;

        const currentSocket = new WebSocket(tableWebSocketUrl(tableId));
        socket = currentSocket;
        syncTimer = window.setTimeout(() => currentSocket.close(), 5000);
        currentSocket.onopen = () => {
          if (disposed || socket !== currentSocket) return;
          currentSocket.send(
            JSON.stringify({ type: "sync", after_seq: lastSeq.current }),
          );
        };
        currentSocket.onmessage = (event) => {
          if (disposed || socket !== currentSocket) return;
          try {
            applyMessage(JSON.parse(event.data) as SocketMessage);
            if (syncTimer !== null) window.clearTimeout(syncTimer);
            setConnected(true);
            setError(null);
          } catch {
            currentSocket.close();
          }
        };
        currentSocket.onerror = () => {
          if (!disposed && socket === currentSocket) {
            setConnected(false);
            setError("Не удалось обновить стол");
          }
        };
        currentSocket.onclose = () => {
          if (disposed || socket !== currentSocket) return;
          if (syncTimer !== null) window.clearTimeout(syncTimer);
          setConnected(false);
          retryTimer = window.setTimeout(connect, 1500);
        };
      } catch (cause) {
        if (disposed) return;
        setConnected(false);
        setError(cause instanceof Error ? cause.message : "Unknown error");
        if (!disposed) {
          retryTimer = window.setTimeout(connect, 1500);
        }
      } finally {
        connecting = false;
      }
    };

    const offline = () => {
      setConnected(false);
      socket?.close();
    };
    const online = () => {
      if (retryTimer !== null) window.clearTimeout(retryTimer);
      if (socket?.readyState === WebSocket.CLOSING) return;
      void connect();
    };
    window.addEventListener("offline", offline);
    window.addEventListener("online", online);

    void connect();
    pollTimer = window.setInterval(() => {
      void refreshSnapshot().catch(() => {
        // WebSocket remains the primary transport; polling is a safety net
        // for Telegram WebViews and transient mobile network gaps.
      });
    }, 1000);

    return () => {
      disposed = true;
      controller.abort();
      window.removeEventListener("offline", offline);
      window.removeEventListener("online", online);
      if (retryTimer !== null) window.clearTimeout(retryTimer);
      if (pollTimer !== null) window.clearInterval(pollTimer);
      if (syncTimer !== null) window.clearTimeout(syncTimer);
      socket?.close();
    };
  }, [tableId]);

  return {
    state: state?.id === tableId ? state : null,
    connected: state?.id === tableId && connected,
    error,
    lastSeq: lastSeq.current,
  };
}
