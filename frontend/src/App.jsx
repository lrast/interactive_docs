import { ChatBox } from "@mui/x-chat";
import { createChatAdapter } from "./chatAdapter.js";

const adapter = createChatAdapter();

export default function App() {
  return (
    <ChatBox
      adapter={adapter}
      variant="compact"
      density="compact"
      initialConversations={[{ id: "main", title: "Assistant" }]}
      initialActiveConversationId="main"
      features={{
        attachments: false,
        helperText: false,
        conversationHeader: true,
        suggestions: false,
      }}
      sx={{
        height: "100%",
        minHeight: 0,
        borderRadius: 0,
        bgcolor: "background.paper",
      }}
    />
  );
}
