import { createTheme } from "@mui/material/styles";

/** Dark theme aligned with `app/static/css/style.css` shell variables. */
export const appTheme = createTheme({
  palette: {
    mode: "dark",
    primary: { main: "#8ab4ff" },
    background: {
      default: "#0d0d0f",
      paper: "#141418",
    },
    divider: "#2a2a32",
    text: {
      primary: "#ececf0",
      secondary: "#9898a4",
    },
  },
  shape: {
    borderRadius: 10,
  },
});
