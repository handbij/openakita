// ─── WebSocket Event Client ───
// Provides real-time event push for ALL modes (Web, Tauri local, Tauri remote, Capacitor).
// Auto-reconnects on disconnect with exponential backoff.

import { IS_TAURI, IS_CAPACITOR } from "./detect";
import { getAccessToken, isTokenExpiringSoon, refreshAccessToken, isTauriRemoteMode } from "./auth";
import { getActiveServer } from "./servers";
import { logger } from "./logger";

export type WsEventHandler = (event: string, data: unknown) => void;

let _ws: WebSocket | null = null;
let _handlers: WsEventHandler[] = [];
let _reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let _reconnectDelay = 1000;
let _reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 120;
let _connected = false;
let _intentionallyClosed = false;

function getWsUrl(): string {
  let host: string;
  let proto: string;

  if (IS_CAPACITOR || (IS_TAURI && isTauriRemoteMode())) {
    const server = getActiveServer();
    if (!server) return "";
    const url = new URL(server.url);
    host = url.host;
    proto = url.protocol === "https:" ? "wss:" : "ws:";
  } else if (IS_TAURI) {
    // Tauri local mode: window.location is tauri://localhost, not the backend.
    // Read actual backend address from localStorage (same source as App.tsx apiBaseUrl).
    const stored = localStorage.getItem("openakita_apiBaseUrl") || "http://127.0.0.1:18900";
    try {
      const url = new URL(stored);
      host = url.host;
      proto = url.protocol === "https:" ? "wss:" : "ws:";
    } catch {
      host = "127.0.0.1:18900";
      proto = "ws:";
    }
  } else {
    const loc = window.location;
    host = loc.host;
    proto = loc.protocol === "https:" ? "wss:" : "ws:";
  }

  const token = getAccessToken();
  const params = token ? `?token=${encodeURIComponent(token)}` : "";
  return `${proto}//${host}/ws/events${params}`;
}

function _connect(): void {
  if (_ws) return;
  _intentionallyClosed = false;

  const url = getWsUrl();
  if (!url) {
    logger.warn("WS", "No WebSocket URL available, skipping connection");
    _scheduleReconnect();
    return;
  }

  try {
    _ws = new WebSocket(url);
  } catch (e) {
    logger.error("WS", "Failed to create WebSocket", { url, error: String(e) });
    _scheduleReconnect();
    return;
  }

  _ws.onopen = () => {
    _connected = true;
    _reconnectDelay = 1000;
    _reconnectAttempts = 0;
    logger.info("WS", "Connected", { url });
  };

  _ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      const event = msg.event as string;
      const data = msg.data;
      if (event === "ping") {
        _ws?.send("ping");
        return;
      }
      for (const handler of _handlers) {
        try {
          handler(event, data);
        } catch (e) {
          logger.error("WS", "Event handler error", { error: String(e) });
        }
      }
    } catch { /* ignore non-JSON */ }
  };

  _ws.onclose = (ev) => {
    _ws = null;
    _connected = false;
    if (!_intentionallyClosed) {
      logger.warn("WS", "Connection closed", { code: ev.code, reason: ev.reason, url });
      _scheduleReconnect();
    }
  };

  _ws.onerror = () => {
    logger.error("WS", "Connection error", { url });
    _ws?.close();
  };
}

function _scheduleReconnect(): void {
  if (_reconnectTimer || _intentionallyClosed) return;
  _reconnectAttempts++;
  if (_reconnectAttempts > MAX_RECONNECT_ATTEMPTS) {
    logger.warn("WS", `Gave up reconnecting after ${MAX_RECONNECT_ATTEMPTS} attempts`);
    return;
  }
  _reconnectTimer = setTimeout(async () => {
    _reconnectTimer = null;
    _reconnectDelay = Math.min(_reconnectDelay * 2, 30000);
    const token = getAccessToken();
    if (!token || isTokenExpiringSoon(token, 60)) {
      await refreshAccessToken().catch(() => {});
    }
    _connect();
  }, _reconnectDelay);
}

/**
 * Subscribe to all WebSocket events. Returns unsubscribe function.
 */
export function onWsEvent(handler: WsEventHandler): () => void {
  _handlers.push(handler);
  // Ensure connection is started
  if (!_ws && !_reconnectTimer) {
    _connect();
  }

  return () => {
    _handlers = _handlers.filter((h) => h !== handler);
    // If no more handlers, disconnect
    if (_handlers.length === 0) {
      disconnectWs();
    }
  };
}

export function disconnectWs(): void {
  _intentionallyClosed = true;
  _reconnectAttempts = 0;
  if (_reconnectTimer) {
    clearTimeout(_reconnectTimer);
    _reconnectTimer = null;
  }
  if (_ws) {
    _ws.close();
    _ws = null;
  }
  _connected = false;
}

/**
 * Immediately reconnect WebSocket (e.g. after app returns from background).
 * Resets backoff and attempts counter. No-op if no handlers are registered.
 */
export function reconnectWsNow(): void {
  _intentionallyClosed = false;
  if (_reconnectTimer) {
    clearTimeout(_reconnectTimer);
    _reconnectTimer = null;
  }
  _reconnectDelay = 1000;
  _reconnectAttempts = 0;
  if (_ws) {
    try { _ws.close(); } catch { /* ignore */ }
    _ws = null;
  }
  _connected = false;
  if (_handlers.length > 0) _connect();
}

export function isWsConnected(): boolean {
  return _connected;
}
