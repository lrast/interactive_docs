import * as React from "react";

let editorContent = "";
const listeners = new Set();

export function getEditorContent() {
  return editorContent;
}

export function setEditorContent(next) {
  const value = typeof next === "string" ? next : "";
  if (value === editorContent) return;
  editorContent = value;
  for (const l of listeners) l();
}

export function subscribeEditorContent(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useEditorContent() {
  return React.useSyncExternalStore(
    subscribeEditorContent,
    getEditorContent,
    getEditorContent,
  );
}
