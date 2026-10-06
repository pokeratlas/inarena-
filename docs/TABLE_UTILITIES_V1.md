# INARENA Table Utilities V1

## Goal

Move secondary table information out of the main play surface so the arena and
betting controls stay visually dominant on mobile.

## Included

- dedicated History button in the table HUD;
- bottom-sheet history drawer;
- latest completed hand summary in BB + chips;
- hero hole cards and board when available;
- ordered action log for the latest hand;
- compact recent-hand pot list;
- close control and backdrop dismissal.

## UX constraints

- history never replaces the live table state;
- betting actions remain outside the drawer and are not duplicated;
- drawer width cannot exceed the viewport;
- close/history controls meet the Guardian touch-target minimum;
- mobile and desktop Guardian both verify the interaction.

## Deferred

Player notes, hand sharing/export and richer filters are intentionally deferred
until closed-beta usage shows they are needed.
