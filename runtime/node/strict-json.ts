/** Reject duplicate decoded keys before JSON.parse discards their evidence. */
export function strictObject(text: string): Record<string, unknown> {
  let offset = 0, nodes = 0;
  const whitespace = () => { while (/\s/.test(text[offset] ?? "") && offset < text.length) offset++; };
  function quoted(): string {
    const start = offset++;
    while (offset < text.length) {
      const char = text[offset++];
      if (char === "\\") offset++;
      else if (char === '"') return JSON.parse(text.slice(start, offset)) as string;
    }
    throw new Error("invalid_json");
  }
  function value(depth: number): void {
    if (depth > 24 || ++nodes > 100_000) throw new Error("invalid_json");
    whitespace();
    if (text[offset] === '"') { quoted(); return; }
    if (text[offset] === "{") {
      offset++; whitespace(); const keys = new Set<string>();
      if (text[offset] === "}") { offset++; return; }
      while (offset < text.length) {
        whitespace(); if (text[offset] !== '"') throw new Error("invalid_json");
        const key = quoted(); if (keys.has(key)) throw new Error("duplicate_json_key"); keys.add(key);
        whitespace(); if (text[offset++] !== ":") throw new Error("invalid_json");
        value(depth + 1); whitespace();
        const separator = text[offset++];
        if (separator === "}") return;
        if (separator !== ",") throw new Error("invalid_json");
      }
      throw new Error("invalid_json");
    }
    if (text[offset] === "[") {
      offset++; whitespace(); if (text[offset] === "]") { offset++; return; }
      while (offset < text.length) {
        value(depth + 1); whitespace(); const separator = text[offset++];
        if (separator === "]") return;
        if (separator !== ",") throw new Error("invalid_json");
      }
      throw new Error("invalid_json");
    }
    const start = offset;
    while (offset < text.length && !/[\s,}\]]/.test(text[offset]!)) offset++;
    if (offset === start) throw new Error("invalid_json");
  }
  value(0); whitespace(); if (offset !== text.length) throw new Error("invalid_json");
  const result: unknown = JSON.parse(text);
  if (!result || typeof result !== "object" || Array.isArray(result)) throw new Error("invalid_json");
  return result as Record<string, unknown>;
}
