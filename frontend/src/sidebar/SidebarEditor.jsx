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

const monokai = {
  background: "#272822",
  foreground: "#F8F8F2",
  caret: "#F8F8F0",
  selection: "#49483E",
  lineHighlight: "#3E3D32",
  gutterBackground: "#2D2E27",
  gutterForeground: "#8F908A",
  comment: "#75715E",
  keyword: "#F92672",
  string: "#E6DB74",
  number: "#AE81FF",
  type: "#66D9EF",
  function: "#A6E22E",
  constant: "#AE81FF",
  variable: "#F8F8F2",
  operator: "#F8F8F2",
  punctuation: "#F8F8F2",
  invalid: "#F8F8F2",
};

const monokaiHighlightStyle = HighlightStyle.define([
  { tag: tags.comment, color: monokai.comment, fontStyle: "italic" },

  { tag: [tags.keyword, tags.modifier, tags.self, tags.operatorKeyword], color: monokai.keyword, fontWeight: "600" },
  { tag: [tags.string, tags.special(tags.string), tags.regexp], color: monokai.string },
  { tag: [tags.number, tags.bool, tags.null], color: monokai.number },
  { tag: [tags.typeName, tags.className], color: monokai.type },
  { tag: [tags.function(tags.variableName), tags.function(tags.definition(tags.variableName))], color: monokai.function },
  { tag: [tags.variableName, tags.propertyName], color: monokai.variable },
  { tag: [tags.definition(tags.variableName), tags.labelName], color: "#FD971F" },

  { tag: tags.atom, color: monokai.constant },
  { tag: tags.operator, color: monokai.operator },
  { tag: tags.punctuation, color: monokai.punctuation },

  { tag: tags.invalid, color: monokai.invalid },
]);

const editorTheme = EditorView.theme(
  {
    "&": {
      height: "100%",
      fontSize: "13px",
      backgroundColor: monokai.background,
      color: monokai.foreground,
    },
    ".cm-scroller": { overflow: "auto" },
    ".cm-content": { caretColor: monokai.caret },
    ".cm-gutters": {
      backgroundColor: monokai.gutterBackground,
      color: monokai.gutterForeground,
      border: "none",
    },
    ".cm-activeLineGutter": {
      backgroundColor: monokai.lineHighlight,
    },
    ".cm-activeLine": {
      backgroundColor: monokai.lineHighlight,
    },
    ".cm-selectionBackground": {
      backgroundColor: `${monokai.selection} !important`,
    },
    "&.cm-focused .cm-selectionBackground": {
      backgroundColor: `${monokai.selection} !important`,
    },
    "&.cm-focused .cm-cursor": {
      borderLeftColor: monokai.caret,
    },
    "&.cm-focused .cm-selectionMatch": {
      backgroundColor: `${monokai.selection}66`,
    },
    ".cm-matchingBracket, &.cm-focused .cm-matchingBracket": {
      backgroundColor: `${monokai.selection}AA`,
      color: monokai.foreground,
    },
    ".cm-nonmatchingBracket, &.cm-focused .cm-nonmatchingBracket": {
      backgroundColor: "#F9267240",
      color: monokai.foreground,
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
        syntaxHighlighting(monokaiHighlightStyle),
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
    if (!trimmed) return;
    // Wrap in bracketed paste so IPython treats the editor contents as a
    // single block (preserves indentation, no per-line auto-indent / exec).
    const PASTE_START = "\x1b[200~";
    const PASTE_END = "\x1b[201~";
    const command = `${PASTE_START}${trimmed}${PASTE_END}\r`;
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
