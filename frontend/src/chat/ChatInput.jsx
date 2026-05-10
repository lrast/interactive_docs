import SendIcon from "@mui/icons-material/Send";
import {
  ChatComposer,
  ChatComposerSendButton,
  ChatComposerTextArea,
} from "@mui/x-chat";
import { useChatLocaleText } from "@mui/x-chat-headless";

/** Compact composer (input + send), MUI X Chat–styled. */
export function ChatInput() {
  const localeText = useChatLocaleText();
  return (
    <ChatComposer variant="compact">
      <ChatComposerTextArea
        maxRows={5}
        placeholder="Ask about a package"
      />
      <ChatComposerSendButton aria-label={localeText.composerSendButtonLabel}>
        <SendIcon fontSize="small" />
      </ChatComposerSendButton>
    </ChatComposer>
  );
}
