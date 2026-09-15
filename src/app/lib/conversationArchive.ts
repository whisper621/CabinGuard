export type ArchivedMessage = {
  role: "user" | "assistant";
  content: string;
  time: string;
};

export type ConversationRecord = {
  sessionId: string;
  title: string;
  messages: ArchivedMessage[];
  scenario: "default" | "rain" | "moving" | "highway" | "low_battery" | "child" | "pickup" | "rest" | "air_quality";
  occupantRole: string;
  updatedAt: string;
};

const isMessage = (value: unknown): value is ArchivedMessage => {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<ArchivedMessage>;
  return (
    (item.role === "user" || item.role === "assistant") &&
    typeof item.content === "string" &&
    typeof item.time === "string"
  );
};

export function readConversationArchive(raw: string | null): ConversationRecord[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((value): value is ConversationRecord => {
      if (!value || typeof value !== "object") return false;
      const item = value as Partial<ConversationRecord>;
      return (
        typeof item.sessionId === "string" &&
        typeof item.title === "string" &&
        Array.isArray(item.messages) &&
        item.messages.every(isMessage) &&
        ["default", "rain", "moving", "highway", "low_battery", "child", "pickup", "rest", "air_quality"].includes(item.scenario ?? "") &&
        typeof item.occupantRole === "string" &&
        typeof item.updatedAt === "string"
      );
    });
  } catch {
    return [];
  }
}

export function upsertConversation(
  records: ConversationRecord[],
  next: ConversationRecord,
  limit = 20,
): ConversationRecord[] {
  return [next, ...records.filter((record) => record.sessionId !== next.sessionId)].slice(0, limit);
}
