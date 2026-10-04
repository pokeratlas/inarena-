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
    if (!tableId) {
      setState(null);
      setConnected(false);
      return;
    }

    let disposed = false;
    let retryTimer: number | null = null;
    let pollTimer: number | null = null;
    let socket: WebSocket | null = null;
    lastSeq.current = 0;

    const applyMessage = (message: SocketMessage) => {
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
      const nextState = await getTable(tableId);
      if (!disposed) {
        setState((current) =>
          mergePublicSeatIdentity(current, nextState),
        );
      }
    };

    const connect = async () => {
      try {
        await refreshSnapshot();
        if (disposed) return;

        socket = new WebSocket(tableWebSocketUrl(tableId));
        socket.onopen = () => {
          setConnected(true);
          setError(null);
          socket?.send(
            JSON.stringify({ type: "sync", after_seq: lastSeq.current }),
          );
        };
        socket.onmessage = (event) => {
          applyMessage(JSON.parse(event.data) as SocketMessage);
        };
        socket.onerror = () => setError("Realtime connection error");
        socket.onclose = () => {
          setConnected(false);
          if (!disposed) {
            retryTimer = window.setTimeout(connect, 1500);
          }
        };
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Unknown error");
        if (!disposed) {
          retryTimer = window.setTimeout(connect, 1500);
        }
      }
    };

    void connect();
    pollTimer = window.setInterval(() => {
      void refreshSnapshot().catch(() => {
        // WebSocket remains the primary transport; polling is a safety net
        // for Telegram WebViews and transient mobile network gaps.
      });
    }, 1000);

    return () => {
      disposed = true;
      if (retryTimer !== null) window.clearTimeout(retryTimer);
      if (pollTimer !== null) window.clearInterval(pollTimer);
      socket?.close();
    };
  }, [tableId]);

  return {
    state,
    connected,
    error,
    lastSeq: lastSeq.current,
  };
}
