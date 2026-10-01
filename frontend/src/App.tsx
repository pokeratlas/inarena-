import { useEffect, useMemo, useState } from "react";

import {
  type AuthSession,
  authenticateTelegram,
  listTables,
  submitPlayerAction,
} from "./api";
import type { AppMode, TableState } from "./types";
import { useTableRealtime } from "./useTableRealtime";

const offlineTabs = ["Главная", "Турниры", "Профиль"];
const onlineTabs = ["Лобби", "Игры", "Профиль"];

function ModeSwitch({
  mode,
  onChange,
}: {
  mode: AppMode;
  onChange: (mode: AppMode) => void;
}) {
  return (
    <div aria-label="Режим приложения">
      <button
        type="button"
        aria-pressed={mode === "offline"}
        onClick={() => onChange("offline")}
      >
        Offline
      </button>
      <button
        type="button"
        aria-pressed={mode === "online"}
        onClick={() => onChange("online")}
      >
        Online
      </button>
    </div>
  );
}

function useTelegramSession() {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [status, setStatus] = useState<
    "idle" | "authenticating" | "authenticated" | "unavailable" | "error"
  >("idle");

  useEffect(() => {
    const webApp = window.Telegram?.WebApp;
    if (!webApp?.initData) {
      setStatus("unavailable");
      return;
    }

    webApp.ready();
    webApp.expand();
    setStatus("authenticating");

    authenticateTelegram(webApp.initData)
      .then((nextSession) => {
        setSession(nextSession);
        setStatus("authenticated");
        window.localStorage.setItem(
          "inarena_session_id",
          nextSession.session_id,
        );
      })
      .catch(() => setStatus("error"));
  }, []);

  return { session, status };
}

function PlayerActions({
  table,
  playerId,
}: {
  table: TableState;
  playerId: string | null;
}) {
  const [amount, setAmount] = useState(0);
  const [pending, setPending] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const hand = table.active_hand;
  const playerSeat = useMemo(
    () => table.seats.find((seat) => seat.player_id === playerId) ?? null,
    [table.seats, playerId],
  );

  if (!hand || !playerSeat || playerSeat.seat_no !== hand.action_seat) {
    return null;
  }

  const actionNo = Number(hand.state.action_no ?? 0);
  const currentBet = Number(hand.state.current_bet ?? 0);
  const contributions =
    (hand.state.contributions as Record<string, number> | undefined) ?? {};
  const contribution = Number(contributions[playerSeat.player_id] ?? 0);
  const facingBet = currentBet > contribution;

  const act = async (
    action: "fold" | "check" | "call" | "bet" | "raise",
    actionAmount?: number,
  ) => {
    setPending(true);
    setActionError(null);
    try {
      await submitPlayerAction(table.id, {
        player_id: playerSeat.player_id,
        action,
        expected_action_no: actionNo,
        ...(actionAmount === undefined ? {} : { amount: actionAmount }),
      });
    } catch (cause) {
      setActionError(
        cause instanceof Error ? cause.message : "Action rejected",
      );
    } finally {
      setPending(false);
    }
  };

  return (
    <section aria-label="Действия игрока">
      <p>Ваш ход · действие #{actionNo + 1}</p>
      <button disabled={pending} type="button" onClick={() => void act("fold")}>
        Fold
      </button>
      {facingBet ? (
        <button disabled={pending} type="button" onClick={() => void act("call")}>
          Call
        </button>
      ) : (
        <button disabled={pending} type="button" onClick={() => void act("check")}>
          Check
        </button>
      )}
      <label>
        Ставка
        <input
          min={0}
          type="number"
          value={amount}
          onChange={(event) => setAmount(Number(event.target.value))}
        />
      </label>
      <button
        disabled={pending || amount <= currentBet}
        type="button"
        onClick={() =>
          void act(currentBet > 0 ? "raise" : "bet", amount)
        }
      >
        {currentBet > 0 ? "Raise" : "Bet"}
      </button>
      {actionError ? <p role="alert">{actionError}</p> : null}
    </section>
  );
}

function OnlineTable({
  table,
  playerId,
  connected,
  lastSeq,
}: {
  table: TableState;
  playerId: string | null;
  connected: boolean;
  lastSeq: number;
}) {
  return (
    <section aria-label="Игровой стол">
      <header>
        <h2>{table.name}</h2>
        <p>
          {connected ? "Live" : "Reconnecting"} · seq {lastSeq}
        </p>
      </header>

      <div aria-label="Места за столом">
        {table.seats.map((seat) => (
          <article key={seat.seat_no}>
            <strong>
              Seat {seat.seat_no}
              {seat.player_id === playerId ? " · Вы" : ""}
            </strong>
            <p>{seat.player_id}</p>
            <p>{seat.stack} chips</p>
          </article>
        ))}
      </div>

      <div>
        <p>Статус: {table.status}</p>
        <p>
          {table.active_hand
            ? `${table.active_hand.street} · pot ${table.active_hand.pot} · ход seat ${table.active_hand.action_seat}`
            : "Ожидание раздачи"}
        </p>
      </div>

      <PlayerActions table={table} playerId={playerId} />
    </section>
  );
}

function OnlineLobby({
  playerId,
}: {
  playerId: string | null;
}) {
  const [tables, setTables] = useState<TableState[]>([]);
  const [selectedTableId, setSelectedTableId] = useState<string | null>(null);
  const [loadingError, setLoadingError] = useState<string | null>(null);
  const realtime = useTableRealtime(selectedTableId);

  useEffect(() => {
    let active = true;

    listTables()
      .then((nextTables) => {
        if (!active) return;
        setTables(nextTables);
        setSelectedTableId((current) => current ?? nextTables[0]?.id ?? null);
      })
      .catch((cause) => {
        if (!active) return;
        setLoadingError(
          cause instanceof Error ? cause.message : "Unable to load lobby",
        );
      });

    return () => {
      active = false;
    };
  }, []);

  return (
    <main>
      <header>
        <p>INARENA ONLINE</p>
        <h1>Лобби</h1>
      </header>

      {loadingError ? <p role="alert">{loadingError}</p> : null}
      {realtime.error ? <p role="status">{realtime.error}</p> : null}

      <section aria-label="Онлайн столы">
        {tables.length === 0 ? (
          <p>Активных столов пока нет.</p>
        ) : (
          tables.map((table) => (
            <button
              key={table.id}
              type="button"
              aria-pressed={selectedTableId === table.id}
              onClick={() => setSelectedTableId(table.id)}
            >
              <strong>{table.name}</strong>
              <span>
                {table.status} · {table.seats.length} игроков
              </span>
            </button>
          ))
        )}
      </section>

      {realtime.state ? (
        <OnlineTable
          table={realtime.state}
          playerId={playerId}
          connected={realtime.connected}
          lastSeq={realtime.lastSeq}
        />
      ) : null}
    </main>
  );
}

function OfflineHome() {
  return (
    <main>
      <header>
        <p>INARENA OFFLINE</p>
        <h1>Главная</h1>
      </header>
      <section>
        <p>Регистрация на офлайн-турниры и клубные события.</p>
      </section>
    </main>
  );
}

export default function App() {
  const [mode, setMode] = useState<AppMode>("offline");
  const telegram = useTelegramSession();
  const tabs = mode === "online" ? onlineTabs : offlineTabs;

  return (
    <div>
      <ModeSwitch mode={mode} onChange={setMode} />
      {mode === "online" ? (
        <>
          {telegram.status === "error" ? (
            <p role="alert">Telegram authentication failed.</p>
          ) : null}
          {telegram.status === "unavailable" ? (
            <p role="status">
              Откройте приложение внутри Telegram для действий от имени игрока.
            </p>
          ) : null}
          <OnlineLobby playerId={telegram.session?.user_id ?? null} />
        </>
      ) : (
        <OfflineHome />
      )}
      <nav aria-label="Основная навигация">
        {tabs.map((tab) => (
          <button type="button" key={tab}>
            {tab}
          </button>
        ))}
      </nav>
    </div>
  );
}
