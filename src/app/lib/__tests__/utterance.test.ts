import { describe, expect, it } from "vitest";
import { appendSpeechSegment } from "../utterance";

describe("appendSpeechSegment", () => {
  it("keeps earlier speech when a later segment arrives", () => {
    expect(appendSpeechSegment("打开空调", "导航到天安门")).toBe("打开空调，导航到天安门");
  });

  it("does not duplicate a repeated recognition result", () => {
    expect(appendSpeechSegment("打开空调", "打开空调")).toBe("打开空调");
  });
});
