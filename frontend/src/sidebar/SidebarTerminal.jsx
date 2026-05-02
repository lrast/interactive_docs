import { useEffect, useRef } from "react";
import { FitAddon } from "xterm-addon-fit";
import { Terminal } from "xterm";
import "xterm/css/xterm.css";
import {
  getLastTerminalRunRequest,
  subscribeTerminalRun,
} from "../state/terminalRunStore.js";

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
    let cancelled = false;
    const pendingSends = [];

    const onData = (data) => {
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send(data);
      }
    };
    term.onData(onData);

    const onMessage = (ev) => {
      if (typeof ev.data === "string") {
        term.write(ev.data);
      } else if (ev.data instanceof ArrayBuffer) {
        term.write(new TextDecoder("utf-8", { fatal: false }).decode(ev.data));
      }
    };

    const sendRunRequest = (req) => {
      if (!req?.text) return;
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send(req.text);
      } else {
        pendingSends.push(req.text);
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

    const onPageHide = () => killSandbox();
    const onVisibilityChange = () => {
      if (document.visibilityState === "hidden") killSandbox();
    };

    window.addEventListener("pagehide", onPageHide);
    document.addEventListener("visibilitychange", onVisibilityChange);

    const startSocket = async () => {
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
      socket = new WebSocket(url);
      socket.addEventListener("message", onMessage);

      socket.addEventListener("open", () => {
        fitAddon.fit();
        sendResize(socket, term);
        term.focus();
        while (pendingSends.length) {
          socket.send(pendingSends.shift());
        }
      });
    };

    startSocket();

    return () => {
      cancelled = true;
      killSandbox();
      unsubscribeRun();
      window.removeEventListener("resize", onWinResize);
      window.removeEventListener("pagehide", onPageHide);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      ro.disconnect();
      socket?.removeEventListener("message", onMessage);
      try {
        socket?.close();
      } catch {
        /* ignore */
      }
      term.dispose();
    };
  }, []);

  return <div className="sidebar-terminal-host" ref={hostRef} />;
}
