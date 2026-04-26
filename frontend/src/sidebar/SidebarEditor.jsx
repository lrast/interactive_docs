import { useEffect, useRef } from "react";
import { EditorState } from "@codemirror/state";
import { EditorView, basicSetup } from "codemirror";
import { python } from "@codemirror/lang-python";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { tags } from "@lezer/highlight";
import {
  getEditorContent,
  setEditorContent,
  subscribeEditorContent,
} from "../state/editorContentStore.js";
import { requestTerminalRun } from "../state/terminalRunStore.js";

const defaultDoc = '';

const ipythonHighlightStyle = HighlightStyle.define([
  { tag: tags.keyword, color: "#0000FF", fontWeight: "600" },
  { tag: [tags.string, tags.special(tags.string)], color: "#008000" },
  { tag: tags.comment, color: "#408080", fontStyle: "italic" },
  { tag: [tags.number, tags.bool, tags.null], color: "#0000FF" },
  { tag: tags.function(tags.variableName), color: "#0000FF" },
  { tag: tags.typeName, color: "#2B91AF" },
  { tag: tags.definition(tags.variableName), color: "#000000" },
  { tag: tags.operator, color: "#AA22FF" },
  { tag: tags.punctuation, color: "#000000" },
]);

const editorTheme = EditorView.theme(
  {
    "&": {
      height: "100%",
      fontSize: "13px",
      backgroundColor: "var(--color-code-bg)",
      color: "var(--color-text)",
    },
    ".cm-scroller": { overflow: "auto" },
    ".cm-content": { caretColor: "var(--color-text)" },
    ".cm-gutters": {
      backgroundColor: "var(--color-surface)",
      color: "var(--color-text-muted)",
      borderColor: "var(--color-border)",
    },
    ".cm-activeLineGutter": {
      backgroundColor: "var(--color-surface-raised)",
    },
    ".cm-activeLine": {
      backgroundColor: "var(--color-surface-raised)",
    },
    ".cm-selectionBackground": {
      backgroundColor: "rgba(236, 236, 240, 0.12) !important",
    },
    "&.cm-focused .cm-selectionBackground": {
      backgroundColor: "rgba(236, 236, 240, 0.18) !important",
    },
    "&.cm-focused .cm-cursor": {
      borderLeftColor: "var(--color-text)",
    },
  },
  { dark: true },
);

export function SidebarEditor() {
  const hostRef = useRef(null);
  const viewRef = useRef(null);
  const publishTimerRef = useRef(null);

  useEffect(() => {
    const parent = hostRef.current;
    if (!parent) return;

    // Ensure other roots can read an initial snapshot.
    setEditorContent(defaultDoc);

    const state = EditorState.create({
      doc: defaultDoc,
      extensions: [
        basicSetup,
        python(),
        editorTheme,
        syntaxHighlighting(ipythonHighlightStyle),
        EditorView.updateListener.of((update) => {
          if (!update.docChanged) return;
          if (publishTimerRef.current) {
            window.clearTimeout(publishTimerRef.current);
          }
          // Debounce: keep global snapshot reasonably fresh without
          // pushing on every single keystroke.
          publishTimerRef.current = window.setTimeout(() => {
            setEditorContent(update.state.doc.toString());
          }, 75);
        }),
      ],
    });

    const view = new EditorView({ state, parent });
    viewRef.current = view;

    const syncFromStore = () => {
      const next = getEditorContent();
      const current = view.state.doc.toString();
      if (next === current) return;
      view.dispatch({
        changes: { from: 0, to: view.state.doc.length, insert: next },
      });
    };
    const unsubscribe = subscribeEditorContent(syncFromStore);
    // In case something updated the store before we subscribed.
    syncFromStore();

    return () => {
      unsubscribe();
      viewRef.current = null;
      if (publishTimerRef.current) {
        window.clearTimeout(publishTimerRef.current);
        publishTimerRef.current = null;
      }
      view.destroy();
    };
  }, []);

  const run = () => {
    const view = viewRef.current;
    if (!view) return;
    const code = view.state.doc.toString();
    setEditorContent(code);
    const trimmed = code.replace(/\n+$/g, "");
    const command = `${trimmed}\n\n`;
    requestTerminalRun(command);
  };

  const buttonStyle = {
    fontSize: 12,
    padding: "6px 10px",
    borderRadius: 8,
    border: "1px solid var(--color-border)",
    background: "var(--color-surface-raised)",
    color: "var(--color-text)",
    cursor: "pointer",
  };

  return (
    <>
      <div className="sidebar-editor-host" ref={hostRef} />
      <div
        style={{
          display: "flex",
          justifyContent: "flex-end",
          gap: 8,
          marginBottom: 8,
        }}
      >
        <button type="button" onClick={run} style={buttonStyle}>
          Run
        </button>
      </div>
    </>
  );
}
