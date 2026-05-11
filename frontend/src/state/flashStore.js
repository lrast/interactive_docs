let flashMessage = null;
const listeners = new Set();

export function getFlashMessage() {
  return flashMessage;
}

export function setFlashMessage(message) {
  const next = typeof message === "string" && message.trim() ? message.trim() : null;
  if (next === flashMessage) return;
  flashMessage = next;
  for (const fn of listeners) fn();
}

export function clearFlashMessage() {
  if (flashMessage === null) return;
  flashMessage = null;
  for (const fn of listeners) fn();
}

export function subscribeFlash(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

