import { parseNdjsonObjectStream } from "./ndjsonChatStream.js";
import { getEditorContent } from "./state/editorContentStore.js";

export function createChatAdapter() {
  return {
    async sendMessage({ message, conversationId, signal }) {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/x-ndjson",
        },
        body: JSON.stringify({
          conversationId,
          editorContent: getEditorContent(),
          message: {
            id: message.id,
            role: message.role,
            parts: message.parts,
          },
        }),
        signal,
      });
      if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(text || `Chat request failed (${res.status})`);
      }
      if (!res.body) {
        throw new Error("No response body");
      }
      return res.body
        .pipeThrough(new TextDecoderStream())
        .pipeThrough(parseNdjsonObjectStream());
    },
  };
}
