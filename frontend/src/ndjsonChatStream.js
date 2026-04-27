/**
 * Converts a UTF-8 newline-delimited JSON stream into parsed chunk objects
 * for MUI X Chat's stream processor.
 */
export function parseNdjsonObjectStream() {
  let carry = "";
  return new TransformStream({
    transform(chunk, controller) {
      if (typeof chunk !== "string") {
        controller.enqueue({
          type: "ndjson-chunk-type-error",
          message: "Expected decoded text chunk (string).",
          chunkType: typeof chunk,
        });
        return;
      }

      carry += chunk;
      const lines = carry.split("\n");
      carry = lines.pop() ?? "";
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        try {
          controller.enqueue(JSON.parse(trimmed));
        } catch (err) {
          controller.enqueue({
            type: "ndjson-parse-error",
            message: err instanceof Error ? err.message : String(err),
            line: trimmed,
          });
        }
      }
    },
    flush(controller) {
      const trimmed = carry.trim();
      if (trimmed) {
        try {
          controller.enqueue(JSON.parse(trimmed));
        } catch (err) {
          controller.enqueue({
            type: "ndjson-parse-error",
            message: err instanceof Error ? err.message : String(err),
            line: trimmed,
          });
        }
      }
    },
  });
}
