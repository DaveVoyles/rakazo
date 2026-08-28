export type LeakedToolCall = {
  name: string;
  args: Record<string, unknown>;
};

/**
 * True while streamed text still looks like a lone tool-call JSON blob
 * (or a fenced JSON blob). Used to hold local-model streaming so leaked
 * JSON is not painted into chat before we can intercept it.
 */
export function shouldHoldLeakedToolText(text: string): boolean {
  const trimmed = text.trim();
  if (!trimmed) return false;
  return trimmed.startsWith("{") || trimmed.startsWith("```");
}

/**
 * Parse assistant text that is *only* a tool-call JSON object.
 * Rejects prose-wrapped JSON, arrays, and unknown tool names so example
 * snippets in markdown are never executed.
 */
export function parseLeakedToolCall(
  text: string,
  allowedNames: ReadonlySet<string> | readonly string[],
): LeakedToolCall | null {
  const allowed = allowedNames instanceof Set ? allowedNames : new Set(allowedNames);
  const candidate = unwrapWholeJson(text);
  if (!candidate) return null;

  let parsed: unknown;
  try {
    parsed = JSON.parse(candidate);
  } catch {
    return null;
  }
  const record = asRecord(parsed);
  if (!record) return null;
  const name = toolNameFrom(record);
  if (!name || !allowed.has(name)) return null;

  const args = toolArgsFrom(record);
  if (!args) return null;
  return { name, args };
}

function unwrapWholeJson(text: string): string | null {
  let trimmed = text.trim();
  if (!trimmed) return null;

  const fence = trimmed.match(/^```(?:json)?\s*\n?([\s\S]*?)\n?```$/);
  if (fence) trimmed = fence[1]!.trim();

  if (!trimmed.startsWith("{") || !trimmed.endsWith("}")) return null;
  return trimmed;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function toolNameFrom(record: Record<string, unknown>): string | null {
  if (typeof record.name === "string" && record.name.trim()) return record.name.trim();
  if (typeof record.tool === "string" && record.tool.trim()) return record.tool.trim();
  if (typeof record.function === "string" && record.function.trim()) {
    return record.function.trim();
  }
  const fn = asRecord(record.function);
  if (fn && typeof fn.name === "string" && fn.name.trim()) return fn.name.trim();
  return null;
}

function toolArgsFrom(record: Record<string, unknown>): Record<string, unknown> | null {
  let raw: unknown = record.arguments ?? record.parameters ?? record.args;
  if (raw === undefined) {
    const fn = asRecord(record.function);
    raw = fn?.arguments;
  }
  if (raw === undefined || raw === null) return {};
  if (typeof raw === "string") {
    try {
      return asRecord(JSON.parse(raw));
    } catch {
      return null;
    }
  }
  return asRecord(raw);
}
