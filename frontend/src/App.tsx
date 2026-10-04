import { useEffect, useMemo, useState } from "react";
import { TableChat } from "./TableChat";

import {
  type AuthSession,
  authenticateOperator,
  authenticateTelegram,
  claimSeatReservation,
  getCashWaitlistStatus,
  getOperatorAudit,
  getOperatorDashboard,
  getReleaseMetadata,
  getTournamentRegistration,
  getHandActions,
  getHandHistory,
  getMyBalance,
  getMyHandHistory,
  getPlayerTableView,
  getTable,
  refreshCurrentSession,
  revokeOperatorSession,
  joinAuthenticatedTable,
  joinCashWaitlist,
  operatorAdjustBalance,
  operatorBlindScheduleCommand,
  operatorCloseTable,
  operatorConfigureCashTable,
  operatorCreateTable,
  operatorSetTableStatus,
  operatorStartHand,
  operatorTournamentCommand,
  operatorWindowControl,
  leaveCashWaitlist,
  listTables,
  registerTournament,
  sitInAuthenticated,
  sitOutAuthenticated,
  standAuthenticated,
  submitPlayerAction,
  tournamentAddon,
  tournamentRebuy,
  topUpAuthenticated,
  unregisterTournament,
} from "./api";
import type { AppMode, CashWaitlistStatus, HandActionEntry, HandHistoryEntry, OperatorAuditEntry, OperatorDashboard, PlayerBalance, PlayerHandHistoryEntry, TableState, TournamentRegistration } from "./types";
import { useTableRealtime } from "./useTableRealtime";

const offlineTabs = ["Главная", "Турниры", "Профиль"];
const onlineTabs = ["Лобби", "Игра", "Профиль"];

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
    let active = true;
    const webApp = window.Telegram?.WebApp;

    // Telegram's native loading placeholder should disappear as soon as our
    // shell is mounted. Authentication may continue in the background.
    webApp?.ready();
    webApp?.expand();

    const persist = (nextSession: AuthSession) => {
      if (!active) return;
      setSession(nextSession);
      setStatus("authenticated");
      window.localStorage.setItem(
        "inarena_session_id",
        nextSession.session_id,
      );
    };

    const loginFromTelegram = async () => {
      if (!webApp?.initData) {
        if (active) setStatus("unavailable");
        return;
      }

      if (active) setStatus("authenticating");
      persist(await authenticateTelegram(webApp.initData));
    };

    const restore = async () => {
      const stored = window.localStorage.getItem("inarena_session_id");
      if (!stored) {
        await loginFromTelegram();
        return;
      }

      try {
        if (active) setStatus("authenticating");
        persist(await refreshCurrentSession(stored));
      } catch {
        window.localStorage.removeItem("inarena_session_id");
        await loginFromTelegram();
      }
    };

    void restore().catch(() => {
      if (active) setStatus("error");
    });

    return () => {
      active = false;
    };
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
  const playerSeat = useMemo(
    () => table.seats.find((seat) => seat.player_id === playerId) ?? null,
    [table.seats, playerId],
  );
  const currentBet = Number(hand?.state.current_bet ?? 0);
  const minRaise = Number(hand?.state.min_raise ?? table.big_blind);
  const streetContributions =
    (hand?.state.street_contributions as Record<string, number> | undefined) ?? {};
  const contribution = playerSeat
    ? Number(streetContributions[playerSeat.player_id] ?? 0)
    : 0;
  const maxTarget = playerSeat ? contribution + playerSeat.stack : 0;
  const minTarget = Math.min(
    maxTarget,
    currentBet === 0 ? minRaise : currentBet + minRaise,
  );

  useEffect(() => {
    const timer = window.setInterval(
      () => setNowEpoch(Math.floor(Date.now() / 1000)),
      250,
    );
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (
      !hand ||
      !playerSeat ||
      playerSeat.seat_no !== hand.action_seat ||
      maxTarget <= 0
    ) {
      return;
    }
    setAmount((current) =>
      current >= minTarget && current <= maxTarget
        ? current
        : minTarget,
    );
  }, [
    hand?.hand_id,
    hand?.state.action_no,
    playerSeat?.seat_no,
    hand?.action_seat,
    minTarget,
    maxTarget,
  ]);

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
  const facingBet = currentBet > contribution;
  const callAmount = Math.max(0, currentBet - contribution);
  const clampTarget = (target: number) =>
    Math.min(maxTarget, Math.max(minTarget, target));
  const presetTargets = [
    {
      label: "1/3",
      value: clampTarget(currentBet + Math.ceil(hand.pot / 3)),
    },
    {
      label: "1/2",
      value: clampTarget(currentBet + Math.ceil(hand.pot * 0.5)),
    },
    {
      label: "2/3",
      value: clampTarget(currentBet + Math.ceil((hand.pot * 2) / 3)),
    },
    {
      label: "Pot",
      value: clampTarget(currentBet + hand.pot),
    },
    { label: "All-in", value: maxTarget },
  ];

  const act = async (
    action: "fold" | "check" | "call" | "bet" | "raise",
    actionAmount?: number,
  ) => {
    if (
      actionAmount !== undefined &&
      actionAmount === maxTarget &&
      maxTarget > 0 &&
      !window.confirm("Подтвердить All-in?")
    ) {
      return;
    }
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

  const primaryLabel =
    amount === maxTarget && maxTarget > 0
      ? "All-in " + amount
      : currentBet > 0
        ? "Raise to " + amount
        : "Bet " + amount;

  return (
    <section className="player-actions player-actions-pro" aria-label="Действия игрока">
      <div className="action-meta">
        <div>
          <p>Ваш ход</p>
          <small>
            {facingBet ? "Нужно добавить " + callAmount : "Можно сделать check"}
          </small>
        </div>
        <span className={connected ? "action-clock" : "action-clock reconnecting"}>
          {!connected
            ? "Reconnecting…"
            : secondsLeft === null
              ? "—"
              : secondsLeft + "s"}
        </span>
      </div>

      <div className="primary-action-row">
        <button
          className="action-button action-danger"
          disabled={interactionLocked}
          type="button"
          onClick={() => void act("fold")}
        >
          Fold
        </button>
        {facingBet ? (
          <button
            className="action-button action-call"
            disabled={interactionLocked}
            type="button"
            onClick={() => void act("call")}
          >
            Call {callAmount}
          </button>
        ) : (
          <button
            className="action-button action-call"
            disabled={interactionLocked}
            type="button"
            onClick={() => void act("check")}
          >
            Check
          </button>
        )}
      </div>

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

      <label className="bet-slider">
        <span>
          Размер
          <strong>{amount}</strong>
        </span>
        <input
          aria-label="Размер ставки"
          min={minTarget}
          max={Math.max(minTarget, maxTarget)}
          step={1}
          type="range"
          value={Math.min(Math.max(amount, minTarget), Math.max(minTarget, maxTarget))}
          disabled={interactionLocked || maxTarget <= currentBet}
          onChange={(event) => setAmount(Number(event.target.value))}
        />
      </label>

      <button
        className="action-button action-primary action-raise"
        disabled={
          interactionLocked ||
          amount <= currentBet ||
          amount > maxTarget
        }
        type="button"
        onClick={() =>
          void act(currentBet > 0 ? "raise" : "bet", amount)
        }
      >
        {primaryLabel}
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

function TablePolicyControls({
  table,
  playerId,
  sessionId,
  onChanged,
  onLeave,
}: {
  table: TableState;
  playerId: string | null;
  sessionId: string | null;
  onChanged: () => void;
  onLeave: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [leaveAfterHand, setLeaveAfterHand] = useState(false);
  const [topUpOpen, setTopUpOpen] = useState(false);
  const [topUpAmount, setTopUpAmount] = useState(0);
  const [topUpBalance, setTopUpBalance] = useState<number | null>(null);
  const seat = table.seats.find((item) => item.player_id === playerId) ?? null;

  useEffect(() => {
    if (
      !leaveAfterHand ||
      table.active_hand ||
      table.table_mode !== "cash" ||
      !seat ||
      !sessionId ||
      pending
    ) {
      return;
    }

    let active = true;
    setPending(true);
    setError(null);
    void standAuthenticated(table.id, sessionId)
      .then(() => {
        if (!active) return;
        setLeaveAfterHand(false);
        onLeave();
      })
      .catch((cause) => {
        if (!active) return;
        setError(cause instanceof Error ? cause.message : "Operation failed");
      })
      .finally(() => {
        if (active) setPending(false);
      });

    return () => {
      active = false;
    };
  }, [
    leaveAfterHand,
    table.active_hand,
    table.id,
    table.table_mode,
    seat,
    sessionId,
    pending,
    onLeave,
  ]);

  if (!seat || !sessionId) return null;

  const run = async (operation: () => Promise<TableState>) => {
    setPending(true);
    setError(null);
    try {
      await operation();
      onChanged();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Operation failed");
    } finally {
      setPending(false);
    }
  };

  const topUpRoom = seat
    ? Math.max(
        0,
        table.cash_buyin_max -
          seat.stack -
          Number(seat.pending_top_up ?? 0),
      )
    : 0;
  const topUpAvailable = Math.min(
    topUpRoom,
    Math.max(0, topUpBalance ?? 0),
  );

  const openTopUp = async () => {
    if (!seat || !sessionId) return;
    setPending(true);
    setError(null);
    try {
      const nextBalance = await getMyBalance(sessionId);
      const available = Math.min(
        topUpRoom,
        Math.max(0, nextBalance.balance),
      );
      setTopUpBalance(nextBalance.balance);
      setTopUpAmount(
        available > 0
          ? Math.min(available, Math.max(table.big_blind * 25, 1))
          : 0,
      );
      setTopUpOpen(true);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Не удалось загрузить баланс",
      );
    } finally {
      setPending(false);
    }
  };

  const submitTopUp = async () => {
    if (!seat || !sessionId || topUpAmount <= 0) return;
    await run(async () => {
      const state = await topUpAuthenticated(
        table.id,
        sessionId,
        topUpAmount,
      );
      const nextBalance = await getMyBalance(sessionId);
      setTopUpBalance(nextBalance.balance);
      setTopUpOpen(false);
      return state;
    });
  };

  return (
    <section className="policy-actions" aria-label="Управление участием">
      {table.table_mode === "tournament" ? (
        table.active_hand ? null : (
          <>
            {seat.status === "eliminated" &&
            table.rebuy_enabled &&
            table.rebuy_window_open &&
            seat.rebuy_count < table.rebuy_max_per_player ? (
              <button
                className="action-button action-primary"
                disabled={pending}
                type="button"
                onClick={() =>
                  void run(() => tournamentRebuy(table.id, sessionId))
                }
              >
                Rebuy +{table.rebuy_stack}
              </button>
            ) : null}
            {seat.status === "seated" &&
            table.addon_enabled &&
            table.addon_window_open &&
            seat.addon_used === 0 ? (
              <button
                className="action-button"
                disabled={pending}
                type="button"
                onClick={() =>
                  void run(() => tournamentAddon(table.id, sessionId))
                }
              >
                Add-on +{table.addon_stack}
              </button>
            ) : null}
          </>
        )
      ) : (
        <>
          <button
            className="action-button"
            disabled={pending || topUpRoom <= 0}
            type="button"
            onClick={() => void openTopUp()}
          >
            {topUpRoom <= 0 ? "Стек на максимуме" : "Пополнить стек"}
          </button>

          {seat.pending_top_up > 0 ? (
            <p className="action-state topup-pending" role="status">
              Top-up +{seat.pending_top_up.toLocaleString()} применится после раздачи.
            </p>
          ) : null}

          {topUpOpen ? (
            <section className="topup-panel" aria-label="Пополнение стека">
              <div className="topup-head">
                <div>
                  <span>TOP-UP</span>
                  <strong>+{topUpAmount.toLocaleString()} chips</strong>
                </div>
                <small>
                  Баланс {(topUpBalance ?? 0).toLocaleString()}
                </small>
              </div>

              <div className="topup-copy">
                <span>
                  Стек {seat.stack.toLocaleString()}
                  {seat.pending_top_up > 0
                    ? " + " + seat.pending_top_up.toLocaleString() + " pending"
                    : ""}
                </span>
                <span>Max {table.cash_buyin_max.toLocaleString()}</span>
              </div>

              <div className="topup-presets">
                <button
                  type="button"
                  disabled={topUpAvailable <= 0}
                  onClick={() =>
                    setTopUpAmount(
                      Math.min(topUpAvailable, table.big_blind * 25),
                    )
                  }
                >
                  +25 BB
                </button>
                <button
                  type="button"
                  disabled={topUpAvailable <= 0}
                  onClick={() =>
                    setTopUpAmount(
                      Math.min(topUpAvailable, table.big_blind * 50),
                    )
                  }
                >
                  +50 BB
                </button>
                <button
                  type="button"
                  disabled={topUpAvailable <= 0}
                  onClick={() => setTopUpAmount(topUpAvailable)}
                >
                  До Max
                </button>
              </div>

              <input
                aria-label="Top-up amount"
                type="range"
                min={topUpAvailable > 0 ? 1 : 0}
                max={Math.max(1, topUpAvailable)}
                step={1}
                value={Math.min(
                  Math.max(topUpAmount, topUpAvailable > 0 ? 1 : 0),
                  Math.max(1, topUpAvailable),
                )}
                disabled={pending || topUpAvailable <= 0}
                onChange={(event) =>
                  setTopUpAmount(Number(event.target.value))
                }
              />

              <div className="topup-actions">
                <button
                  className="ghost-button"
                  type="button"
                  disabled={pending}
                  onClick={() => setTopUpOpen(false)}
                >
                  Отмена
                </button>
                <button
                  className="action-button action-primary"
                  type="button"
                  disabled={
                    pending ||
                    topUpAmount <= 0 ||
                    topUpAmount > topUpAvailable
                  }
                  onClick={() => void submitTopUp()}
                >
                  {table.active_hand
                    ? "Добавить со следующей · " +
                      topUpAmount.toLocaleString()
                    : "Добавить · " + topUpAmount.toLocaleString()}
                </button>
              </div>
            </section>
          ) : null}

          {seat.status === "seated" ? (
            <button
              className="action-button"
              disabled={pending}
              type="button"
              onClick={() =>
                void run(() => sitOutAuthenticated(table.id, sessionId))
              }
            >
              Sit out
            </button>
          ) : seat.status === "sitting_out_next" ? (
            <button className="action-button" disabled type="button">
              Sit out после раздачи
            </button>
          ) : seat.status === "sitting_in_next" ? (
            <button className="action-button" disabled type="button">
              Вернётесь со следующей
            </button>
          ) : (
            <button
              className="action-button action-primary"
              disabled={pending}
              type="button"
              onClick={() =>
                void run(() => sitInAuthenticated(table.id, sessionId))
              }
            >
              Вернуться в игру
            </button>
          )}

          <button
            className="action-button"
            disabled={pending || leaveAfterHand}
            type="button"
            onClick={() => {
              if (table.active_hand) {
                setLeaveAfterHand(true);
                setError(null);
                return;
              }
              void run(async () => {
                const state = await standAuthenticated(table.id, sessionId);
                onLeave();
                return state;
              });
            }}
          >
            {leaveAfterHand ? "Выход после раздачи…" : "Покинуть стол"}
          </button>

          {seat.status === "sitting_out" ? (
            <p className="action-state" role="status">
              Вы пропускаете раздачи. Место и chips сохранены.
            </p>
          ) : seat.status === "sitting_out_next" ? (
            <p className="action-state" role="status">
              Текущую раздачу доигрываете, следующую пропустите.
            </p>
          ) : seat.status === "sitting_in_next" ? (
            <p className="action-state" role="status">
              Вы вернётесь за стол со следующей раздачи.
            </p>
          ) : null}

          {table.active_hand && leaveAfterHand ? (
            <p className="action-state" role="status">
              Вы покинете стол сразу после текущей раздачи.
            </p>
          ) : null}
        </>
      )}
      {error ? <p role="alert">{error}</p> : null}
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
  const [infoOpen, setInfoOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
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
  const heroSeat =
    table.seats.find((seat) => seat.player_id === playerId) ?? null;
  const opponents = table.seats
    .filter((seat) => seat.player_id !== playerId)
    .slice()
    .sort((left, right) => left.seat_no - right.seat_no);
  const actionSeat = table.active_hand?.action_seat ?? null;
  const potChips = table.active_hand?.pot ?? 0;
  const formatBb = (chips: number) => {
    const blinds = table.big_blind > 0 ? chips / table.big_blind : 0;
    const rounded = Number.isInteger(blinds) ? String(blinds) : blinds.toFixed(1);
    return rounded + " BB";
  };

  const seatBadges = (seatNo: number) => (
    <div className="seat-badges">
      {seatNo === buttonSeat ? <span>D</span> : null}
      {seatNo === smallBlindSeat ? <span>SB</span> : null}
      {seatNo === bigBlindSeat ? <span>BB</span> : null}
    </div>
  );

  const renderCards = (cards: string[], hero = false) =>
    cards.map((card) => {
      const rank = card.slice(0, -1);
      const suitCode = card.slice(-1);
      const suitMap: Record<string, string> = {
        c: "♣",
        d: "♦",
        h: "♥",
        s: "♠",
      };
      const isRed = suitCode === "d" || suitCode === "h";
      return (
        <span
          className={[
            "playing-card",
            hero ? "hero-card" : "",
            isRed ? "card-red" : "card-black",
          ].filter(Boolean).join(" ")}
          key={card}
          aria-label={card}
        >
          <span className="card-rank">{rank}</span>
          <span className="card-suit" aria-hidden="true">
            {suitMap[suitCode] ?? suitCode}
          </span>
        </span>
      );
    });

  return (
    <section className="table-screen table-screen-redesign table-screen-v2" aria-label="Игровой стол">
      <header className="table-header table-header-redesign">
        <button className="table-back" type="button" onClick={onBack}>
          ← Лобби
        </button>
        <div className="table-title-block">
          <span className="table-kicker">INARENA CASH</span>
          <h2>{table.name}</h2>
          <span className="table-limit">
            {table.small_blind}/{table.big_blind}
          </span>
        </div>
        <div className="table-header-actions">
          <button
            className="table-icon-button table-history-button"
            type="button"
            aria-label="История рук"
            aria-expanded={historyOpen}
            onClick={() => setHistoryOpen(true)}
          >
            ≡
          </button>
          <button
            className="table-icon-button"
            type="button"
            aria-label="Информация о столе"
            aria-expanded={infoOpen}
            onClick={() => setInfoOpen((value) => !value)}
          >
            i
          </button>
          <span
            className={connected ? "live-pill" : "live-pill reconnecting"}
            aria-label={connected ? "Соединение активно" : "Переподключение"}
          >
            <i />
            {connected ? "LIVE" : "RECONNECT"}
          </span>
        </div>
      </header>

      {infoOpen ? (
        <section className="table-info-strip" aria-label="Информация о столе">
          <span><strong>{table.max_seats}-MAX</strong> формат</span>
          <span><strong>{table.small_blind}/{table.big_blind}</strong> blinds</span>
          <span><strong>{table.seats.length}/{table.max_seats}</strong> игроков</span>
          <span><strong>{table.status.toUpperCase()}</strong> статус</span>
        </section>
      ) : null}

      {!connected && (
        <p className="table-connection-state" role="status">
          Восстанавливаем связь со столом. Дождитесь обновления перед действием.
        </p>
      )}

      <section
        className="game-stage game-stage-v2"
        data-opponents={opponents.length}
        aria-label="Стол INARENA"
      >
        <div className="felt-table felt-table-v2">
          <div className="table-brand">INARENA</div>
          <div className="pot-display pot-display-v2">
            <small>ОБЩИЙ БАНК</small>
            <strong>{formatBb(potChips)}</strong>
            <span>{potChips.toLocaleString()} chips</span>
          </div>

          <div className="board-cards board-cards-redesign" aria-label="Общие карты">
            {board.length > 0
              ? renderCards(board)
              : Array.from({ length: 5 }, (_, index) => (
                  <span
                    className="card-slot"
                    key={"board-slot-" + index}
                    aria-hidden="true"
                  />
                ))}
          </div>

          <div className="street-label">
            {table.active_hand
              ? String(table.active_hand.street).toUpperCase()
              : "WAITING"}
          </div>
        </div>

        <div className="opponent-layer" data-count={opponents.length}>
          {opponents.map((seat, index) => (
            <article
              className={[
                "player-pod",
                "opponent-pod",
                "opponent-seat",
                "opponent-seat-" + index,
                seat.seat_no === actionSeat ? "is-acting" : "",
              ].filter(Boolean).join(" ")}
              key={seat.seat_no}
              aria-label={"Игрок " + (seat.display_name ?? seat.seat_no)}
            >
              <div className="player-pod-top">
                {seat.photo_url ? (
                  <img
                    className="player-avatar player-avatar-photo"
                    src={seat.photo_url}
                    alt=""
                    referrerPolicy="no-referrer"
                  />
                ) : (
                  <span className="player-avatar">
                    {(seat.display_name?.trim()?.[0] ?? "P").toUpperCase()}
                  </span>
                )}
                <div className="player-stack-block">
                  <strong>{seat.display_name ?? "Игрок " + seat.seat_no}</strong>
                  <b>{formatBb(seat.stack)}</b>
                  <small>{seat.stack.toLocaleString()} chips</small>
                </div>
              </div>
              {seatBadges(seat.seat_no)}
            </article>
          ))}
        </div>

        {heroSeat ? (
          <article
            className={[
              "player-pod",
              "hero-player-pod",
              heroSeat.seat_no === actionSeat ? "is-acting" : "",
            ].filter(Boolean).join(" ")}
            aria-label="Ваше место"
          >
            <div className="hero-player-info">
              {heroSeat.photo_url ? (
                <img
                  className="player-avatar player-avatar-photo hero-avatar"
                  src={heroSeat.photo_url}
                  alt=""
                  referrerPolicy="no-referrer"
                />
              ) : (
                <span className="player-avatar hero-avatar">
                  {(heroSeat.display_name?.trim()?.[0] ?? "Я").toUpperCase()}
                </span>
              )}
              <div className="hero-identity">
                <span className="hero-label">ВЫ</span>
                <strong>{heroSeat.display_name ?? "Игрок"}</strong>
                <b>{formatBb(heroSeat.stack)}</b>
                <small>{heroSeat.stack.toLocaleString()} chips</small>
              </div>
              {seatBadges(heroSeat.seat_no)}
            </div>

            <div className="hole-cards hole-cards-redesign" aria-label="Ваши карты">
              {holeCards.length > 0
                ? renderCards(holeCards, true)
                : (
                  <>
                    <span className="card-back" />
                    <span className="card-back" />
                  </>
                )}
            </div>
          </article>
        ) : null}
      </section>

      <div className="game-message" role="status">
        {!table.active_hand
          ? "Ожидание следующей раздачи"
          : heroSeat?.seat_no === actionSeat
            ? "Ваш ход"
            : "Ход игрока " + (actionSeat ?? "—")}
      </div>

      <PlayerActions
        table={table}
        playerId={playerId}
        sessionId={sessionId}
        connected={connected}
      />

      <div id="table-controls">
      <TablePolicyControls
        table={table}
        playerId={playerId}
        sessionId={sessionId}
        onChanged={() => {
          // Table mutations are delivered through realtime/polling.
          // Keep the player on the table instead of reloading the mini-app.
        }}
        onLeave={onBack}
      />
      </div>

      {sessionId && playerId && table.seats.some((seat) => seat.player_id === playerId) && (
        <div id="table-chat-dock">
          <TableChat key={table.id + sessionId} tableId={table.id} sessionId={sessionId} playerId={playerId} />
        </div>
      )}

      {historyOpen ? (
        <div
          className="table-drawer-backdrop"
          role="presentation"
          onClick={() => setHistoryOpen(false)}
        >
          <aside
            className="table-history-drawer"
            role="dialog"
            aria-modal="true"
            aria-label="История рук"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="table-drawer-handle" aria-hidden="true" />
            <header className="table-drawer-header">
              <div>
                <span>ИГРА</span>
                <h3>История рук</h3>
              </div>
              <button
                className="table-drawer-close"
                type="button"
                aria-label="Закрыть историю"
                onClick={() => setHistoryOpen(false)}
              >
                ×
              </button>
            </header>

            {history[0] ? (
              <>
                <section className="history-hand-summary" aria-label="Последняя раздача">
                  <div>
                    <span>POT</span>
                    <strong>{formatBb(history[0].pot)}</strong>
                    <small>{history[0].pot.toLocaleString()} chips</small>
                  </div>
                  {myHistory[0] ? (
                    <div className="history-my-cards">
                      <span>МОИ КАРТЫ</span>
                      <strong>{myHistory[0].hole_cards.join(" ")}</strong>
                    </div>
                  ) : null}
                </section>

                {myHistory[0]?.board.length ? (
                  <p className="history-board">
                    Board · {myHistory[0].board.join(" ")}
                  </p>
                ) : null}

                <div className="history-actions history-actions-drawer" aria-label="Действия раздачи">
                  {historyActions.length > 0 ? historyActions.map((item) => (
                    <article key={item.action_no}>
                      <span>#{item.action_no}</span>
                      <strong>Seat {item.seat_no}</strong>
                      <b>{item.action}</b>
                      <small>{item.amount === null ? "—" : item.amount.toLocaleString()}</small>
                    </article>
                  )) : (
                    <p>Действия этой раздачи ещё не записаны.</p>
                  )}
                </div>

                {history.length > 1 ? (
                  <section className="history-recent-list" aria-label="Недавние раздачи">
                    <span>НЕДАВНИЕ</span>
                    {history.slice(1, 5).map((hand) => (
                      <article key={hand.hand_id}>
                        <strong>{formatBb(hand.pot)}</strong>
                        <small>{hand.pot.toLocaleString()} chips</small>
                      </article>
                    ))}
                  </section>
                ) : null}
              </>
            ) : (
              <p className="history-empty">Завершённых раздач пока нет.</p>
            )}
          </aside>
        </div>
      ) : null}
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
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);
  const [loadingError, setLoadingError] = useState<string | null>(null);
  const [balance, setBalance] = useState<PlayerBalance | null>(null);
  const [registrations, setRegistrations] = useState<Record<string, TournamentRegistration>>({});
  const [waitlists, setWaitlists] = useState<Record<string, CashWaitlistStatus>>({});
  const [tableOpen, setTableOpen] = useState(false);
  const [buyInIntent, setBuyInIntent] = useState<{
    tableId: string;
    seatNo: number;
    reservationId?: string;
  } | null>(null);
  const [buyInAmount, setBuyInAmount] = useState(0);
  const [buyInPending, setBuyInPending] = useState(false);
  const [returnPending, setReturnPending] = useState(false);
  const realtime = useTableRealtime(tableOpen ? selectedTableId : null);

  useEffect(() => {
    if (!session) {
      setBalance(null);
      return;
    }
    let active = true;
    getMyBalance(session.session_id)
      .then((nextBalance) => {
        if (active) setBalance(nextBalance);
      })
      .catch(() => {
        if (active) setBalance(null);
      });
    return () => {
      active = false;
    };
  }, [session]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setLoadingError(null);

    listTables()
      .then((nextTables) => {
        if (!active) return;
        setTables(nextTables);
        setSelectedTableId((current) => current ?? nextTables[0]?.id ?? null);
      })
      .catch((cause) => {
        if (!active) return;
        setLoadingError(
          cause instanceof Error ? cause.message : "Не удалось загрузить лобби",
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [reloadKey]);

  useEffect(() => {
    if (!session || tables.length === 0) {
      setRegistrations({});
      return;
    }

    let active = true;
    const tournamentTables = tables.filter(
      (table) => table.table_mode === "tournament",
    );
    void Promise.all(
      tournamentTables.map(async (table) => {
        try {
          const registration = await getTournamentRegistration(
            table.id,
            session.session_id,
          );
          return [table.id, registration] as const;
        } catch {
          return null;
        }
      }),
    ).then((rows) => {
      if (!active) return;
      const next: Record<string, TournamentRegistration> = {};
      for (const row of rows) {
        if (row) next[row[0]] = row[1];
      }
      setRegistrations(next);
    });

    return () => {
      active = false;
    };
  }, [session, tables]);

  useEffect(() => {
    if (!session || tables.length === 0) {
      setWaitlists({});
      return;
    }

    let active = true;
    const cashTables = tables.filter((table) => table.table_mode === "cash");
    void Promise.all(
      cashTables.map(async (table) => {
        try {
          const status = await getCashWaitlistStatus(
            table.id,
            session.session_id,
          );
          return [table.id, status] as const;
        } catch {
          return null;
        }
      }),
    ).then((rows) => {
      if (!active) return;
      const next: Record<string, CashWaitlistStatus> = {};
      for (const row of rows) {
        if (row) next[row[0]] = row[1];
      }
      setWaitlists(next);
    });

    return () => {
      active = false;
    };
  }, [session, tables]);

  const openBuyIn = (
    table: TableState,
    seatNo: number,
    reservationId?: string,
  ) => {
    const availableMax = Math.min(
      table.cash_buyin_max,
      balance?.balance ?? 0,
    );
    const preferred = table.big_blind * 100;
    const initial = Math.min(
      availableMax,
      Math.max(table.cash_buyin_min, preferred),
    );
    setBuyInAmount(initial);
    setBuyInIntent({
      tableId: table.id,
      seatNo,
      ...(reservationId ? { reservationId } : {}),
    });
    setLoadingError(null);
  };

  const submitBuyIn = async (table: TableState) => {
    if (!session || !buyInIntent || buyInIntent.tableId !== table.id) return;
    const availableMax = Math.min(
      table.cash_buyin_max,
      balance?.balance ?? 0,
    );
    if (
      buyInAmount < table.cash_buyin_min ||
      buyInAmount > availableMax
    ) {
      setLoadingError("Buy-in вне доступного диапазона");
      return;
    }

    setBuyInPending(true);
    setLoadingError(null);
    try {
      const updated = buyInIntent.reservationId
        ? await claimSeatReservation(
            table.id,
            session.session_id,
            buyInIntent.reservationId,
            buyInAmount,
          )
        : await joinAuthenticatedTable(
            table.id,
            session.session_id,
            buyInIntent.seatNo,
            buyInAmount,
          );

      setTables((current) =>
        current.map((item) =>
          item.id === updated.id ? updated : item,
        ),
      );
      if (buyInIntent.reservationId) {
        setWaitlists((current) => ({
          ...current,
          [table.id]: {
            ...current[table.id],
            status: "seated",
            reservation: null,
          },
        }));
      }
      setBalance((current) =>
        current
          ? { ...current, balance: Math.max(0, current.balance - buyInAmount) }
          : current,
      );
      setBuyInIntent(null);
      setSelectedTableId(table.id);
      setTableOpen(true);
      onTableScreenChange(true);
    } catch (cause) {
      setLoadingError(
        cause instanceof Error ? cause.message : "Не удалось сесть за стол",
      );
    } finally {
      setBuyInPending(false);
    }
  };

  const cashTableCount = tables.filter(
    (table) => table.table_mode === "cash" && table.status !== "closed",
  ).length;
  const liveTableCount = tables.filter(
    (table) => Boolean(table.active_hand),
  ).length;
  const onlinePlayers = new Set(
    tables.flatMap((table) =>
      table.seats.map((seat) => seat.player_id),
    ),
  ).size;

  const myTables = playerId ? tables.filter((table) =>
    table.status !== "closed" && table.seats.some((seat) => seat.player_id === playerId),
  ) : [];

  const returnToTable = async (tableId: string) => {
    if (!playerId || returnPending) return;
    setReturnPending(true);
    setLoadingError(null);
    try {
      const current = await getTable(tableId, AbortSignal.timeout(5000));
      if (current.status === "closed" || !current.seats.some((seat) => seat.player_id === playerId)) {
        setTables((items) => items.map((table) => table.id === tableId ? current : table));
        setLoadingError("Место за этим столом больше недоступно. Выберите стол в лобби.");
        return;
      }
      setSelectedTableId(tableId);
      setTableOpen(true);
      onTableScreenChange(true);
    } catch {
      setLoadingError("Не удалось проверить стол. Проверьте связь и попробуйте ещё раз.");
    } finally {
      setReturnPending(false);
    }
  };

  if (tableOpen && !realtime.state) {
    return <main className="app-main">
      <div className="state-card" role="status">
        {realtime.error ? "Не удалось связаться со столом. Повторяем подключение…" : "Подключаемся к столу…"}
      </div>
      <button className="ghost-button" type="button" onClick={() => {
        setTableOpen(false); onTableScreenChange(false); setReloadKey((value) => value + 1);
      }}>← Лобби</button>
    </main>;
  }

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
            setReloadKey((value) => value + 1);
          }}
        />
      </main>
    );
  }

  return (
    <main className="app-main">
      <header className="app-header online-lobby-header">
        <div>
          <p>INARENA ONLINE</p>
          <h1>Лобби</h1>
        </div>
        {balance ? (
          <span className="balance-chip">
            Баланс {balance.balance} chips
          </span>
        ) : null}
      </header>

      {!loading && !loadingError && myTables.length > 0 && (
        <section className="return-to-table" aria-label="Ваши столы">
          {myTables.map((table) => <div key={table.id}>
            <strong>{table.name}</strong>
            <p>{table.seats.find((seat) => seat.player_id === playerId)?.status.startsWith("sitting_out")
              ? "Вы в sit-out. Возвращение откроет стол; участие включается отдельно."
              : "Ваше место за столом сохранено."}</p>
            <button className="action-button action-primary" type="button" disabled={returnPending}
              onClick={() => void returnToTable(table.id)}>{returnPending ? "Проверяем стол…" : "Вернуться в игру"}</button>
          </div>)}
        </section>
      )}

      <section className="lobby-overview" aria-label="Сводка лобби">
        <article>
          <strong>{cashTableCount}</strong>
          <span>Cash столов</span>
        </article>
        <article>
          <strong>{liveTableCount}</strong>
          <span>Сейчас играют</span>
        </article>
        <article>
          <strong>{onlinePlayers}</strong>
          <span>Игроков за столами</span>
        </article>
      </section>

      {loading ? (
        <div className="state-card" role="status" aria-live="polite">
          Загружаем столы…
        </div>
      ) : null}
      {loadingError ? (
        <div className="state-card state-error" role="alert">
          <span>{loadingError}</span>
          <button
            className="ghost-button"
            type="button"
            onClick={() => setReloadKey((value) => value + 1)}
          >
            Повторить
          </button>
        </div>
      ) : null}
      {realtime.error ? (
        <div className="state-card" role="status" aria-live="polite">
          {realtime.error}
        </div>
      ) : null}

      <section className="lobby-list" aria-label="Онлайн столы">
        {!loading && !loadingError && tables.length === 0 ? (
          <div className="state-card">
            <strong>Сейчас нет активных столов</strong>
            <span>Новый стол появится здесь автоматически после создания оператором.</span>
          </div>
        ) : (
          tables
            .slice()
            .sort((left, right) => {
              const leftMine = left.seats.some(
                (seat) => seat.player_id === playerId,
              );
              const rightMine = right.seats.some(
                (seat) => seat.player_id === playerId,
              );
              if (leftMine !== rightMine) return leftMine ? -1 : 1;
              if (left.table_mode !== right.table_mode) {
                return left.table_mode === "cash" ? -1 : 1;
              }
              if (Boolean(left.active_hand) !== Boolean(right.active_hand)) {
                return left.active_hand ? -1 : 1;
              }
              return left.name.localeCompare(right.name);
            })
            .map((table) => {
            const seated = table.seats.some(
              (seat) => seat.player_id === playerId,
            );
            const maxSeats = table.max_seats;
            const occupied = new Set(table.seats.map((seat) => seat.seat_no));
            const firstFreeSeat = Array.from(
              { length: maxSeats },
              (_, index) => index + 1,
            ).find((seatNo) => !occupied.has(seatNo));
            const freeSeats = Math.max(0, maxSeats - table.seats.length);
            const tableStatus =
              table.status === "closed"
                ? "Закрыт"
                : seated
                  ? "Вы за столом"
                  : table.seats.length >= maxSeats
                    ? "Полный"
                    : table.active_hand
                      ? "Идёт игра"
                      : table.seats.length >= 2
                        ? "Готов к игре"
                        : "Ожидание игроков";
            const statusTone =
              table.status === "closed"
                ? "closed"
                : seated
                  ? "mine"
                  : table.active_hand
                    ? "live"
                    : table.seats.length >= maxSeats
                      ? "full"
                      : "waiting";

            return (
              <article
                className={[
                  "lobby-card",
                  "lobby-room-card",
                  seated ? "is-my-table" : "",
                ].filter(Boolean).join(" ")}
                key={table.id}
              >
                <div className="lobby-room-head">
                  <div className="lobby-room-title">
                    <span className="lobby-room-mode">
                      {table.table_mode === "cash" ? "CASH" : "TOURNAMENT"}
                    </span>
                    <strong>{table.name}</strong>
                  </div>
                  <span className={"room-status " + statusTone}>
                    <i />
                    {tableStatus}
                  </span>
                </div>

                <div className="lobby-room-stats">
                  <div>
                    <small>BLINDS</small>
                    <strong>
                      {table.small_blind}/{table.big_blind}
                    </strong>
                  </div>
                  <div>
                    <small>ИГРОКИ</small>
                    <strong>
                      {table.seats.length}/{maxSeats}
                    </strong>
                  </div>
                  {table.table_mode === "cash" ? (
                    <div>
                      <small>BUY-IN</small>
                      <strong>
                        {table.cash_buyin_min.toLocaleString()}–
                        {table.cash_buyin_max.toLocaleString()}
                      </strong>
                    </div>
                  ) : (
                    <div>
                      <small>REGISTERED</small>
                      <strong>{table.registration_count}</strong>
                    </div>
                  )}
                </div>

                <div className="lobby-room-people">
                  <div className="room-avatar-stack" aria-label="Игроки за столом">
                    {table.seats.slice(0, 5).map((seat) =>
                      seat.photo_url ? (
                        <img
                          key={seat.player_id}
                          src={seat.photo_url}
                          alt=""
                          referrerPolicy="no-referrer"
                        />
                      ) : (
                        <span key={seat.player_id}>
                          {(seat.display_name?.trim()?.[0] ?? "P").toUpperCase()}
                        </span>
                      ),
                    )}
                    {table.seats.length === 0 ? (
                      <span className="room-avatar-empty">—</span>
                    ) : null}
                    {table.seats.length > 5 ? (
                      <span>+{table.seats.length - 5}</span>
                    ) : null}
                  </div>
                  <span className="room-free-seats">
                    {freeSeats > 0
                      ? `Свободно ${freeSeats} ${freeSeats === 1 ? "место" : "мест"}`
                      : "Свободных мест нет"}
                    {table.waitlist_count > 0
                      ? ` · очередь ${table.waitlist_count}`
                      : ""}
                  </span>
                </div>

                <div className="lobby-actions lobby-room-actions">
                  <button
                    className={seated ? "action-button action-primary" : "ghost-button"}
                    type="button"
                    aria-label="Открыть"
                    onClick={() => {
                      setSelectedTableId(table.id);
                      setTableOpen(true);
                      onTableScreenChange(true);
                    }}
                  >
                    {seated ? "Вернуться за стол" : "Смотреть"}
                  </button>

                  {table.table_mode === "tournament" && session ? (
                    <>
                      {registrations[table.id]?.status !== "registered" &&
                      ["registering", "running"].includes(table.tournament_status) ? (
                        <button
                          className="action-button action-primary"
                          type="button"
                          onClick={() =>
                            void registerTournament(
                              table.id,
                              session.session_id,
                            )
                              .then((registration) =>
                                setRegistrations((current) => ({
                                  ...current,
                                  [table.id]: registration,
                                })),
                              )
                              .catch((cause) =>
                                setLoadingError(
                                  cause instanceof Error
                                    ? cause.message
                                    : "Tournament registration failed",
                                ),
                              )
                          }
                        >
                          Зарегистрироваться
                        </button>
                      ) : null}
                      {registrations[table.id]?.status === "registered" &&
                      table.tournament_status === "registering" ? (
                        <button
                          className="ghost-button"
                          type="button"
                          onClick={() =>
                            void unregisterTournament(
                              table.id,
                              session.session_id,
                            ).then((registration) =>
                              setRegistrations((current) => ({
                                ...current,
                                [table.id]: registration,
                              })),
                            )
                          }
                        >
                          Отменить регистрацию
                        </button>
                      ) : null}
                      {!seated &&
                      firstFreeSeat &&
                      registrations[table.id]?.status === "registered" &&
                      table.tournament_status === "running" ? (
                        <button
                          className="action-button action-primary"
                          type="button"
                          onClick={() =>
                            void joinAuthenticatedTable(
                              table.id,
                              session.session_id,
                              firstFreeSeat,
                              table.starting_stack,
                            ).then((updated) => {
                              setTables((current) =>
                                current.map((item) =>
                                  item.id === updated.id ? updated : item,
                                ),
                              );
                              setSelectedTableId(table.id);
                              setTableOpen(true);
                              onTableScreenChange(true);
                            })
                          }
                        >
                          Сесть · Seat {firstFreeSeat}
                        </button>
                      ) : null}
                    </>
                  ) : !seated && session ? (
                    <>
                      {waitlists[table.id]?.reservation ? (
                        <button
                          className="action-button action-primary"
                          type="button"
                          disabled={
                            table.status === "closed" ||
                            (balance?.balance ?? 0) < table.cash_buyin_min
                          }
                          onClick={() => {
                            const reservation = waitlists[table.id].reservation;
                            if (!reservation) return;
                            openBuyIn(
                              table,
                              reservation.seat_no,
                              reservation.id,
                            );
                          }}
                        >
                          Занять Seat {waitlists[table.id].reservation?.seat_no}
                        </button>
                      ) : waitlists[table.id]?.status === "waiting" ? (
                        <>
                          <span className="waitlist-status">
                            Очередь #{waitlists[table.id].position ?? "—"}
                          </span>
                          <button
                            className="ghost-button"
                            type="button"
                            onClick={() =>
                              void leaveCashWaitlist(
                                table.id,
                                session.session_id,
                              ).then((status) =>
                                setWaitlists((current) => ({
                                  ...current,
                                  [table.id]: status,
                                })),
                              )
                            }
                          >
                            Выйти из очереди
                          </button>
                        </>
                      ) : firstFreeSeat && table.waitlist_count === 0 ? (
                        <button
                          className="action-button action-primary"
                          type="button"
                          disabled={
                            table.status === "closed" ||
                            (balance?.balance ?? 0) < table.cash_buyin_min
                          }
                          onClick={() =>
                            openBuyIn(table, firstFreeSeat)
                          }
                        >
                          Сесть · Seat {firstFreeSeat}
                        </button>
                      ) : (
                        <button
                          className="action-button action-primary"
                          type="button"
                          disabled={table.status === "closed"}
                          onClick={() =>
                            void joinCashWaitlist(
                              table.id,
                              session.session_id,
                            ).then((status) =>
                              setWaitlists((current) => ({
                                ...current,
                                [table.id]: status,
                              })),
                            )
                          }
                        >
                          Встать в очередь
                        </button>
                      )}
                    </>
                  ) : null}
                </div>

                {buyInIntent?.tableId === table.id ? (() => {
                  const availableMax = Math.min(
                    table.cash_buyin_max,
                    balance?.balance ?? 0,
                  );
                  const minBuyIn = table.cash_buyin_min;
                  const clamp = (value: number) =>
                    Math.min(
                      availableMax,
                      Math.max(minBuyIn, value),
                    );
                  const enoughBalance = availableMax >= minBuyIn;
                  return (
                    <section className="buyin-panel" aria-label="Выбор buy-in">
                      <div className="buyin-head">
                        <div>
                          <span>BUY-IN</span>
                          <strong>{buyInAmount.toLocaleString()} chips</strong>
                        </div>
                        <small>
                          Баланс {(balance?.balance ?? 0).toLocaleString()}
                        </small>
                      </div>

                      <div className="buyin-range-copy">
                        <span>Min {minBuyIn.toLocaleString()}</span>
                        <span>Max {availableMax.toLocaleString()}</span>
                      </div>

                      <div className="buyin-presets">
                        <button
                          type="button"
                          disabled={!enoughBalance}
                          onClick={() => setBuyInAmount(clamp(table.big_blind * 50))}
                        >
                          50 BB
                        </button>
                        <button
                          type="button"
                          disabled={!enoughBalance}
                          onClick={() => setBuyInAmount(clamp(table.big_blind * 100))}
                        >
                          100 BB
                        </button>
                        <button
                          type="button"
                          disabled={!enoughBalance}
                          onClick={() => setBuyInAmount(availableMax)}
                        >
                          Max
                        </button>
                      </div>

                      <input
                        aria-label="Buy-in amount"
                        type="range"
                        min={minBuyIn}
                        max={Math.max(minBuyIn, availableMax)}
                        step={table.big_blind}
                        value={
                          enoughBalance
                            ? Math.min(
                                Math.max(buyInAmount, minBuyIn),
                                availableMax,
                              )
                            : minBuyIn
                        }
                        disabled={!enoughBalance || buyInPending}
                        onChange={(event) =>
                          setBuyInAmount(Number(event.target.value))
                        }
                      />

                      {!enoughBalance ? (
                        <p className="buyin-warning" role="alert">
                          Недостаточно chips для минимального buy-in.
                        </p>
                      ) : null}

                      <div className="buyin-actions">
                        <button
                          className="ghost-button"
                          type="button"
                          disabled={buyInPending}
                          onClick={() => setBuyInIntent(null)}
                        >
                          Отмена
                        </button>
                        <button
                          className="action-button action-primary"
                          type="button"
                          disabled={!enoughBalance || buyInPending}
                          onClick={() => void submitBuyIn(table)}
                        >
                          {buyInPending
                            ? "Посадка…"
                            : "Сесть за стол · " + buyInAmount.toLocaleString()}
                        </button>
                      </div>
                    </section>
                  );
                })() : null}
              </article>
            );
          })
        )}
      </section>

    </main>
  );
}

function DiagnosticsView({
  telegramStatus,
  session,
}: {
  telegramStatus: "idle" | "authenticating" | "authenticated" | "unavailable" | "error";
  session: AuthSession | null;
}) {
  const [release, setRelease] = useState<{ release: string; environment: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const webApp = window.Telegram?.WebApp;

  useEffect(() => {
    let active = true;
    getReleaseMetadata()
      .then((metadata) => {
        if (active) setRelease(metadata);
      })
      .catch(() => {
        if (active) setRelease(null);
      });
    return () => {
      active = false;
    };
  }, []);

  const payload = {
    release: release?.release ?? "unknown",
    environment: release?.environment ?? "unknown",
    telegram: {
      available: Boolean(webApp),
      initDataPresent: Boolean(webApp?.initData),
      platform: webApp?.platform ?? "unknown",
      version: webApp?.version ?? "unknown",
      colorScheme: webApp?.colorScheme ?? "unknown",
      isExpanded: webApp?.isExpanded ?? null,
      viewportHeight: webApp?.viewportHeight ?? null,
      viewportStableHeight: webApp?.viewportStableHeight ?? null,
    },
    browser: {
      viewportWidth: window.innerWidth,
      viewportHeight: window.innerHeight,
      devicePixelRatio: window.devicePixelRatio,
      language: navigator.language,
      userAgent: navigator.userAgent,
      online: navigator.onLine,
    },
    session: {
      status: telegramStatus,
      authenticated: Boolean(session),
      provider: session?.provider ?? null,
    },
  };

  return (
    <main className="app-main diagnostics-page">
      <header className="app-header">
        <p>INARENA BETA</p>
        <h1>Device diagnostics</h1>
      </header>

      <section className="diagnostics-grid">
        <article>
          <strong>Release</strong>
          <span>{payload.release}</span>
          <span>{payload.environment}</span>
        </article>
        <article>
          <strong>Telegram</strong>
          <span>{payload.telegram.available ? "available" : "unavailable"}</span>
          <span>{payload.telegram.platform} · {payload.telegram.version}</span>
          <span>{payload.telegram.colorScheme}</span>
        </article>
        <article>
          <strong>Viewport</strong>
          <span>{payload.browser.viewportWidth} × {payload.browser.viewportHeight}</span>
          <span>DPR {payload.browser.devicePixelRatio}</span>
          <span>
            Telegram {payload.telegram.viewportHeight ?? "—"} /
            {payload.telegram.viewportStableHeight ?? "—"}
          </span>
        </article>
        <article>
          <strong>Session</strong>
          <span>{payload.session.status}</span>
          <span>{payload.session.authenticated ? "authenticated" : "not authenticated"}</span>
          <span>{payload.session.provider ?? "—"}</span>
        </article>
        <article>
          <strong>Network</strong>
          <span>{payload.browser.online ? "online" : "offline"}</span>
          <span>{payload.browser.language}</span>
        </article>
      </section>

      <details className="diagnostics-raw">
        <summary>Technical payload</summary>
        <pre>{JSON.stringify(payload, null, 2)}</pre>
      </details>

      <button
        className="action-button action-primary"
        type="button"
        onClick={() => {
          void navigator.clipboard
            .writeText(JSON.stringify(payload, null, 2))
            .then(() => setCopied(true))
            .catch(() => setCopied(false));
        }}
      >
        {copied ? "Скопировано" : "Копировать диагностику"}
      </button>

      <p className="diagnostics-note">
        Экран намеренно не показывает Telegram initData, session ID,
        operator token или закрытые карты.
      </p>
    </main>
  );
}


function OperatorDashboardView() {
  const [operatorKey, setOperatorKey] = useState(
    () =>
      window.localStorage.getItem("inarena_operator_token") ??
      window.sessionStorage.getItem("inarena_operator_token") ??
      "",
  );
  const [bootstrapKey, setBootstrapKey] = useState("");
  const [dashboard, setDashboard] = useState<OperatorDashboard | null>(null);
  const [tables, setTables] = useState<TableState[]>([]);
  const [audit, setAudit] = useState<OperatorAuditEntry[]>([]);
  const [expandedTableId, setExpandedTableId] = useState<string | null>(null);
  const [tableName, setTableName] = useState("");
  const [smallBlind, setSmallBlind] = useState(50);
  const [bigBlind, setBigBlind] = useState(100);
  const [buyInMin, setBuyInMin] = useState(1_000);
  const [buyInMax, setBuyInMax] = useState(10_000);
  const [creatingTable, setCreatingTable] = useState(false);
  const [tableAction, setTableAction] = useState<string | null>(null);
  const [balanceUser, setBalanceUser] = useState("");
  const [balanceDelta, setBalanceDelta] = useState(0);
  const [quickCreditPending, setQuickCreditPending] = useState(false);
  const [quickCreditResult, setQuickCreditResult] = useState<PlayerBalance | null>(null);
  const [tableFilter, setTableFilter] = useState<"all" | "live" | "open" | "paused" | "closed">("all");
  const [error, setError] = useState<string | null>(null);

  const load = async (key = operatorKey) => {
    setError(null);
    try {
      const [data, auditRows, tableRows] = await Promise.all([
        getOperatorDashboard(key),
        getOperatorAudit(key),
        listTables(),
      ]);
      setDashboard(data);
      setAudit(auditRows);
      setTables(tableRows);
      if (key.startsWith("ops_")) {
        window.localStorage.setItem("inarena_operator_token", key);
        window.sessionStorage.removeItem("inarena_operator_token");
      }
    } catch (cause) {
      setDashboard(null);
      setTables([]);
      const message =
        cause instanceof Error ? cause.message : "Operator error";
      if (
        key.startsWith("ops_") &&
        message.includes("expired or unauthorized")
      ) {
        window.sessionStorage.removeItem("inarena_operator_token");
        window.localStorage.removeItem("inarena_operator_token");
        setOperatorKey("");
        setAudit([]);
        setError("Сессия оператора истекла. Получите новую сессию.");
        return;
      }
      setError(message);
    }
  };

  useEffect(() => {
    if (operatorKey) void load(operatorKey);
  }, []);

  useEffect(() => {
    if (!operatorKey || !dashboard) return;
    let active = true;
    const refresh = async () => {
      try {
        const [tableRows, data] = await Promise.all([
          listTables(),
          getOperatorDashboard(operatorKey),
        ]);
        if (!active) return;
        setTables(tableRows);
        setDashboard(data);
      } catch {
        // Keep the current owner view intact; explicit actions surface errors.
      }
    };
    const timer = window.setInterval(() => {
      void refresh();
    }, 2000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [operatorKey, Boolean(dashboard)]);

  const runTableAction = async (
    tableId: string,
    operation: () => Promise<TableState>,
  ) => {
    setTableAction(tableId);
    setError(null);
    try {
      await operation();
      await load();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Не удалось изменить состояние стола",
      );
    } finally {
      setTableAction(null);
    }
  };

  const quickCredit = async (amount: number) => {
    const userId = balanceUser.trim();
    if (!userId || quickCreditPending) return;
    setQuickCreditPending(true);
    setQuickCreditResult(null);
    setError(null);
    try {
      const updated = await operatorAdjustBalance(userId, amount, operatorKey);
      setBalanceUser(userId);
      setQuickCreditResult(updated);
      await load();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Не удалось начислить тестовые chips",
      );
    } finally {
      setQuickCreditPending(false);
    }
  };

  const orderedTables = tables
    .slice()
    .sort((left, right) => {
      if (left.table_mode !== right.table_mode) {
        return left.table_mode === "cash" ? -1 : 1;
      }
      if (Boolean(left.active_hand) !== Boolean(right.active_hand)) {
        return left.active_hand ? -1 : 1;
      }
      return left.name.localeCompare(right.name);
    });

  const tableFilters = [
    { key: "all", label: "Все", count: tables.length },
    {
      key: "live",
      label: "Live",
      count: tables.filter((table) => Boolean(table.active_hand)).length,
    },
    {
      key: "open",
      label: "Открыты",
      count: tables.filter(
        (table) =>
          !table.active_hand &&
          table.status !== "paused" &&
          table.status !== "closed",
      ).length,
    },
    {
      key: "paused",
      label: "Пауза",
      count: tables.filter((table) => table.status === "paused").length,
    },
    {
      key: "closed",
      label: "Закрыты",
      count: tables.filter((table) => table.status === "closed").length,
    },
  ] as const;

  const visibleTables = orderedTables.filter((table) => {
    if (tableFilter === "all") return true;
    if (tableFilter === "live") return Boolean(table.active_hand);
    if (tableFilter === "paused") return table.status === "paused";
    if (tableFilter === "closed") return table.status === "closed";
    return (
      !table.active_hand &&
      table.status !== "paused" &&
      table.status !== "closed"
    );
  });

  return (
    <main className="app-main operator-dashboard table-manager">
      <header className="app-header operator-header manager-header">
        <div>
          <p>INARENA OWNER</p>
          <h1>Table Manager</h1>
          <span>7-max cash club</span>
        </div>
        {dashboard && operatorKey ? (
          <button
            className="ghost-button"
            type="button"
            onClick={() => {
              void revokeOperatorSession(operatorKey).catch(() => undefined);
              window.sessionStorage.removeItem("inarena_operator_token");
              window.localStorage.removeItem("inarena_operator_token");
              setOperatorKey("");
              setDashboard(null);
              setTables([]);
              setAudit([]);
              setError(null);
            }}
          >
            Выйти
          </button>
        ) : null}
      </header>

      {!dashboard ? (
        <>
          <p>Вход будет сохранён на этом устройстве на 30 дней.</p>
          <div className="operator-login">
            <input
              type="password"
              placeholder="Bootstrap operator key"
              value={bootstrapKey}
              onChange={(event) => setBootstrapKey(event.target.value)}
            />
            <button
              className="action-button action-primary"
              type="button"
              disabled={!bootstrapKey}
              onClick={() =>
                void authenticateOperator(bootstrapKey, [], true)
                  .then((session) => {
                    setOperatorKey(session.token);
                    setBootstrapKey("");
                    window.localStorage.setItem(
                      "inarena_operator_token",
                      session.token,
                    );
                    return load(session.token);
                  })
                  .catch((cause) =>
                    setError(
                      cause instanceof Error
                        ? cause.message
                        : "Operator authentication failed",
                    ),
                  )
              }
            >
              Получить сессию
            </button>
          </div>
        </>
      ) : null}

      {error ? <p className="state-card state-error" role="alert">{error}</p> : null}

      {dashboard ? (
        <>
          <section className="manager-metrics" aria-label="Состояние клуба">
            <article>
              <strong>{dashboard.cash_tables}</strong>
              <span>Cash столов</span>
            </article>
            <article>
              <strong>{dashboard.active_hands}</strong>
              <span>Идёт раздач</span>
            </article>
            <article>
              <strong>{dashboard.seated_players}</strong>
              <span>Игроков</span>
            </article>
            <article>
              <strong>{dashboard.active_sessions}</strong>
              <span>Online</span>
            </article>
          </section>

          <section
            className="manager-quick-credit"
            aria-label="Быстрое начисление тестовых chips"
          >
            <div className="manager-quick-credit-head">
              <div>
                <span>TEST CHIPS</span>
                <h2>Быстрое начисление</h2>
              </div>
              <p>Player ID можно скопировать в профиле игрока.</p>
            </div>
            <label className="manager-credit-player">
              <span>Player ID</span>
              <input
                aria-label="Player ID для начисления"
                placeholder="Вставьте Player ID"
                autoComplete="off"
                value={balanceUser}
                disabled={quickCreditPending}
                onChange={(event) => {
                  setBalanceUser(event.target.value);
                  setQuickCreditResult(null);
                }}
              />
            </label>
            <div className="manager-credit-presets" aria-label="Сумма начисления">
              {[1_000, 5_000, 10_000].map((amount) => (
                <button
                  className="action-button"
                  type="button"
                  key={amount}
                  aria-label={`Начислить ${amount} test chips`}
                  disabled={!balanceUser.trim() || quickCreditPending}
                  onClick={() => void quickCredit(amount)}
                >
                  +{amount.toLocaleString()}
                </button>
              ))}
            </div>
            {quickCreditResult ? (
              <p className="manager-credit-result" role="status">
                Баланс {quickCreditResult.user_id}:{" "}
                <strong>{quickCreditResult.balance.toLocaleString()} chips</strong>
              </p>
            ) : (
              <p className="manager-credit-note">
                Только внутренние тестовые chips; операция фиксируется в audit.
              </p>
            )}
          </section>

          <details className="manager-create" open>
            <summary>+ Создать cash-стол</summary>
            <form
              className="manager-create-form"
              aria-label="Создание стола"
              onSubmit={(event) => {
                event.preventDefault();
                if (creatingTable || !tableName.trim()) return;
                if (
                  smallBlind <= 0 ||
                  bigBlind <= smallBlind ||
                  buyInMin <= 0 ||
                  buyInMax < buyInMin
                ) {
                  setError("Проверьте blinds и диапазон buy-in.");
                  return;
                }
                setCreatingTable(true);
                setError(null);
                void operatorCreateTable(tableName, operatorKey)
                  .then((created) =>
                    operatorConfigureCashTable(created.id, operatorKey, {
                      smallBlind,
                      bigBlind,
                      cashBuyinMin: buyInMin,
                      cashBuyinMax: buyInMax,
                    }),
                  )
                  .then(async () => {
                    setTableName("");
                    await load();
                  })
                  .catch(async (cause) => {
                    if (
                      cause instanceof Error &&
                      cause.message.includes("expired or unauthorized")
                    ) {
                      await load();
                      return;
                    }
                    setError(
                      cause instanceof Error
                        ? cause.message
                        : "Не удалось создать стол",
                    );
                  })
                  .finally(() => setCreatingTable(false));
              }}
            >
              <label>
                <span>Название</span>
                <input
                  aria-label="Название стола"
                  placeholder="Например, Main 50/100"
                  value={tableName}
                  disabled={creatingTable}
                  onChange={(event) => setTableName(event.target.value)}
                />
              </label>

              <div className="manager-field-grid">
                <label>
                  <span>Small blind</span>
                  <input
                    aria-label="Small blind"
                    type="number"
                    min={1}
                    value={smallBlind}
                    disabled={creatingTable}
                    onChange={(event) =>
                      setSmallBlind(Number(event.target.value))
                    }
                  />
                </label>
                <label>
                  <span>Big blind</span>
                  <input
                    aria-label="Big blind"
                    type="number"
                    min={2}
                    value={bigBlind}
                    disabled={creatingTable}
                    onChange={(event) =>
                      setBigBlind(Number(event.target.value))
                    }
                  />
                </label>
                <label>
                  <span>Min buy-in</span>
                  <input
                    aria-label="Min buy-in"
                    type="number"
                    min={1}
                    value={buyInMin}
                    disabled={creatingTable}
                    onChange={(event) =>
                      setBuyInMin(Number(event.target.value))
                    }
                  />
                </label>
                <label>
                  <span>Max buy-in</span>
                  <input
                    aria-label="Max buy-in"
                    type="number"
                    min={1}
                    value={buyInMax}
                    disabled={creatingTable}
                    onChange={(event) =>
                      setBuyInMax(Number(event.target.value))
                    }
                  />
                </label>
              </div>

              <div className="manager-capacity-note">
                <strong>7-max</strong>
                <span>Формат фиксирован для текущего MVP.</span>
              </div>

              <button
                className="action-button action-primary"
                type="submit"
                aria-label="Создать стол"
                disabled={creatingTable || !tableName.trim()}
              >
                {creatingTable ? "Создание…" : "Создать и открыть стол"}
              </button>
            </form>
          </details>

          <nav className="manager-table-filters" aria-label="Фильтр столов">
            {tableFilters.map((filter) => (
              <button
                type="button"
                key={filter.key}
                aria-pressed={tableFilter === filter.key}
                aria-label={`Показать столы: ${filter.label.toLowerCase()}`}
                onClick={() => setTableFilter(filter.key)}
              >
                <span>{filter.label}</span>
                <strong>{filter.count}</strong>
              </button>
            ))}
          </nav>

          <section className="manager-table-list" aria-label="Управление столами">
            {visibleTables.length === 0 ? (
              <div className="state-card">
                <strong>
                  {orderedTables.length === 0
                    ? "Столов пока нет"
                    : "Нет столов в этом фильтре"}
                </strong>
                <span>
                  {orderedTables.length === 0
                    ? "Создайте первый 7-max cash-стол выше."
                    : "Выберите другой статус стола."}
                </span>
              </div>
            ) : null}

            {visibleTables.map((table) => {
              const isCash = table.table_mode === "cash";
              const activePlayers = table.seats.filter(
                (seat) => seat.status === "seated",
              ).length;
              const isExpanded = expandedTableId === table.id;
              const busy = tableAction === table.id;
              const canStart =
                isCash &&
                table.status === "open" &&
                !table.active_hand &&
                activePlayers >= 2;

              return (
                <article
                  className={[
                    "operator-table-card",
                    "manager-table-card",
                    table.active_hand ? "is-live" : "",
                    table.status === "closed" ? "is-closed" : "",
                  ].filter(Boolean).join(" ")}
                  key={table.id}
                >
                  <div className="manager-table-head">
                    <div>
                      <span className="manager-mode">
                        {isCash ? "CASH · 7-MAX" : "TOURNAMENT"}
                      </span>
                      <strong>{table.name}</strong>
                    </div>
                    <span
                      className={[
                        "manager-status",
                        table.active_hand
                          ? "live"
                          : table.status === "closed"
                            ? "closed"
                            : table.status === "paused"
                              ? "paused"
                              : "open",
                      ].join(" ")}
                    >
                      {table.active_hand
                        ? "Идёт раздача"
                        : table.status === "closed"
                          ? "Закрыт"
                          : table.status === "paused"
                            ? "Пауза"
                            : "Открыт"}
                    </span>
                  </div>

                  <div className="manager-table-stats">
                    <div>
                      <small>BLINDS</small>
                      <strong>{table.small_blind}/{table.big_blind}</strong>
                    </div>
                    <div>
                      <small>PLAYERS</small>
                      <strong>{table.seats.length}/{table.max_seats}</strong>
                    </div>
                    <div>
                      <small>WAIT</small>
                      <strong>{table.waitlist_count}</strong>
                    </div>
                    <div>
                      <small>BUY-IN</small>
                      <strong>
                        {table.cash_buyin_min.toLocaleString()}–
                        {table.cash_buyin_max.toLocaleString()}
                      </strong>
                    </div>
                  </div>

                  <div className="manager-seat-strip" aria-label="Места за столом">
                    {Array.from(
                      { length: table.max_seats },
                      (_, index) => index + 1,
                    ).map((seatNo) => {
                      const seat = table.seats.find(
                        (item) => item.seat_no === seatNo,
                      );
                      return (
                        <div
                          className={[
                            "manager-seat-dot",
                            seat ? "occupied" : "empty",
                            seat?.status === "sitting_out" ||
                            seat?.status === "sitting_out_next"
                              ? "sitting-out"
                              : "",
                          ].filter(Boolean).join(" ")}
                          key={seatNo}
                          title={
                            seat
                              ? `${seat.display_name ?? seat.player_id} · ${seat.stack}`
                              : `Seat ${seatNo} свободен`
                          }
                        >
                          {seat?.photo_url ? (
                            <img
                              src={seat.photo_url}
                              alt=""
                              referrerPolicy="no-referrer"
                            />
                          ) : (
                            <span>{seat ? (seat.display_name?.[0] ?? "P").toUpperCase() : seatNo}</span>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  <div className="manager-table-actions">
                    <button
                      className="ghost-button"
                      type="button"
                      onClick={() =>
                        setExpandedTableId((current) =>
                          current === table.id ? null : table.id,
                        )
                      }
                    >
                      {isExpanded ? "Скрыть детали" : "Управление"}
                    </button>

                    {table.status === "open" && !table.active_hand ? (
                      <button
                        className="ghost-button"
                        type="button"
                        disabled={busy}
                        onClick={() =>
                          void runTableAction(table.id, () =>
                            operatorSetTableStatus(
                              table.id,
                              "pause",
                              operatorKey,
                            ),
                          )
                        }
                      >
                        Пауза
                      </button>
                    ) : table.status === "paused" || table.status === "closed" ? (
                      <button
                        className="action-button action-primary"
                        type="button"
                        disabled={busy}
                        onClick={() =>
                          void runTableAction(table.id, () =>
                            operatorSetTableStatus(
                              table.id,
                              "resume",
                              operatorKey,
                            ),
                          )
                        }
                      >
                        Открыть стол
                      </button>
                    ) : null}

                    {canStart ? (
                      <button
                        className="action-button action-primary"
                        type="button"
                        disabled={busy}
                        onClick={() =>
                          void runTableAction(table.id, () =>
                            operatorStartHand(table.id, operatorKey),
                          )
                        }
                      >
                        Начать раздачу
                      </button>
                    ) : null}
                  </div>

                  {isExpanded ? (
                    <section className="manager-table-details">
                      <div className="manager-player-list">
                        <h3>Игроки</h3>
                        {table.seats.length === 0 ? (
                          <p>За столом пока никого нет.</p>
                        ) : (
                          table.seats
                            .slice()
                            .sort((a, b) => a.seat_no - b.seat_no)
                            .map((seat) => (
                              <article key={seat.player_id}>
                                <div className="manager-player-main">
                                  {seat.photo_url ? (
                                    <img
                                      src={seat.photo_url}
                                      alt=""
                                      referrerPolicy="no-referrer"
                                    />
                                  ) : (
                                    <span className="manager-player-avatar">
                                      {(seat.display_name?.[0] ?? "P").toUpperCase()}
                                    </span>
                                  )}
                                  <div>
                                    <strong>
                                      Seat {seat.seat_no} ·{" "}
                                      {seat.display_name ?? "Игрок"}
                                    </strong>
                                    <small>{seat.player_id}</small>
                                  </div>
                                </div>
                                <div className="manager-player-stack">
                                  <strong>{seat.stack.toLocaleString()}</strong>
                                  <span>
                                    {seat.status === "sitting_out"
                                      ? "Sit out"
                                      : seat.status === "sitting_out_next"
                                        ? "Sit out next"
                                        : seat.status === "sitting_in_next"
                                          ? "Returning"
                                          : "Playing"}
                                  </span>
                                </div>
                              </article>
                            ))
                        )}
                      </div>

                      {table.active_hand ? (
                        <div className="manager-live-hand">
                          <span>HAND</span>
                          <strong>
                            {String(table.active_hand.street).toUpperCase()} ·
                            Pot {table.active_hand.pot.toLocaleString()}
                          </strong>
                          <small>
                            Ход: Seat {table.active_hand.action_seat ?? "—"}
                          </small>
                        </div>
                      ) : null}

                      <div className="manager-danger-zone">
                        <button
                          className="ghost-button action-danger"
                          type="button"
                          disabled={busy || Boolean(table.active_hand) || table.status === "closed"}
                          onClick={() =>
                            void runTableAction(table.id, () =>
                              operatorCloseTable(table.id, operatorKey),
                            )
                          }
                        >
                          Закрыть стол
                        </button>
                      </div>
                    </section>
                  ) : null}
                </article>
              );
            })}
          </section>

          <details className="manager-admin-tools">
            <summary>Баланс игроков и audit</summary>

            <section className="operator-balance-control">
              <input
                placeholder="User ID"
                value={balanceUser}
                onChange={(event) => setBalanceUser(event.target.value)}
              />
              <input
                type="number"
                placeholder="Δ chips"
                value={balanceDelta}
                onChange={(event) =>
                  setBalanceDelta(Number(event.target.value))
                }
              />
              <button
                className="action-button action-primary"
                type="button"
                disabled={!balanceUser || balanceDelta === 0}
                onClick={() =>
                  void operatorAdjustBalance(
                    balanceUser,
                    balanceDelta,
                    operatorKey,
                  )
                    .then(() => load())
                    .catch((cause) =>
                      setError(
                        cause instanceof Error
                          ? cause.message
                          : "Balance adjustment failed",
                      ),
                    )
                }
              >
                Изменить баланс
              </button>
            </section>

            <section className="operator-audit">
              <h3>Последние действия</h3>
              {audit.slice(0, 12).map((entry) => (
                <article key={entry.id}>
                  <strong>{entry.action}</strong>
                  <span>
                    {entry.table_id ?? "global"} · {entry.created_at}
                  </span>
                </article>
              ))}
            </section>
          </details>
        </>
      ) : null}
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

function PlayerProfile({ session }: { session: AuthSession | null }) {
  const [balance, setBalance] = useState<PlayerBalance | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    let active = true;
    setLoading(true);
    setBalance(null);
    setError(null);
    getMyBalance(session.session_id)
      .then((value) => { if (active) setBalance(value); })
      .catch(() => { if (active) setError("Не удалось загрузить баланс"); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [session, reloadKey]);

  const user = session?.data.telegram_user;
  const telegramUser = user && typeof user === "object" ? user as Record<string, unknown> : {};
  const name = [telegramUser.first_name, telegramUser.last_name]
    .filter((value): value is string => typeof value === "string" && Boolean(value))
    .join(" ") || (typeof telegramUser.username === "string" ? telegramUser.username : "Игрок");

  return (
    <main className="app-main">
      <header className="app-header"><div><p>INARENA</p><h1>Профиль</h1></div></header>
      {session ? (
        <section className="state-card player-profile">
          <h2>{name}</h2>
          <p>ID игрока: <strong>{session.user_id}</strong></p>
          <p>Этот ID используется владельцем клуба для начисления фишек.</p>
          <button className="action-button" type="button" onClick={async () => {
            try {
              await navigator.clipboard.writeText(session.user_id);
              setCopyStatus("ID скопирован");
            } catch {
              setCopyStatus("Не удалось скопировать ID. Выделите его и скопируйте вручную.");
            }
          }}>
            Скопировать ID
          </button>
          {copyStatus ? <p role="status">{copyStatus}</p> : null}
          {loading ? <p role="status">Загружаем баланс…</p> : null}
          {error ? <p role="alert">{error}</p> : null}
          {balance ? <p>Баланс: <strong>{balance.balance} chips</strong></p> : null}
          <button className="action-button action-primary" type="button" disabled={loading}
            onClick={() => setReloadKey((value) => value + 1)}>
            Обновить баланс
          </button>
        </section>
      ) : <p className="state-card">Откройте приложение внутри Telegram и дождитесь входа, чтобы увидеть профиль.</p>}
    </main>
  );
}

export default function App() {
  const params = new URLSearchParams(window.location.search);
  const operatorMode = params.get("operator") === "1";
  const diagnosticsMode = params.get("diagnostics") === "1";
  const [mode, setMode] = useState<AppMode>("offline");
  const telegram = useTelegramSession();
  const [tableScreenOpen, setTableScreenOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const tabs = mode === "online" ? onlineTabs : offlineTabs;

  if (diagnosticsMode) {
    return (
      <div className="app-shell">
        <div className="brand-row">
          <span className="brand-mark">INARENA</span>
          <span className="status-dot" aria-hidden="true" />
        </div>
        <DiagnosticsView
          telegramStatus={telegram.status}
          session={telegram.session}
        />
      </div>
    );
  }

  if (operatorMode) {
    return (
      <div className="app-shell operator-shell">
        <div className="brand-row">
          <span className="brand-mark">INARENA</span>
          <span className="status-dot" aria-hidden="true" />
        </div>
        <OperatorDashboardView />
      </div>
    );
  }

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
          setProfileOpen(false);
          setTableScreenOpen(false);
        }}
      />
      {mode === "online" ? (
        <>
          {telegram.status === "authenticating" ? (
            <div className="state-card" role="status" aria-live="polite">
              Подключаем Telegram…
            </div>
          ) : null}
          {telegram.status === "error" ? (
            <div className="state-card state-error" role="alert">
              Не удалось подтвердить Telegram-сессию. Закройте и снова откройте приложение из Telegram.
            </div>
          ) : null}
          {telegram.status === "unavailable" ? (
            <div className="state-card" role="status">
              Откройте приложение внутри Telegram для действий от имени игрока.
            </div>
          ) : null}
          {profileOpen ? <PlayerProfile session={telegram.session} /> : (
            <OnlineLobby session={telegram.session} onTableScreenChange={setTableScreenOpen} />
          )}
        </>
      ) : (
        profileOpen ? <PlayerProfile session={telegram.session} /> : <OfflineHome />
      )}
      {!tableScreenOpen ? (
        <nav className="bottom-nav" aria-label="Основная навигация">
          {tabs.map((tab) => (
            <button className="nav-item" type="button" key={tab}
              disabled={tab === "Игра" || tab === "Турниры"}
              aria-current={(profileOpen ? tab === "Профиль" : tab === tabs[0]) ? "page" : undefined}
              onClick={() => setProfileOpen(tab === "Профиль")}>

              {tab}
            </button>
          ))}
        </nav>
      ) : null}
    </div>
  );
}
