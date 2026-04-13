import Box from "@mui/material/Box";
import { ChatRoot } from "@mui/x-chat-headless";
import { createChatAdapter } from "./chatAdapter.js";
import ChatThread from "./chat/ChatThread.jsx";

const adapter = createChatAdapter();

export default function App() {
  return (
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
            bgcolor: "background.paper"
          },
        },
      }}
    >
      <ChatThread />
    </ChatRoot>
  );
}
