import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ThemeProvider, CssBaseline } from "@mui/material";
import App from "./App.jsx";
import { SidebarEditor } from "./sidebar/SidebarEditor.jsx";
import { appTheme } from "./theme.js";
import "./App.css";

function shell(children) {
  return (
    <StrictMode>
      <ThemeProvider theme={appTheme}>{children}</ThemeProvider>
    </StrictMode>
  );
}

const chatEl = document.getElementById("react-root");
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
