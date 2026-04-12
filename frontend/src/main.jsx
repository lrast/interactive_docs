import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";

const el = document.getElementById("react-root");
if (el) {
  createRoot(el).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}
