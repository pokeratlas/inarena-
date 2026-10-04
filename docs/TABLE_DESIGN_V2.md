# INARENA Table V2

## Product intent

Table V2 keeps the fast-read structure of mature mobile poker clients without
copying another product's artwork, branding, exact controls or animation assets.
The table remains recognizably INARENA: navy/indigo arena surface, restrained
electric-blue emphasis, compact sports HUD and server-authoritative interaction.

## Visual hierarchy

1. Header: back, table identity, blinds, table info and connection state.
2. Arena: fixed 7-max oval with the hero anchored at the bottom and opponents
   distributed around the remaining arc.
3. Center HUD: total pot in BB with chip value underneath, board and street.
4. Hero zone: avatar/name, stack in BB + chips, D/SB/BB badges and hole cards.
5. Action dock: Fold, Check/Call, sizing presets, slider and Bet/Raise/All-in.
6. Secondary controls: top-up, sit-out/leave, table chat and hand history.

## Poker readability rules

- Primary stack unit is BB; exact chips remain visible as secondary information.
- The current actor uses one luminous outline; non-actors stay visually quiet.
- Board and pot have higher contrast than decorative branding.
- Hero hole cards remain larger than board cards.
- Utility controls must not compete with betting actions.
- Reconnect state locks actions and stays visible without replacing the table.

## Responsive contract

- 360, 390 and 430px widths must not introduce horizontal overflow.
- Hero remains below the geometric center of the arena.
- In heads-up, the single opponent sits at the top.
- Up to six opponents are distributed around the oval for fixed 7-max.
- Touch-critical controls keep the Guardian minimum hit target.

## Motion follow-up

Table V2 foundation intentionally ships before the motion layer. Motion V1 will
add card dealing/reveal, actor pulse, chip-to-pot movement, pot count-up and
showdown/result transitions while respecting reduced-motion preferences.
