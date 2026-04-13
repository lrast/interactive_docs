import * as React from "react";
import Box from "@mui/material/Box";
import {
  ChatConversation,
  ChatMessageContent,
  ChatMessageGroup,
  ChatMessageInlineMeta,
  ChatMessageList,
  ChatMessageMeta,
  ChatMessage,
  ChatScrollToBottomAffordance,
} from "@mui/x-chat";
import {
  useChatVariant,
  useMessage,
  useMessageIds,
} from "@mui/x-chat-headless";
import { ChatContainer } from "./ChatContainer.jsx";
import { ChatInput } from "./ChatInput.jsx";

/** Matches @mui/x-chat-headless MessageListRoot default; list viewport = N rows tall. */
const ESTIMATED_MESSAGE_ROW_PX = 42;
const MESSAGE_LIST_VIEWPORT_ROWS = 3;

function MessageRow({ id }) {
  const variant = useChatVariant();
  const message = useMessage(id);
  const isDefault = variant !== "compact";
  const isStreaming = message?.status === "streaming";
  const hasMeta =
    Boolean(message?.createdAt) ||
    Boolean(message?.editedAt) ||
    Boolean(message?.status);
  const inlineMeta =
    isDefault && !isStreaming && hasMeta ? (
      <ChatMessageInlineMeta />
    ) : undefined;

  return (
    <ChatMessageGroup
      messageId={id}
      sx={{ "--MuiChatMessage-avatarSize": "0px" }}
    >
      <ChatMessage messageId={id}>
        <ChatMessageContent afterContent={inlineMeta} />
        {!isDefault && <ChatMessageMeta />}
      </ChatMessage>
    </ChatMessageGroup>
  );
}

/**
 * Composed thread: ChatContainer > flex column > ChatConversation > message list + ChatInput.
 * Must render as a descendant of ChatRoot (chat store).
 */
export default function ChatThread() {
  const messageIds = useMessageIds();
  const renderItem = React.useCallback(
    ({ id }) => <MessageRow key={id} id={id} />,
    [],
  );

  return (
    <ChatContainer>
      <Box
        sx={{
          flexGrow: 1,
          display: "flex",
          flexDirection: "column",
          minHeight: 0,
        }}
      >
        <ChatConversation>
          <ChatMessageList
            items={messageIds}
            estimatedItemSize={ESTIMATED_MESSAGE_ROW_PX}
            renderItem={renderItem}
            autoScroll
            overlay={<ChatScrollToBottomAffordance />}
            sx={{
              flex: "0 0 auto",
              flexGrow: 0,
              height: MESSAGE_LIST_VIEWPORT_ROWS * ESTIMATED_MESSAGE_ROW_PX,
              maxHeight: MESSAGE_LIST_VIEWPORT_ROWS * ESTIMATED_MESSAGE_ROW_PX,
              minHeight: MESSAGE_LIST_VIEWPORT_ROWS * ESTIMATED_MESSAGE_ROW_PX,
            }}
          />
          <ChatInput />
        </ChatConversation>
      </Box>
    </ChatContainer>
  );
}
