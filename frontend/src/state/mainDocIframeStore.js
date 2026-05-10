const IFRAME_ID = "main-doc-iframe";

let useFallback = null;
let documentationUrl = "";
let fallbackHtml = "";
const listeners = new Set();

function emit() {
  for (const l of listeners) l();
}

function isAllowedIframeSrc(src) {
  if (typeof src !== "string") return false;
  const trimmed = src.trim();
  if (!trimmed) return false;
  try {
    const url = new URL(trimmed, window.location.href);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

function getIframeEl() {
  return document.getElementById(IFRAME_ID);
}

export function getMainDocIframeUseFallback() {
  return useFallback;
}

export function getMainDocIframeDocumentationUrl() {
  return documentationUrl;
}

export function subscribeMainDocIframe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function setMainDocIframeUseFallback(next) {
  if (typeof next !== "boolean") return false;
  if (next === useFallback) return true;
  useFallback = next;
  emit();
  return true;
}

/** Applies streamed UI fields in one notify so the status line never reads a mismatched pair. */
export function applyMainDocIframeResponseUiState(patch = {}) {
  const { displayedUrl, useFallback: nextUseFallback } = patch;
  let changed = false;
  if (typeof displayedUrl === "string") {
    const v = displayedUrl.trim();
    if (v !== documentationUrl) {
      documentationUrl = v;
      changed = true;
    }
  }
  if (typeof nextUseFallback === "boolean" && nextUseFallback !== useFallback) {
    useFallback = nextUseFallback;
    changed = true;
  }
  if (changed) emit();
  return true;
}

export function setMainDocIframeFallbackHtml(next) {
  const value = typeof next === "string" ? next : "";
  if (value === fallbackHtml) return true;
  fallbackHtml = value;
  emit();
  return true;
}

export function renderMainDocIframeFallback(html) {
  const iframe = getIframeEl();
  if (!iframe) return false;
  const content = typeof html === "string" ? html : fallbackHtml;
  if (!content) return false;

  iframe.removeAttribute("src");
  iframe.setAttribute("srcdoc", content);
  return true;
}

export function setMainDocIframeSrc(src) {
  const iframe = getIframeEl();
  if (!iframe) return false;
  if (!isAllowedIframeSrc(src)) return false;
  iframe.removeAttribute("srcdoc");
  iframe.setAttribute("src", src);
  return true;
}

export function initMainDocIframe({ exposeGlobalSetter = false } = {}) {
  if (exposeGlobalSetter) {
    // Allow other frontend code (or the console) to control the main iframe.
    window.setMainDocIframeSrc = setMainDocIframeSrc;
  } else if ("setMainDocIframeSrc" in window) {
    // Reduce accidental global surface area in prod (or when disabled).
    try {
      delete window.setMainDocIframeSrc;
    } catch {
      // Ignore if the property is non-configurable.
    }
  }

  const iframe = getIframeEl();
  if (!iframe) return;

  const params = new URLSearchParams(window.location.search);
  const fromQuery = params.get("doc");
  if (fromQuery && setMainDocIframeSrc(fromQuery)) return;

  const initial = iframe.getAttribute("data-initial-src");
  if (initial) setMainDocIframeSrc(initial);
}

