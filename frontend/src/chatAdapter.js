import { parseNdjsonObjectStream } from "./ndjsonChatStream.js";
import { getEditorContent } from "./state/editorContentStore.js";
import { setEditorContent } from "./state/editorContentStore.js";
import {
  applyMainDocIframeResponseUiState,
  renderMainDocIframeFallback,
  setMainDocIframeFallbackHtml,
  setMainDocIframeSrc,
} from "./state/mainDocIframeStore.js";
import { setFlashMessage } from "./state/flashStore.js";

function applyUiStateFromChunk(chunk) {
  if (!chunk || typeof chunk !== "object") return;

  if (
    chunk.type &&
    chunk.type !== "ui-state" &&
    chunk.type !== "finish" &&
    typeof chunk.editorContent !== "string" &&
    typeof chunk.displayedUrl !== "string" &&
    typeof chunk.useFallback !== "boolean" &&
    typeof chunk.fallbackHtml !== "string" &&
    typeof chunk.flashMessage !== "string"
  ) {
    return;
  }

  if (typeof chunk.editorContent === "string") {
    setEditorContent(chunk.editorContent);
  }

  if (typeof chunk.fallbackHtml === "string") {
    setMainDocIframeFallbackHtml(chunk.fallbackHtml);
  }

  if (typeof chunk.displayedUrl === "string" || typeof chunk.useFallback === "boolean") {
    applyMainDocIframeResponseUiState({
      displayedUrl: typeof chunk.displayedUrl === "string" ? chunk.displayedUrl : undefined,
      useFallback: typeof chunk.useFallback === "boolean" ? chunk.useFallback : undefined,
    });
  }

  if (typeof chunk.flashMessage === "string") {
    setFlashMessage(chunk.flashMessage);
  }

  // Deterministic render decision: backend decides embeddability.
  if (chunk.useFallback === true) {
    renderMainDocIframeFallback(
      typeof chunk.fallbackHtml === "string" ? chunk.fallbackHtml : undefined,
    );
  } else if (chunk.useFallback === false && typeof chunk.displayedUrl === "string") {
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
