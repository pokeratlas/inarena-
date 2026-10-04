import { useEffect, useRef, useState } from "react";

const API = import.meta.env.VITE_API_BASE ?? "";
type Message = { sequence: number; player_id: string; display_name: string; text: string; created_at: string };

export function TableChat({ tableId, sessionId, playerId }: { tableId: string; sessionId: string; playerId: string }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState("");
  const opened = useRef(false);
  const latest = useRef<number | null>(null);
  const pending = useRef<{ text: string; id: string } | null>(null);
  const log = useRef<HTMLDivElement>(null);
  const url = `${API}/api/v1/tables/${tableId}/chat`;

  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    latest.current = null;
    setMessages([]);
    setUnread(0);
    async function refresh() {
      try {
        const response = await fetch(url, { headers: { "X-Session-ID": sessionId }, signal: AbortSignal.any([controller.signal, AbortSignal.timeout(5000)]) });
        if (!response.ok) throw new Error("Чат временно недоступен");
        const rows: Message[] = await response.json();
        if (stopped) return;
        if (latest.current !== null && !opened.current) {
          const after = latest.current;
          setUnread((count) => count + rows.filter((m) => m.sequence > after && m.player_id !== playerId).length);
        }
        latest.current = Math.max(latest.current ?? 0, ...rows.map((m) => m.sequence));
        setMessages(rows);
        setConnected(true);
      } catch {
        if (!stopped) setConnected(false);
      } finally {
        if (!stopped) timer = setTimeout(refresh, 1000);
      }
    }
    void refresh();
    return () => { stopped = true; controller.abort(); clearTimeout(timer); };
  }, [url, sessionId, playerId]);

  useEffect(() => { if (open && log.current) log.current.scrollTop = log.current.scrollHeight; }, [messages, open]);

  async function send() {
    const text = draft.trim();
    if (!text || sending) return;
    const attempt = pending.current?.text === text ? pending.current : { text, id: crypto.randomUUID() };
    pending.current = attempt;
    setSending(true);
    setError("");
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Session-ID": sessionId },
        body: JSON.stringify({ text, client_message_id: attempt.id }),
        signal: AbortSignal.timeout(8000),
      });
      if (!response.ok) throw new Error(response.status === 429 ? "Подождите две секунды перед следующим сообщением" : "Не удалось отправить. Попробуйте ещё раз");
      const message: Message = await response.json();
      setMessages((rows) => [...rows.filter((m) => m.sequence !== message.sequence), message].sort((a, b) => a.sequence - b.sequence).slice(-50));
      setDraft("");
      pending.current = null;
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Не удалось отправить"); }
    finally { setSending(false); }
  }

  return <section className="table-chat" aria-label="Чат за столом">
    <button type="button" aria-expanded={open} aria-controls={`chat-${tableId}`} onClick={() => {
      opened.current = !open; setOpen(!open); setUnread(0);
    }}>Чат{unread ? ` · ${unread} новых` : ""}</button>
    {open && <div id={`chat-${tableId}`}>
      <p role="status">{connected ? "Чат подключён" : "Восстанавливаем связь с чатом…"}</p>
      <div ref={log} className="table-chat-log" role="log" aria-label="Сообщения за столом" aria-live="polite">
        {messages.length ? messages.map((m) => <p key={m.sequence}><strong>{m.player_id === playerId ? "Вы" : m.display_name}</strong>: <span>{m.text}</span></p>) : <p>Сообщений пока нет</p>}
      </div>
      <form onSubmit={(event) => { event.preventDefault(); void send(); }}>
        <label>Сообщение<input value={draft} maxLength={500} disabled={sending} onChange={(event) => setDraft(event.target.value)} /></label>
        <button type="submit" disabled={!connected || sending || !draft.trim()}>{sending ? "Отправляем…" : "Отправить"}</button>
      </form>
      {error && <p role="alert">{error}</p>}
    </div>}
  </section>;
}
