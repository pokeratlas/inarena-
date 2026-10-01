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
    <div className="mode-switch" aria-label="Режим приложения">
      <button
        className="mode-button"
        type="button"
        aria-pressed={mode === "offline"}
        onClick={() => onChange("offline")}
      >
        Offline
      </button>
      <button
        className="mode-button"
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
    <section className="player-actions" aria-label="Действия игрока">
      <p>Ваш ход · действие #{actionNo + 1}</p>
      <button className="action-button action-danger" disabled={pending} type="button" onClick={() => void act("fold")}>
        Fold
      </button>
      {facingBet ? (
        <button className="action-button" disabled={pending} type="button" onClick={() => void act("call")}>
          Call
        </button>
      ) : (
        <button className="action-button" disabled={pending} type="button" onClick={() => void act("check")}>
          Check
        </button>
      )}
      <label className="bet-control">
        Ставка
        <input
          min={0}
          type="number"
          value={amount}
          onChange={(event) => setAmount(Number(event.target.value))}
        />
      </label>
      <button
        className="action-button action-primary"
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
  onBack,
}: {
  table: TableState;
  playerId: string | null;
  connected: boolean;
  lastSeq: number;
  onBack: () => void;
}) {
  return (
    <section className="table-screen" aria-label="Игровой стол">
      <header className="table-header">
        <button className="ghost-button" type="button" onClick={onBack}>← Лобби</button>
        <h2>{table.name}</h2>
        <p>
          {connected ? "Live" : "Reconnecting"} · seq {lastSeq}
        </p>
      </header>

      <div className="poker-table" aria-label="Места за столом">
        {table.seats.map((seat) => (
          <article className={seat.player_id === playerId ? "seat-card hero-seat" : "seat-card"} key={seat.seat_no}>
            <strong>
              Seat {seat.seat_no}
              {seat.player_id === playerId ? " · Вы" : ""}
            </strong>
            <p>{seat.player_id}</p>
            <p>{seat.stack} chips</p>
          </article>
        ))}
      </div>

      <div className="hand-status">
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
  onTableScreenChange,
}: {
  playerId: string | null;
  onTableScreenChange: (open: boolean) => void;
}) {
  const [tables, setTables] = useState<TableState[]>([]);
  const [selectedTableId, setSelectedTableId] = useState<string | null>(null);
  const [loadingError, setLoadingError] = useState<string | null>(null);
  const [tableOpen, setTableOpen] = useState(false);
  const realtime = useTableRealtime(tableOpen ? selectedTableId : null);

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

  if (tableOpen && realtime.state) {
    return (
      <main className="app-main table-main">
        <OnlineTable
          table={realtime.state}
          playerId={playerId}
          connected={realtime.connected}
          lastSeq={realtime.lastSeq}
          onBack={() => {
            setTableOpen(false);
            onTableScreenChange(false);
          }}
        />
      </main>
    );
  }

  return (
    <main className="app-main">
      <header className="app-header">
        <p>INARENA ONLINE</p>
        <h1>Лобби</h1>
      </header>

      {loadingError ? <p role="alert">{loadingError}</p> : null}
      {realtime.error ? <p role="status">{realtime.error}</p> : null}

      <section className="lobby-list" aria-label="Онлайн столы">
        {tables.length === 0 ? (
          <p>Активных столов пока нет.</p>
        ) : (
          tables.map((table) => (
            <button
              className="lobby-card"
              key={table.id}
              type="button"
              aria-pressed={selectedTableId === table.id}
              onClick={() => {
                setSelectedTableId(table.id);
                setTableOpen(true);
                onTableScreenChange(true);
              }}
            >
              <strong>{table.name}</strong>
              <span>
                {table.status} · {table.seats.length} игроков
              </span>
            </button>
          ))
        )}
      </section>

    </main>
  );
}

function OfflineHome() {
  return (
    <main className="app-main">
      <header className="app-header">
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
  const [tableScreenOpen, setTableScreenOpen] = useState(false);
  const tabs = mode === "online" ? onlineTabs : offlineTabs;

  return (
    <div className="app-shell">
      <div className="brand-row">
        <span className="brand-mark">INARENA</span>
        <span className="status-dot" aria-hidden="true" />
      </div>
      <ModeSwitch
        mode={mode}
        onChange={(nextMode) => {
          setMode(nextMode);
          setTableScreenOpen(false);
        }}
      />
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
          <OnlineLobby
            playerId={telegram.session?.user_id ?? null}
            onTableScreenChange={setTableScreenOpen}
          />
        </>
      ) : (
        <OfflineHome />
      )}
      {!tableScreenOpen ? (
        <nav className="bottom-nav" aria-label="Основная навигация">
          {tabs.map((tab) => (
            <button className="nav-item" type="button" key={tab}>
              {tab}
            </button>
          ))}
        </nav>
      ) : null}
    </div>
  );
}
