import http from "k6/http";
import ws from "k6/ws";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8000";
const WS_BASE_URL =
  __ENV.WS_BASE_URL ||
  BASE_URL.replace("https://", "wss://").replace("http://", "ws://");
const TABLE_ID = __ENV.TABLE_ID || "";

export const options = {
  scenarios: {
    http_reads: {
      executor: "ramping-vus",
      startVUs: 1,
      stages: [
        { duration: "10s", target: 10 },
        { duration: "20s", target: 25 },
        { duration: "10s", target: 0 },
      ],
      exec: "httpReads",
    },
    websocket_reconnects: {
      executor: "constant-arrival-rate",
      rate: 2,
      timeUnit: "1s",
      duration: "30s",
      preAllocatedVUs: 4,
      maxVUs: 20,
      exec: "websocketReconnect",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<500"],
    checks: ["rate>0.99"],
  },
};

export function httpReads() {
  const health = http.get(`${BASE_URL}/health`);
  check(health, {
    "health 200": (r) => r.status === 200,
  });

  const ready = http.get(`${BASE_URL}/ready`);
  check(ready, {
    "ready 200": (r) => r.status === 200,
  });

  if (TABLE_ID) {
    const table = http.get(`${BASE_URL}/api/v1/tables/${TABLE_ID}`);
    check(table, {
      "table read 200": (r) => r.status === 200,
    });
  }

  sleep(0.2);
}

export function websocketReconnect() {
  if (!TABLE_ID) {
    return;
  }

  const origin = __ENV.ORIGIN || "http://staging.local";
  const response = ws.connect(
    `${WS_BASE_URL}/ws/tables/${TABLE_ID}`,
    { headers: { Origin: origin } },
    (socket) => {
      socket.setTimeout(() => socket.close(), 500);
    },
  );

  check(response, {
    "websocket upgraded": (r) => r && r.status === 101,
  });
}
