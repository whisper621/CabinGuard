import { describe, expect, it } from "vitest";
import { readConversationArchive, upsertConversation } from "../conversationArchive";

const record = {
  sessionId: "session-1",
  title: "导航到天安门",
  messages: [{ role: "user" as const, content: "导航到天安门", time: "10:00:00" }],
  scenario: "default" as const,
  occupantRole: "driver",
  updatedAt: "2026-09-14T10:00:00.000Z",
};

describe("conversation archive", () => {
  it("ignores corrupt browser storage", () => {
    expect(readConversationArchive("not-json")).toEqual([]);
  });

  it("updates a conversation without deleting earlier sessions", () => {
    const second = { ...record, sessionId: "session-2", title: "第二段对话" };
    expect(upsertConversation([record], second).map((item) => item.sessionId)).toEqual([
      "session-2",
      "session-1",
    ]);
  });
});
