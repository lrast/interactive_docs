import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ThemeProvider, CssBaseline } from "@mui/material";
import App from "./App.jsx";
import { SidebarEditor } from "./sidebar/SidebarEditor.jsx";
import { SidebarTerminal } from "./sidebar/SidebarTerminal.jsx";
import { appTheme } from "./theme.js";
import {
  getMainDocIframeDocumentationUrl,
  getMainDocIframeUseFallback,
  initMainDocIframe,
  subscribeMainDocIframe,
} from "./state/mainDocIframeStore.js";
import "./App.css";

function shell(children) {
  return (
    <StrictMode>
      <ThemeProvider theme={appTheme}>{children}</ThemeProvider>
    </StrictMode>
  );
}

const IS_DEV = Boolean(import.meta?.env?.DEV);
initMainDocIframe({ exposeGlobalSetter: IS_DEV });

const chatEl = document.getElementById("main-chat-root");
if (chatEl) {
  createRoot(chatEl).render(
    shell(
      <>
        <CssBaseline />
        <App />
      </>,
    ),
  );
}

const sidebarEl = document.getElementById("sidebar-editor-root");
if (sidebarEl) {
  createRoot(sidebarEl).render(shell(<SidebarEditor />));
}

const terminalEl = document.getElementById("sidebar-terminal-root");
if (terminalEl) {
  createRoot(terminalEl).render(shell(<SidebarTerminal />));
}

initDocSourceStatusBar();

function initDocSourceStatusBar() {
  const el = document.getElementById("doc-source-status");
  if (!el) return;

  const render = () => {
    const useFb = getMainDocIframeUseFallback();
    const url = getMainDocIframeDocumentationUrl();
    if (useFb === null || typeof url !== "string" || !url.trim()) {
      el.hidden = true;
      el.replaceChildren();
      el.className = "doc-source-status";
      return;
    }
    let href;
    try {
      const u = new URL(url.trim(), window.location.href);
      if (u.protocol !== "http:" && u.protocol !== "https:") {
        el.hidden = true;
        el.replaceChildren();
        el.className = "doc-source-status";
        return;
      }
      href = u.href;
    } catch {
      el.hidden = true;
      el.replaceChildren();
      el.className = "doc-source-status";
      return;
    }

    el.hidden = false;
    el.replaceChildren();

    const link = () => {
      const a = document.createElement("a");
      a.href = href;
      a.textContent = "original";
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      return a;
    };

    if (useFb === false) {
      el.className = "doc-source-status doc-source-status--original";
      el.appendChild(link());
      return;
    }

    el.className = "doc-source-status doc-source-status--fallback";
    el.appendChild(document.createTextNode("Parsed from the "));
    el.appendChild(link());
  };

  subscribeMainDocIframe(render);
  render();
}
