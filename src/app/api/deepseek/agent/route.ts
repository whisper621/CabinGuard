import { NextRequest, NextResponse } from "next/server";
import { ProxyAgent, request } from "undici";
import { z } from "zod";
import {
  clearPendingAction,
  consumeRateLimit,
  createSunroofConfirmation,
  getCabinSession,
  takeSunroofConfirmation,
  updateCabinSession,
} from "../../../lib/cabinSession";
import { CABIN_TOOL_VERSION, cabinToolDefinitions, executeCabinTool } from "../../../lib/cabinTools";
import { classifyConfirmation, groundAgentMessage, isNavigationRequested } from "../../../lib/cabinPolicy";

export const runtime = "nodejs";
const AGENT_PROMPT_VERSION = "3.2.0-next";

type ToolCall = {
  id: string;
  type: "function";
  function: { name: string; arguments: string };
};

type ModelMessage = {
  role: "system" | "user" | "assistant" | "tool";
  content?: string | null;
  tool_calls?: ToolCall[];
  tool_call_id?: string;
};

type DeepSeekResponse = {
  model?: string;
  choices?: Array<{ message?: ModelMessage }>;
  usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };
  error?: { code?: string; message?: string };
};

type Trace = {
  id: string;
  name: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  status: "success" | "blocked";
};

const agentRequestSchema = z.object({
  text: z.string().trim().min(1).max(500),
  sessionId: z.string().uuid(),
  history: z.array(z.object({
    role: z.enum(["user", "assistant"]),
    content: z.string().trim().min(1).max(1000),
  })).max(10).default([]),
});

const systemPrompt = `你是 CabinGuard，一名可信的智能座舱任务 Agent。你的职责是把用户目标转成真实工具调用，并依据工具返回值用简洁中文反馈。

执行规则：
1. 调节空调前先读取 get_climate_state；涉及天窗先读取 get_vehicle_state 和 get_weather；补能前先读取 get_vehicle_state。
2. 不得编造状态、地点、执行成功或工具结果。只有工具返回 executed=true 或 navigation_started=true 才能声称完成。
3. 车速不低于 80 km/h 时，开启天窗前必须读取状态和天气，再调用 control_sunroof 且 confirmed=false，让工具层创建一次性确认状态；工具层返回确认要求后，向用户说明风噪风险。用户下一轮明确确认时由服务端恢复该动作。降雨概率不低于 50% 时不要开启天窗。
4. 收到后备箱请求时，先调用 get_vehicle_state，再调用 control_trunk，由工具层执行最终安全校验并返回是否被拦截；不要只凭模型判断后直接结束。
5. “舒服一点”等缺少关键偏好的表达应先追问；明确温度或循环模式时可以执行。
6. 找到充电站后，仅在用户明确要求导航时调用 start_navigation。
7. 一次请求可能需要多次工具调用。根据上一个工具返回继续决策，直到完成、需要澄清或被安全规则阻止。
8. 最终回复控制在 120 字内，说明执行对象、关键参数、结果或未执行原因。
9. 浏览器定位只能作为路线原型上下文；充电站目录、道路距离和 ETA 来自演示沙箱。用户追问数据来源或真实性时必须明确此边界。`;

async function callDeepSeek(messages: ModelMessage[]) {
  const apiKey = process.env.DEEPSEEK_API_KEY;
  if (!apiKey) throw new Error("DEEPSEEK_API_KEY is not configured");

  const proxyUrl = process.env.HTTPS_PROXY || process.env.HTTP_PROXY;
  const dispatcher = proxyUrl ? new ProxyAgent(proxyUrl) : undefined;
  const requestBody = JSON.stringify({
    model: process.env.DEEPSEEK_MODEL || "deepseek-v4-flash",
    messages,
    tools: cabinToolDefinitions,
    tool_choice: "auto",
    stream: false,
    max_tokens: 700,
    temperature: 0.1,
  });

  let lastError: unknown;
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      const response = await request("https://api.deepseek.com/chat/completions", {
        method: "POST",
        dispatcher,
        headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
        body: requestBody,
        headersTimeout: 15_000,
        bodyTimeout: 30_000,
      });
      const data = (await response.body.json()) as DeepSeekResponse;
      if (response.statusCode < 200 || response.statusCode >= 300) {
        const providerError = new Error(data.error?.message || `DeepSeek request failed: ${response.statusCode}`);
        if (response.statusCode < 500 || attempt === 3) throw providerError;
        lastError = providerError;
      } else {
        const message = data.choices?.[0]?.message;
        if (!message) throw new Error("DeepSeek returned no message");
        return { message, model: data.model || "deepseek", usage: data.usage };
      }
    } catch (error) {
      lastError = error;
      if (attempt === 3) throw error;
    }
    await new Promise((resolve) => setTimeout(resolve, attempt * 250));
  }
  throw lastError instanceof Error ? lastError : new Error("DeepSeek request failed");
}

export async function POST(req: NextRequest) {
  try {
    const parsed = agentRequestSchema.safeParse(await req.json().catch(() => null));
    if (!parsed.success) {
      return NextResponse.json(
        { error: { code: "invalid_request", message: "text, sessionId and a bounded history are required" } },
        { status: 400 },
      );
    }

    const forwardedFor = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
    const rate = consumeRateLimit(forwardedFor || "local-anonymous");
    if (!rate.allowed) {
      return NextResponse.json(
        { error: { code: "rate_limited", message: "请求过于频繁，请稍后再试" } },
        { status: 429, headers: { "Retry-After": String(rate.retryAfterSeconds) } },
      );
    }

    const session = getCabinSession(parsed.data.sessionId);
    if (!session) {
      return NextResponse.json(
        { error: { code: "session_not_found", message: "演示会话已过期，请重置后重试" } },
        { status: 404 },
      );
    }

    const confirmationText = parsed.data.text;
    if (session.pendingAction?.kind === "sunroof") {
      const confirmationDecision = classifyConfirmation(confirmationText);
      if (confirmationDecision === "cancel") {
        clearPendingAction(session);
        return NextResponse.json({
          message: "已取消本次高速天窗操作。",
          sessionId: session.id,
          vehicle: session.vehicle,
          traces: [],
          model: "server-confirmation",
          turns: 0,
          totalTokens: 0,
          promptVersion: AGENT_PROMPT_VERSION,
          toolVersion: CABIN_TOOL_VERSION,
        });
      }
      if (confirmationDecision === "confirm") {
        const pending = takeSunroofConfirmation(session);
        if (pending) {
          const execution = executeCabinTool(
            "control_sunroof",
            { target_percent: pending.targetPercent, confirmed: true },
            session.vehicle,
            { allowHighSpeedSunroof: true, bypassReadPrerequisites: true },
          );
          updateCabinSession(session, execution.vehicle);
          return NextResponse.json({
            message: execution.status === "success"
              ? `已根据你的确认，将天窗打开至 ${pending.targetPercent}%。`
              : `本次天窗操作未执行：${String(execution.output.reason || "安全条件不满足")}。`,
            sessionId: session.id,
            vehicle: execution.vehicle,
            traces: [{
              id: `server-confirmation-${Date.now()}`,
              name: "control_sunroof",
              input: { target_percent: pending.targetPercent, confirmed: true },
              output: execution.output,
              status: execution.status,
            }],
            model: "server-confirmation",
            turns: 0,
            totalTokens: 0,
            promptVersion: AGENT_PROMPT_VERSION,
            toolVersion: CABIN_TOOL_VERSION,
          });
        }
      }
      return NextResponse.json({
        message: "我没有执行天窗操作。请明确回复“确认继续”或“取消”，其他表达不会被视为高风险授权。",
        sessionId: session.id,
        vehicle: session.vehicle,
        traces: [],
        model: "server-confirmation",
        turns: 0,
        totalTokens: 0,
        promptVersion: AGENT_PROMPT_VERSION,
        toolVersion: CABIN_TOOL_VERSION,
      });
    }

    let vehicle = session.vehicle;
    const history = parsed.data.history;
    const messages: ModelMessage[] = [
      { role: "system", content: systemPrompt },
      ...history.map((item) => ({ role: item.role, content: item.content } as ModelMessage)),
      { role: "user", content: parsed.data.text },
    ];
    const traces: Trace[] = [];
    let model = "deepseek";
    let totalTokens = 0;

    for (let turn = 1; turn <= 6; turn += 1) {
      const result = await callDeepSeek(messages);
      model = result.model;
      totalTokens += result.usage?.total_tokens || 0;
      const toolCalls = result.message.tool_calls || [];

      if (!toolCalls.length) {
        updateCabinSession(session, vehicle);
        const fallbackMessage = result.message.content || "我暂时无法完成该请求，请换一种说法。";
        return NextResponse.json({
          message: groundAgentMessage(fallbackMessage, traces),
          sessionId: session.id,
          vehicle,
          traces,
          model,
          turns: turn,
          totalTokens,
          promptVersion: AGENT_PROMPT_VERSION,
          toolVersion: CABIN_TOOL_VERSION,
        });
      }

      messages.push({
        role: "assistant",
        content: result.message.content || null,
        tool_calls: toolCalls,
      });

      for (const toolCall of toolCalls) {
        let input: Record<string, unknown> = {};
        try {
          input = JSON.parse(toolCall.function.arguments || "{}") as Record<string, unknown>;
        } catch {
          input = {};
        }
        const successfulTools = traces
          .filter((trace) => trace.status === "success")
          .map((trace) => trace.name);
        const allowedNavigationDestinations = traces.flatMap((trace) => {
          if (trace.name !== "search_charging_stations" || trace.status !== "success") return [];
          const stations = trace.output.stations;
          if (!Array.isArray(stations)) return [];
          return stations.flatMap((station) => {
            if (!station || typeof station !== "object" || !("name" in station)) return [];
            return typeof station.name === "string" ? [station.name] : [];
          });
        });
        const execution = executeCabinTool(toolCall.function.name, input, vehicle, {
          priorSuccessfulTools: successfulTools,
          navigationAuthorized: isNavigationRequested(parsed.data.text),
          allowedNavigationDestinations,
          onSunroofConfirmationRequired: (targetPercent) => createSunroofConfirmation(session, targetPercent),
        });
        vehicle = execution.vehicle;
        updateCabinSession(session, vehicle);
        traces.push({
          id: toolCall.id,
          name: toolCall.function.name,
          input,
          output: execution.output,
          status: execution.status,
        });
        messages.push({
          role: "tool",
          tool_call_id: toolCall.id,
          content: JSON.stringify(execution.output),
        });
      }
    }

    return NextResponse.json({
      message: "任务执行步骤超过上限，我已停止继续操作，请拆分请求后重试。",
      sessionId: session.id,
      vehicle,
      traces,
      model,
      turns: 6,
      totalTokens,
      promptVersion: AGENT_PROMPT_VERSION,
      toolVersion: CABIN_TOOL_VERSION,
      stopped: true,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Agent execution failed";
    return NextResponse.json({ error: { message } }, { status: 502 });
  }
}
