import Box from "@mui/material/Box";

/** Outermost chat shell: fills the bar and lays out children in a column. */
export function ChatContainer({ children }) {
  return (
    <Box
      component="section"
      aria-label="Chat"
      sx={{
        height: "100%",
        flex: 1,
        display: "flex",
        flexDirection: "column",
        minHeight: 0,
      }}
    >
      {children}
    </Box>
  );
}
