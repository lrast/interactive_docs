import { useEffect, useRef } from "react";
import { FitAddon } from "xterm-addon-fit";
import { Terminal } from "xterm";
import "xterm/css/xterm.css";

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

    const socket = new WebSocket(terminalWsUrl());

    const onData = (data) => {
      if (socket.readyState === WebSocket.OPEN) {
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
    socket.addEventListener("message", onMessage);

    socket.addEventListener("open", () => {
      fitAddon.fit();
      sendResize(socket, term);
      term.focus();
    });

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

    return () => {
      window.removeEventListener("resize", onWinResize);
      ro.disconnect();
      socket.removeEventListener("message", onMessage);
      try {
        socket.close();
      } catch {
        /* ignore */
      }
      term.dispose();
    };
  }, []);

  return <div className="sidebar-terminal-host" ref={hostRef} />;
}
