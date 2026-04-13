import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ThemeProvider, CssBaseline } from "@mui/material";
import App from "./App.jsx";
import { appTheme } from "./theme.js";
import "./App.css";

const el = document.getElementById("react-root");
if (el) {
  createRoot(el).render(
    <StrictMode>
      <ThemeProvider theme={appTheme}>
        <CssBaseline />
        <App />
      </ThemeProvider>
    </StrictMode>,
  );
}
