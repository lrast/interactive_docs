import { useEffect, useRef } from "react";
import { FitAddon } from "xterm-addon-fit";
import { Terminal } from "xterm";
import "xterm/css/xterm.css";
import {
  getLastTerminalRunRequest,
  subscribeTerminalRun,
} from "../state/terminalRunStore.js";

const PING_INTERVAL_MS = 45_000;
const RECONNECT_DELAY_MS = 400;

function terminalWsUrl() {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/ws/terminal`;
}

function sendResize(socket, term) {
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(
      JSON.stringify({
        type: "resize",
        cols: term.cols,
        rows: term.rows,
      }),
    );
  }
}

export function SidebarTerminal() {
  const hostRef = useRef(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    const term = new Terminal({
      cursorBlink: true,
      fontSize: 13,
      fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
      theme: {
        background: "#25252c",
        foreground: "#ececf0",
        cursor: "#ececf0",
        selectionBackground: "rgba(236, 236, 240, 0.2)",
      },
    });
    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(host);
    fitAddon.fit();

    let socket = null;
    let boundHandlers = null;
    let cancelled = false;
    const pendingSends = [];
    let pingTimer = null;
    let reconnectTimer = null;
    let sawDisconnect = false;

    const clearPingTimer = () => {
      if (pingTimer != null) {
        clearInterval(pingTimer);
        pingTimer = null;
      }
    };

    const clearReconnectTimer = () => {
      if (reconnectTimer != null) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
    };

    const startPingIfVisible = () => {
      clearPingTimer();
      if (document.visibilityState !== "visible") return;
      pingTimer = setInterval(() => {
        if (cancelled || document.visibilityState !== "visible") return;
        if (socket?.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify({ type: "ping" }));
        }
      }, PING_INTERVAL_MS);
    };

    const scheduleReconnect = () => {
      if (cancelled) return;
      clearReconnectTimer();
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        if (cancelled) return;
        connectSocket();
      }, RECONNECT_DELAY_MS);
    };

    const detachSocketHandlers = (ws, handlers) => {
      if (!ws || !handlers) return;
      ws.removeEventListener("message", handlers.onMessage);
      ws.removeEventListener("open", handlers.onOpen);
      ws.removeEventListener("close", handlers.onClose);
      ws.removeEventListener("error", handlers.onError);
    };

    const onMessage = (ev) => {
      if (typeof ev.data === "string") {
        term.write(ev.data);
      } else if (ev.data instanceof ArrayBuffer) {
        term.write(new TextDecoder("utf-8", { fatal: false }).decode(ev.data));
      }
    };

    const onData = (data) => {
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send(data);
      } else if (!cancelled) {
        pendingSends.push(data);
        scheduleReconnect();
      }
    };
    term.onData(onData);

    const sendRunRequest = (req) => {
      if (!req?.text) return;
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send(req.text);
      } else {
        pendingSends.push(req.text);
        scheduleReconnect();
      }
    };

    const unsubscribeRun = subscribeTerminalRun(sendRunRequest);
    const initial = getLastTerminalRunRequest();
    if (initial) sendRunRequest(initial);

    const ro = new ResizeObserver(() => {
      fitAddon.fit();
      sendResize(socket, term);
    });
    ro.observe(host);

    const onWinResize = () => {
      fitAddon.fit();
      sendResize(socket, term);
    };
    window.addEventListener("resize", onWinResize);

    let sentKill = false;
    const killSandbox = () => {
      if (sentKill) return;
      sentKill = true;
      try {
        const body = new Blob(["{}"], { type: "application/json" });
        if (navigator?.sendBeacon) {
          navigator.sendBeacon("/api/terminal/kill", body);
          return;
        }
      } catch {
        // ignore
      }
      try {
        fetch("/api/terminal/kill", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{}",
          credentials: "same-origin",
          keepalive: true,
        });
      } catch {
        // ignore
      }
    };

    const onVisibilityChange = () => {
      if (document.visibilityState === "hidden") {
        clearPingTimer();
        return;
      }
      if (cancelled) return;
      if (socket?.readyState === WebSocket.OPEN) {
        startPingIfVisible();
      }
    };
    document.addEventListener("visibilitychange", onVisibilityChange);

    const connectSocket = async () => {
      if (cancelled) return;
      clearPingTimer();
      clearReconnectTimer();

      if (socket) {
        detachSocketHandlers(socket, boundHandlers);
        try {
          socket.close();
        } catch {
          /* ignore */
        }
        socket = null;
        boundHandlers = null;
      }

      let token = "";
      try {
        const res = await fetch("/api/terminal/token", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{}",
          credentials: "same-origin",
        });
        if (res.ok) {
          const json = await res.json();
          token = typeof json?.token === "string" ? json.token : "";
        }
      } catch {
        // ignore; local dev may not require token
      }

      if (cancelled) return;

      const base = terminalWsUrl();
      const url = token ? `${base}?token=${encodeURIComponent(token)}` : base;
      const ws = new WebSocket(url);

      const onOpen = () => {
        if (socket !== ws) return;
        fitAddon.fit();
        sendResize(ws, term);
        term.focus();
        while (pendingSends.length) {
          ws.send(pendingSends.shift());
        }
        if (sawDisconnect) {
          term.writeln(
            "\r\n\x1b[90m[Terminal: connected — new backend session (previous connection ended).]\x1b[0m",
          );
          sawDisconnect = false;
        }
        startPingIfVisible();
      };

      const handlers = {
        onMessage,
        onOpen,
        onClose: () => {
          if (cancelled) return;
          detachSocketHandlers(ws, handlers);
          if (socket !== ws) return;
          socket = null;
          boundHandlers = null;
          sawDisconnect = true;
          clearPingTimer();
          term.writeln(
            "\r\n\x1b[90m[Terminal: session ended — type here to connect again.]\x1b[0m",
          );
        },
        onError: () => {
          // Browser typically emits `close` after `error`.
        },
      };

      ws.addEventListener("message", handlers.onMessage);
      ws.addEventListener("open", handlers.onOpen);
      ws.addEventListener("close", handlers.onClose);
      ws.addEventListener("error", handlers.onError);
      boundHandlers = handlers;
      socket = ws;
    };

    connectSocket();

    return () => {
      cancelled = true;
      clearPingTimer();
      clearReconnectTimer();
      killSandbox();
      unsubscribeRun();
      window.removeEventListener("resize", onWinResize);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      ro.disconnect();
      if (socket) {
        detachSocketHandlers(socket, boundHandlers);
        try {
          socket.close();
        } catch {
          /* ignore */
        }
      }
      socket = null;
      boundHandlers = null;
      term.dispose();
    };
  }, []);

  return <div className="sidebar-terminal-host" ref={hostRef} />;
}
