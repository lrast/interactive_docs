import { parseNdjsonObjectStream } from "./ndjsonChatStream.js";
import { getEditorContent } from "./state/editorContentStore.js";
import { setEditorContent } from "./state/editorContentStore.js";
import { setMainDocIframeSrc } from "./state/mainDocIframeStore.js";

function applyUiStateFromChunk(chunk) {
  if (!chunk || typeof chunk !== "object") return;

  if (typeof chunk.editorContent === "string") {
    setEditorContent(chunk.editorContent);
  }

  if (typeof chunk.displayedUrl === "string") {
    setMainDocIframeSrc(chunk.displayedUrl);
  }
}

export function createChatAdapter() {
  return {
    async sendMessage({ message, conversationId, signal }) {
      const res = await fetch("/api/chat", {
        method: "POST",
        credentials: "include",
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
        .pipeThrough(parseNdjsonObjectStream())
        .pipeThrough(
          new TransformStream({
            transform(chunk, controller) {
              applyUiStateFromChunk(chunk);
              controller.enqueue(chunk);
            },
          }),
        );
    },
  };
}
