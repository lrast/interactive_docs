import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ThemeProvider, CssBaseline } from "@mui/material";
import App from "./App.jsx";
import { SidebarEditor } from "./sidebar/SidebarEditor.jsx";
import { SidebarTerminal } from "./sidebar/SidebarTerminal.jsx";
import { appTheme } from "./theme.js";
import { initMainDocIframe } from "./state/mainDocIframeStore.js";
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
