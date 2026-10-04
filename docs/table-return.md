# Return to table v1

The online lobby shows a prominent Your tables section for the authenticated
player's existing seats. One click opens a table after checking its current state.
The server's seat is the source of truth; no bookmark, credential or local seat
reservation is added. Reopening the app restores the existing session and then
offers the shortcut when the player switches Online.

Returning does not join again, change balances, or enable participation. A player
in sit-out remains in sit-out until explicitly choosing the existing participation
control. If another device has left or the table has closed, the shortcut refreshes
the visible table state and explains that the place is no longer available.
Leaving the table view for the lobby refreshes its list.

The table shows reconnect feedback even between hands. LIVE requires receipt of
a table snapshot/event/replay, rather than only a socket opening. A five-second
connection/sync deadline closes a stalled socket so the existing retry can recover.
Offline/online events update connection state and resume connection automatically.
Changing tables clears the old display, disposed handlers cannot update it, and a
REST snapshot started before a socket update cannot overwrite that newer update.
Initial loading has an explicit status and a usable Lobby exit.

Long table names are constrained to their title column so they cannot cover the
Lobby button. Guardian verifies the return shortcut and the back button on desktop
and mobile, delayed initial sync, offline recovery between hands, unchanged seat
and balance, sit-out after reload, and stale membership after another device leaves.
The required return journey has an eight-second click-to-synced ceiling.

This is stacked on table chat PR #25 and Guardian PR #24. There are no backend,
database or production configuration changes in this increment.
