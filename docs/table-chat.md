# Table chat v1

Seated players can open Chat below participation controls, exchange plain-text
messages, see an unread count while it is collapsed, and recover the latest
history after a network interruption or reopening the app. Sit-out players keep
access while seated. Visitors and players at another table cannot read or send.
Sessions must be valid; a closed table rejects chat. Telegram names are taken
from the authenticated session; the client cannot supply a sender identity.

The authenticated REST endpoints refresh once per second, independently of game
state and public table sockets. Requests time out and retry automatically; sending
preserves the draft on failure and reuses a client message ID for retry. This is
an initial closed-beta implementation, not a high-volume messaging service.

SQLite and PostgreSQL migrate additively from schema 16 to 17. Chat keeps at most
200 messages per table after a send and returns the latest 50 in chronological
order. The database permits one new message per player every two seconds across
tables and workers. Repeating the same retained message ID and content returns
the original message; changing its content returns 409. Messages are limited to
500 characters and rendered as text. No credentials or private cards are included.

Guardian requires desktop and mobile `table-chat` journeys, with a 5-second
send-to-visible budget, unread feedback, plain-text rendering, offline recovery,
and history after reload. Backend tests cover authorization, expiry, validation,
retention, throttle, duplicates and migration without losing seats. PostgreSQL CI
also checks chat writes and upgrades. No new cloud service is needed.

The chat change is a separate increment based on Guardian PR #24. Promotion to
RC1 still requires the same-SHA backend, frontend and Guardian checks.
