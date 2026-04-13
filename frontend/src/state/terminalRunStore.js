let seq = 0;
let lastRequest = null;
const listeners = new Set();

export function requestTerminalRun(commandText) {
  const text = typeof commandText === "string" ? commandText : "";
  if (!text) return;
  seq += 1;
  lastRequest = { id: seq, text, at: Date.now() };
  for (const l of listeners) l(lastRequest);
}

export function subscribeTerminalRun(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getLastTerminalRunRequest() {
  return lastRequest;
}
