const IFRAME_ID = "main-doc-iframe";

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

export function setMainDocIframeSrc(src) {
  const iframe = getIframeEl();
  if (!iframe) return false;
  if (!isAllowedIframeSrc(src)) return false;
  iframe.setAttribute("src", src);
  return true;
}

export function initMainDocIframe({ exposeGlobalSetter = true } = {}) {
  if (exposeGlobalSetter) {
    // Allow other frontend code (or the console) to control the main iframe.
    window.setMainDocIframeSrc = setMainDocIframeSrc;
  }

  const iframe = getIframeEl();
  if (!iframe) return;

  const params = new URLSearchParams(window.location.search);
  const fromQuery = params.get("doc");
  if (fromQuery && setMainDocIframeSrc(fromQuery)) return;

  const initial = iframe.getAttribute("data-initial-src");
  if (initial) setMainDocIframeSrc(initial);
}

