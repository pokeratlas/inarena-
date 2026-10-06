# INARENA Motion V1

## Goal

Make the poker table feel alive without changing game timing or server authority.
Motion is cosmetic feedback only; it must never hide legal actions or imply state
that the backend has not confirmed.

## Included

- board card deal/reveal with short stagger;
- hero hole-card deal;
- active-seat pulse;
- pot update pop;
- action dock entrance when it becomes the hero's turn;
- reconnect breathing state.

## Timing

Animations intentionally stay in the ~180–300 ms range. Active-seat and reconnect
feedback may loop while the corresponding state remains active.

## Accessibility

All Table V2 motion respects `prefers-reduced-motion: reduce`. In reduced-motion
mode animation/transition durations collapse to effectively zero and layout/state
remain identical.

## Later motion

Chip trajectories, showdown winner collection, richer hand-result overlays and
sound/haptic cues are explicitly deferred until the foundation is reviewed on a
real device.
