export type ConfirmationDecision = "confirm" | "cancel" | "none";

const cancelSignals = [
  "取消",
  "不要",
  "别开",
  "停止",
  "算了",
  "不确认",
  "不同意",
  "不可以",
  "不行",
  "不好",
  "否",
];

const explicitConfirmations = new Set([
  "确认",
  "我确认",
  "确认继续",
  "继续",
  "继续执行",
  "继续打开",
  "可以",
  "可以打开",
  "同意",
  "我同意",
  "是",
  "是的",
  "好",
  "好的",
  "打开",
  "打开吧",
]);

const normalizeDecisionText = (text: string) =>
  text.trim().toLowerCase().replace(/[\s，。！？、,.!?；;：:“”'‘’]/g, "");

/**
 * Classifies a reply to a pending high-risk action.
 * Cancellation always wins, and confirmation must match an explicit whole reply.
 */
export function classifyConfirmation(text: string): ConfirmationDecision {
  const normalized = normalizeDecisionText(text);
  if (!normalized) return "none";
  if (cancelSignals.some((signal) => normalized.includes(signal))) return "cancel";
  return explicitConfirmations.has(normalized) ? "confirm" : "none";
}

export function isNavigationRequested(text: string) {
  return /导航|带我去|带路|规划路线|开始路线|前往.*(?:充电|超充|能源站)|去.*(?:充电|超充|能源站)/.test(text);
}

type GroundingTrace = {
  status: "success" | "blocked";
  output: Record<string, unknown>;
};

/** Prevents the model from claiming a side effect that no tool result proves. */
export function groundAgentMessage(message: string, traces: GroundingTrace[]) {
  const claimsSideEffect = /已(?:经)?(?:将|为|帮|开始|完成|打开|关闭|设置|切换)|导航已开始|操作成功/.test(message);
  if (!claimsSideEffect) return message;

  const hasVerifiedSideEffect = traces.some(
    (trace) => trace.status === "success"
      && (trace.output.executed === true || trace.output.navigation_started === true),
  );
  if (hasVerifiedSideEffect) return message;

  const blockedReason = [...traces]
    .reverse()
    .find((trace) => trace.status === "blocked")?.output.reason;
  return blockedReason
    ? `本次操作未执行：${String(blockedReason)}。`
    : "本次没有获得可核验的工具执行结果，因此我不能确认操作已经完成。";
}
