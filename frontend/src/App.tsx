import { useEffect, useState } from "react";

import { listTables } from "./api";
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

function OnlineLobby() {
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
        <p>
          {realtime.connected ? "Live" : "Reconnecting"}
          {realtime.lastSeq > 0 ? ` · seq ${realtime.lastSeq}` : ""}
        </p>
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
        <section aria-label="Текущий стол">
          <h2>{realtime.state.name}</h2>
          <p>
            {realtime.state.active_hand
              ? `Раздача: ${realtime.state.active_hand.street}, банк ${realtime.state.active_hand.pot}`
              : "Ожидание раздачи"}
          </p>
          <p>Игроков за столом: {realtime.state.seats.length}</p>
        </section>
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
  const tabs = mode === "online" ? onlineTabs : offlineTabs;

  return (
    <div>
      <ModeSwitch mode={mode} onChange={setMode} />
      {mode === "online" ? <OnlineLobby /> : <OfflineHome />}
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
