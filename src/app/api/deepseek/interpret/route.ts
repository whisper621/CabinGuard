import { NextRequest, NextResponse } from "next/server";
import { ProxyAgent, request } from "undici";
import { z } from "zod";
import { consumeRateLimit } from "../../../lib/cabinSession";

export const runtime = "nodejs";

type DeepSeekResponse = {
  choices?: Array<{ message?: { content?: string | null } }>;
  model?: string;
  usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };
  error?: { message?: string; type?: string; code?: string | null };
};

const interpretationSchema = z.object({
  intent: z.enum(["sunroof", "charging", "climate", "trunk", "status", "unknown"]),
  percent: z.number().min(0).max(100).nullable(),
  temperature: z.number().min(16).max(30).nullable(),
  circulation: z.enum(["inside", "outside"]).nullable(),
  confidence: z.number().min(0).max(1),
}).strict();

export async function POST(req: NextRequest) {
  if (!process.env.DEEPSEEK_API_KEY) {
    return NextResponse.json(
      { error: { code: "not_configured", message: "DEEPSEEK_API_KEY is not configured" } },
      { status: 503 },
    );
  }

  const forwardedFor = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  const rate = consumeRateLimit(`interpret:${forwardedFor || "local-anonymous"}`);
  if (!rate.allowed) {
    return NextResponse.json(
      { error: { code: "rate_limited", message: "请求过于频繁，请稍后再试" } },
      { status: 429, headers: { "Retry-After": String(rate.retryAfterSeconds) } },
    );
  }

  const payload = (await req.json().catch(() => null)) as { text?: unknown } | null;
  const text = typeof payload?.text === "string" ? payload.text.trim() : "";
  if (!text || text.length > 500) {
    return NextResponse.json(
      { error: { code: "invalid_input", message: "text must contain 1-500 characters" } },
      { status: 400 },
    );
  }

  const proxyUrl = process.env.HTTPS_PROXY || process.env.HTTP_PROXY;
  const dispatcher = proxyUrl ? new ProxyAgent(proxyUrl) : undefined;
  const model = process.env.DEEPSEEK_MODEL || "deepseek-v4-flash";

  try {
    const response = await request("https://api.deepseek.com/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${process.env.DEEPSEEK_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model,
        messages: [
          {
            role: "system",
            content:
              "你是智能座舱任务解析器。只输出JSON对象，不要输出解释。intent只能是sunroof、charging、climate、trunk、status、unknown之一。字段格式：{\"intent\":\"...\",\"percent\":number|null,\"temperature\":number|null,\"circulation\":\"inside\"|\"outside\"|null,\"confidence\":0到1}。不要声称任务已执行。",
          },
          { role: "user", content: text },
        ],
        thinking: { type: "disabled" },
        response_format: { type: "json_object" },
        max_tokens: 160,
        stream: false,
      }),
      dispatcher,
      headersTimeout: 15_000,
      bodyTimeout: 30_000,
    });
    const data = (await response.body.json()) as DeepSeekResponse;

    if (response.statusCode < 200 || response.statusCode >= 300) {
      return NextResponse.json(
        { error: data.error ?? { code: "provider_error", message: "DeepSeek request failed" } },
        { status: response.statusCode },
      );
    }

    const content = data.choices?.[0]?.message?.content;
    if (!content) {
      return NextResponse.json(
        { error: { code: "empty_response", message: "DeepSeek returned no interpretation" } },
        { status: 502 },
      );
    }

    const interpretation = interpretationSchema.safeParse(JSON.parse(content));
    if (!interpretation.success) {
      return NextResponse.json(
        { error: { code: "invalid_provider_output", message: "DeepSeek returned an invalid interpretation" } },
        { status: 502 },
      );
    }
    return NextResponse.json({ interpretation: interpretation.data, model: data.model ?? model, usage: data.usage });
  } catch (error) {
    console.error("Error in /api/deepseek/interpret:", error);
    return NextResponse.json(
      { error: { code: "provider_unavailable", message: "Unable to reach DeepSeek" } },
      { status: 502 },
    );
  }
}
