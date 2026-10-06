# INARENA Load Testing

Primary script: `load/inarena.js`

Required environment:
- `BASE_URL` — backend base URL;
- `TABLE_ID` — optional table id for table reads / WebSocket tests;
- `ORIGIN` — approved WebSocket origin.

Example:

```bash
k6 run \
  -e BASE_URL=https://staging-api.example.com \
  -e TABLE_ID=<table-id> \
  -e ORIGIN=https://staging.example.com \
  load/inarena.js
```

Initial thresholds:
- HTTP error rate < 1%;
- HTTP p95 < 500 ms;
- successful checks > 99%.

These are baseline thresholds for staging, not final production SLOs.
Production SLOs should be set after measured closed-beta traffic.
