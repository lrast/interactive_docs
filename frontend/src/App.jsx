import * as React from "react";
import Box from "@mui/material/Box";
import Alert from "@mui/material/Alert";
import Snackbar from "@mui/material/Snackbar";
import { ChatRoot } from "@mui/x-chat-headless";
import { createChatAdapter } from "./chatAdapter.js";
import ChatThread from "./chat/ChatThread.jsx";
import {
  clearFlashMessage,
  getFlashMessage,
  subscribeFlash,
} from "./state/flashStore.js";

const adapter = createChatAdapter();

export default function App() {
  const flashMessage = React.useSyncExternalStore(
    subscribeFlash,
    getFlashMessage,
    getFlashMessage,
  );

  return (
    <Box sx={{ height: "100%", minHeight: 0 }}>
      <ChatRoot
        adapter={adapter}
        variant="compact"
        density="compact"
        initialConversations={[{ id: "main", title: "Assistant" }]}
        initialActiveConversationId="main"
        slotProps={{
          root: {
            sx: {
              height: "100%",
              minHeight: 0,
              display: "flex",
              flexDirection: "column",
              bgcolor: "background.paper",
            },
          },
        }}
      >
        <ChatThread />
      </ChatRoot>

      <Snackbar
        open={typeof flashMessage === "string" && flashMessage.length > 0}
        autoHideDuration={4000}
        onClose={() => clearFlashMessage()}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        <Alert
          onClose={() => clearFlashMessage()}
          severity="error"
          variant="filled"
          sx={{ width: "100%" }}
        >
          {flashMessage}
        </Alert>
      </Snackbar>
    </Box>
  );
}
