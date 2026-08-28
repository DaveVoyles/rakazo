import { describe, expect, it } from "vitest";
import { parseLeakedToolCall, shouldHoldLeakedToolText } from "./leaked-tool-call.js";

const ALLOWED = ["scratchpad_complete", "broadcast_to_fleet", "vault_search", "list_files"] as const;

describe("parseLeakedToolCall", () => {
  it("recovers the Shopping-bot leak shape", () => {
    const leaked = `{
  "name": "scratchpad_complete",
  "arguments": {
    "itemId": "cmta1mtd50026m7nr8i36nik7"
  }
}`;
    expect(parseLeakedToolCall(leaked, ALLOWED)).toEqual({
      name: "scratchpad_complete",
      args: { itemId: "cmta1mtd50026m7nr8i36nik7" },
    });
  });

  it("accepts parameters and fenced JSON", () => {
    const fenced = "```json\n{\"name\":\"vault_search\",\"parameters\":{\"query\":\"Paladin\"}}\n```";
    expect(parseLeakedToolCall(fenced, ALLOWED)).toEqual({
      name: "vault_search",
      args: { query: "Paladin" },
    });
  });

  it("accepts OpenAI function envelope and stringified arguments", () => {
    const envelope = JSON.stringify({
      function: { name: "broadcast_to_fleet", arguments: "{\"channel\":\"announcements\"}" },
    });
    expect(parseLeakedToolCall(envelope, ALLOWED)).toEqual({
      name: "broadcast_to_fleet",
      args: { channel: "announcements" },
    });
  });

  it("recovers {function: name} string shape instead of painting it", () => {
    expect(
      parseLeakedToolCall('{"function": "list_files", "arguments": {"path": "."}}', ALLOWED),
    ).toEqual({
      name: "list_files",
      args: { path: "." },
    });
  });

  it("rejects unknown tool names", () => {
    expect(parseLeakedToolCall('{"name":"rm_rf","arguments":{}}', ALLOWED)).toBeNull();
  });

  it("rejects prose-wrapped JSON so examples are not executed", () => {
    const prose = `Call this next:\n{"name":"scratchpad_complete","arguments":{"itemId":"x"}}`;
    expect(parseLeakedToolCall(prose, ALLOWED)).toBeNull();
  });

  it("rejects JSON arrays and non-objects", () => {
    expect(parseLeakedToolCall('[{"name":"vault_search"}]', ALLOWED)).toBeNull();
    expect(parseLeakedToolCall('"vault_search"', ALLOWED)).toBeNull();
  });
});

describe("shouldHoldLeakedToolText", () => {
  it("holds a JSON or fence prefix and releases prose", () => {
    expect(shouldHoldLeakedToolText("{")).toBe(true);
    expect(shouldHoldLeakedToolText("```json\n{")).toBe(true);
    expect(shouldHoldLeakedToolText("I'll send a message to Shopping.")).toBe(false);
    expect(shouldHoldLeakedToolText("")).toBe(false);
  });
});
