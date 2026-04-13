/**
 * Converts a UTF-8 newline-delimited JSON stream into parsed chunk objects
 * for MUI X Chat's stream processor.
 */
export function parseNdjsonObjectStream() {
  let carry = "";
  return new TransformStream({
    transform(chunk, controller) {
      carry += chunk;
      const lines = carry.split("\n");
      carry = lines.pop() ?? "";
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        controller.enqueue(JSON.parse(trimmed));
      }
    },
    flush(controller) {
      const trimmed = carry.trim();
      if (trimmed) {
        controller.enqueue(JSON.parse(trimmed));
      }
    },
  });
}
