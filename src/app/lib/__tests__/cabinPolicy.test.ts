import { describe, expect, it } from "vitest";
import { classifyConfirmation, groundAgentMessage, isNavigationRequested } from "../cabinPolicy";

describe("classifyConfirmation", () => {
  it.each(["确认继续", "我确认", "可以打开", "好的", "打开吧"])("accepts explicit confirmation: %s", (text) => {
    expect(classifyConfirmation(text)).toBe("confirm");
  });

  it.each(["取消", "不要打开", "好吧，不要打开了", "不好", "我不同意"])("lets cancellation win: %s", (text) => {
    expect(classifyConfirmation(text)).toBe("cancel");
  });

  it.each(["天气好吗？", "为什么有风险？", "我再想想", "打开天窗安全吗？"])("does not infer authorization: %s", (text) => {
    expect(classifyConfirmation(text)).toBe("none");
  });
});

describe("isNavigationRequested", () => {
  it("distinguishes search from an explicit navigation request", () => {
    expect(isNavigationRequested("帮我找一个顺路快充站")).toBe(false);
    expect(isNavigationRequested("找个顺路快充并导航")).toBe(true);
  });
});

describe("groundAgentMessage", () => {
  it("replaces an ungrounded success claim", () => {
    expect(groundAgentMessage("已帮你打开天窗。", [])).toContain("不能确认");
  });

  it("keeps a success claim backed by a tool result", () => {
    const message = "已帮你打开天窗。";
    expect(groundAgentMessage(message, [{ status: "success", output: { executed: true } }])).toBe(message);
  });
});
