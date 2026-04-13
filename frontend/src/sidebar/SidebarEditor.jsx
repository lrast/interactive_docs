import { useEffect, useRef } from "react";
import { EditorState } from "@codemirror/state";
import { EditorView, basicSetup } from "codemirror";
import { python } from "@codemirror/lang-python";

const defaultDoc = `# Sample
import math

def greet(name: str) -> str:
    return f"Hello, {name}"
`;

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

  useEffect(() => {
    const parent = hostRef.current;
    if (!parent) return;

    const state = EditorState.create({
      doc: defaultDoc,
      extensions: [basicSetup, python(), editorTheme],
    });

    const view = new EditorView({ state, parent });
    return () => view.destroy();
  }, []);

  return <div className="sidebar-editor-host" ref={hostRef} />;
}
