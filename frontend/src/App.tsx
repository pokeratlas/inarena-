import { useEffect, useMemo, useState } from "react";

import {
  type AuthSession,
  authenticateTelegram,
  getHandActions,
  getHandHistory,
  getMyHandHistory,
  getPlayerTableView,
  joinAuthenticatedTable,
  listTables,
  submitPlayerAction,
} from "./api";
import type { AppMode, HandActionEntry, HandHistoryEntry, PlayerHandHistoryEntry, TableState } from "./types";
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
  sessionId,
  connected,
}: {
  table: TableState;
  playerId: string | null;
  sessionId: string | null;
  connected: boolean;
}) {
  const [amount, setAmount] = useState(0);
  const [pending, setPending] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [nowEpoch, setNowEpoch] = useState(() => Math.floor(Date.now() / 1000));

  const hand = table.active_hand;

  useEffect(() => {
    const timer = window.setInterval(
      () => setNowEpoch(Math.floor(Date.now() / 1000)),
      250,
    );
    return () => window.clearInterval(timer);
  }, []);
  const playerSeat = useMemo(
    () => table.seats.find((seat) => seat.player_id === playerId) ?? null,
    [table.seats, playerId],
  );

  if (
    !hand ||
    !playerSeat ||
    !sessionId ||
    playerSeat.seat_no !== hand.action_seat
  ) {
    return null;
  }

  const actionNo = Number(hand.state.action_no ?? 0);
  const deadline = Number(hand.state.action_deadline_epoch ?? 0);
  const secondsLeft = deadline > 0 ? Math.max(0, deadline - nowEpoch) : null;
  const interactionLocked = pending || !connected || secondsLeft === 0;
  const currentBet = Number(hand.state.current_bet ?? 0);
  const contributions =
    (hand.state.contributions as Record<string, number> | undefined) ?? {};
  const contribution = Number(contributions[playerSeat.player_id] ?? 0);
  const facingBet = currentBet > contribution;
  const maxTarget = contribution + playerSeat.stack;
  const presetTargets = [
    { label: "1/2 Pot", value: Math.min(maxTarget, Math.max(currentBet + 1, currentBet + Math.ceil(hand.pot * 0.5))) },
    { label: "3/4 Pot", value: Math.min(maxTarget, Math.max(currentBet + 1, currentBet + Math.ceil(hand.pot * 0.75))) },
    { label: "Pot", value: Math.min(maxTarget, Math.max(currentBet + 1, currentBet + hand.pot)) },
    { label: "All-in", value: maxTarget },
  ];

  const act = async (
    action: "fold" | "check" | "call" | "bet" | "raise",
    actionAmount?: number,
  ) => {
    setPending(true);
    setActionError(null);
    try {
      await submitPlayerAction(table.id, sessionId, {
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
      <div className="action-meta">
        <p>Ваш ход · действие #{actionNo + 1}</p>
        <span className={connected ? "action-clock" : "action-clock reconnecting"}>
          {!connected
            ? "Reconnecting…"
            : secondsLeft === null
              ? "—"
              : `${secondsLeft}s`}
        </span>
      </div>
      <button className="action-button action-danger" disabled={interactionLocked} type="button" onClick={() => void act("fold")}>
        Fold
      </button>
      {facingBet ? (
        <button className="action-button" disabled={interactionLocked} type="button" onClick={() => void act("call")}>
          Call
        </button>
      ) : (
        <button className="action-button" disabled={interactionLocked} type="button" onClick={() => void act("check")}>
          Check
        </button>
      )}
      <div className="bet-presets" aria-label="Быстрый размер ставки">
        {presetTargets.map((preset) => (
          <button
            className="preset-button"
            key={preset.label}
            type="button"
            disabled={interactionLocked || preset.value <= currentBet}
            onClick={() => setAmount(preset.value)}
          >
            {preset.label}
          </button>
        ))}
      </div>
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
        disabled={interactionLocked || amount <= currentBet}
        type="button"
        onClick={() =>
          void act(currentBet > 0 ? "raise" : "bet", amount)
        }
      >
        {currentBet > 0 ? "Raise" : "Bet"}
      </button>
      {!connected ? (
        <p className="action-state" role="status">
          Соединение восстанавливается. Действия временно заблокированы.
        </p>
      ) : secondsLeft === 0 ? (
        <p className="action-state" role="status">
          Время хода истекло. Ожидаем обновление состояния стола.
        </p>
      ) : pending ? (
        <p className="action-state" role="status">
          Отправляем действие…
        </p>
      ) : null}
      {actionError ? <p role="alert">{actionError}</p> : null}
    </section>
  );
}

function OnlineTable({
  table,
  playerId,
  sessionId,
  connected,
  lastSeq,
  onBack,
}: {
  table: TableState;
  playerId: string | null;
  sessionId: string | null;
  connected: boolean;
  lastSeq: number;
  onBack: () => void;
}) {
  const [holeCards, setHoleCards] = useState<string[]>([]);
  const [history, setHistory] = useState<HandHistoryEntry[]>([]);
  const [historyActions, setHistoryActions] = useState<HandActionEntry[]>([]);
  const [myHistory, setMyHistory] = useState<PlayerHandHistoryEntry[]>([]);
  const handId = table.active_hand?.hand_id ?? null;

  useEffect(() => {
    if (!sessionId || !handId) {
      setHoleCards([]);
      return;
    }
    let active = true;
    getPlayerTableView(table.id, sessionId)
      .then((view) => {
        if (active) setHoleCards(view.hole_cards);
      })
      .catch(() => {
        if (active) setHoleCards([]);
      });
    return () => {
      active = false;
    };
  }, [table.id, sessionId, handId]);

  useEffect(() => {
    let active = true;
    getHandHistory(table.id, 5)
      .then((items) => {
        if (!active) return;
        setHistory(items);
        if (items[0]) {
          void getHandActions(table.id, items[0].hand_id).then((actions) => {
            if (active) setHistoryActions(actions);
          });
        } else {
          setHistoryActions([]);
        }
      })
      .catch(() => {
        if (active) {
          setHistory([]);
          setHistoryActions([]);
        }
      });
    return () => {
      active = false;
    };
  }, [table.id, handId]);

  useEffect(() => {
    if (!sessionId) {
      setMyHistory([]);
      return;
    }

    let active = true;
    getMyHandHistory(sessionId, 5)
      .then((items) => {
        if (active) setMyHistory(items);
      })
      .catch(() => {
        if (active) setMyHistory([]);
      });

    return () => {
      active = false;
    };
  }, [sessionId, handId]);

  const board =
    (table.active_hand?.state.board as string[] | undefined) ?? [];
  const buttonSeat = Number(table.active_hand?.state.button_seat ?? 0);
  const smallBlindSeat = Number(table.active_hand?.state.small_blind_seat ?? 0);
  const bigBlindSeat = Number(table.active_hand?.state.big_blind_seat ?? 0);
  const minRaise = Number(table.active_hand?.state.min_raise ?? 0);

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
            <div className="seat-badges">
              {seat.seat_no === buttonSeat ? <span>D</span> : null}
              {seat.seat_no === smallBlindSeat ? <span>SB</span> : null}
              {seat.seat_no === bigBlindSeat ? <span>BB</span> : null}
            </div>
            <p>{seat.player_id}</p>
            <p>{seat.stack} chips</p>
          </article>
        ))}
      </div>

      <div className="board-cards" aria-label="Общие карты">
        {board.length === 0 ? (
          <span className="card-placeholder">Board</span>
        ) : (
          board.map((card) => (
            <span className="playing-card" key={card}>{card}</span>
          ))
        )}
      </div>

      {holeCards.length > 0 ? (
        <div className="hole-cards" aria-label="Ваши карты">
          {holeCards.map((card) => (
            <span className="playing-card hero-card" key={card}>{card}</span>
          ))}
        </div>
      ) : null}

      <div className="hand-status">
        <p>Статус: {table.status}</p>
        {table.active_hand ? (
          <p>
            Blinds {String(table.active_hand.state.small_blind ?? "—")}/
            {String(table.active_hand.state.big_blind ?? "—")} · min raise {minRaise}
          </p>
        ) : null}
        <p>
          {table.active_hand
            ? `${table.active_hand.street} · pot ${table.active_hand.pot} · ход seat ${table.active_hand.action_seat}`
            : "Ожидание раздачи"}
        </p>
      </div>

      <PlayerActions
        table={table}
        playerId={playerId}
        sessionId={sessionId}
        connected={connected}
      />

      <section className="history-panel" aria-label="История раздач">
        <h3>Последняя раздача</h3>
        {history[0] ? (
          <>
            <p>Pot {history[0].pot}</p>
            <p>
              Выплаты: {Object.entries(history[0].payouts)
                .filter(([, value]) => value > 0)
                .map(([player, value]) => `${player} +${value}`)
                .join(" · ")}
            </p>
            <div className="history-actions">
              {historyActions.map((item) => (
                <span key={item.action_no}>
                  #{item.action_no} seat {item.seat_no} {item.action}
                  {item.amount === null ? "" : ` ${item.amount}`}
                </span>
              ))}
            </div>
          </>
        ) : (
          <p>Завершённых раздач пока нет.</p>
        )}

        {myHistory[0] ? (
          <div className="my-hand-history">
            <h4>Моя последняя раздача</h4>
            <p>
              Карты: {myHistory[0].hole_cards.join(" ")}
              {myHistory[0].board.length > 0
                ? ` · Board ${myHistory[0].board.join(" ")}`
                : ""}
            </p>
            <p>
              Payout +{myHistory[0].payout} · Stack {myHistory[0].final_stack}
            </p>
          </div>
        ) : null}
      </section>
    </section>
  );
}

function OnlineLobby({
  session,
  onTableScreenChange,
}: {
  session: AuthSession | null;
  onTableScreenChange: (open: boolean) => void;
}) {
  const playerId = session?.user_id ?? null;
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
          sessionId={session?.session_id ?? null}
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
          tables.map((table) => {
            const seated = table.seats.some(
              (seat) => seat.player_id === playerId,
            );
            const occupied = new Set(table.seats.map((seat) => seat.seat_no));
            const firstFreeSeat = Array.from(
              { length: 9 },
              (_, index) => index + 1,
            ).find((seatNo) => !occupied.has(seatNo));

            return (
              <article className="lobby-card" key={table.id}>
                <strong>{table.name}</strong>
                <span>
                  {table.status} · {table.seats.length} игроков
                </span>
                <div className="lobby-actions">
                  <button
                    className="ghost-button"
                    type="button"
                    onClick={() => {
                      setSelectedTableId(table.id);
                      setTableOpen(true);
                      onTableScreenChange(true);
                    }}
                  >
                    Открыть
                  </button>
                  {!seated && session && firstFreeSeat ? (
                    <button
                      className="action-button action-primary"
                      type="button"
                      onClick={() => {
                        void joinAuthenticatedTable(
                          table.id,
                          session.session_id,
                          firstFreeSeat,
                          10000,
                        )
                          .then((updated) => {
                            setTables((current) =>
                              current.map((item) =>
                                item.id === updated.id ? updated : item,
                              ),
                            );
                            setSelectedTableId(table.id);
                            setTableOpen(true);
                            onTableScreenChange(true);
                          })
                          .catch((cause) =>
                            setLoadingError(
                              cause instanceof Error
                                ? cause.message
                                : "Unable to join table",
                            ),
                          );
                      }}
                    >
                      Сесть · Seat {firstFreeSeat}
                    </button>
                  ) : null}
                </div>
              </article>
            );
          })
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
            session={telegram.session}
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
