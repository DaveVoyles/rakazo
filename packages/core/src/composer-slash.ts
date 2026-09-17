export const SLASH_ACTIONS = [
  { id: "action-build" as const, label: "/build <idea> — Autonomous concept-to-merge pipeline" },
  { id: "action-work" as const, label: "/work <repo> #N — Launch CoderBot on an issue" },
  { id: "action-review" as const, label: "/review <repo> #N — Launch ReviewerBot on PR" },
  { id: "action-status" as const, label: "/status <repo> #N — Check issue & PR run status" },
  { id: "action-doctor" as const, label: "/doctor — Platform diagnostics & profile health" },
  { id: "chat-settings" as const, label: "Chat Settings" },
  { id: "settings-general" as const, label: "Settings: General" },
  { id: "settings-usage" as const, label: "Settings: Usage" },
] as const;

export type SlashActionId = (typeof SLASH_ACTIONS)[number]["id"];

/** Serialize composer chips + draft into the prompt text sent to the agent. */
export function serializeComposerPrompt(
  draft: string,
  skill: { name: string } | null,
  mentions: Array<{ name: string }>,
): string {
  const body = draft.replace(/^\s+/, "");
  const mentionPrefix = mentions.map((member) => `@${member.name}`).join(" ");
  const afterSkill = [mentionPrefix, body].filter((part) => part.trim().length > 0).join(" ");
  if (!skill) return afterSkill.trimEnd();
  return afterSkill.trim().length > 0 ? `/${skill.name}\n${afterSkill}` : `/${skill.name}`;
}

export function truncateSlashDescription(value: string, max = 72): string {
  const text = value.replace(/\s+/g, " ").trim();
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1).trimEnd()}…`;
}
