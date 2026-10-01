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
    let socket: WebSocket | null = null;

    const applyMessage = (message: SocketMessage) => {
      if (message.type === "table_snapshot") {
        lastSeq.current = Math.max(lastSeq.current, message.seq);
        setState(message.data);
        return;
      }

      if (message.type === "table_event") {
        if (message.seq <= lastSeq.current) return;
        lastSeq.current = message.seq;
        setState(message.data);
        return;
      }

      for (const event of message.events) {
        if (event.seq <= lastSeq.current) continue;
        lastSeq.current = event.seq;
        setState(event.payload);
      }
    };

    const connect = async () => {
      try {
        if (!state) {
          setState(await getTable(tableId));
        }
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

    return () => {
      disposed = true;
      if (retryTimer !== null) window.clearTimeout(retryTimer);
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
